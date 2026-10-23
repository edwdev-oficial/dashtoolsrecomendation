from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pandas as pd


_ACCOUNT_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(.+?)\s*$")
_FILTER_PATTERN = re.compile(
    r"Customers\s+é\s+(.*?)\s*\n\s*A\s+é\s+(\d{4})",
    flags=re.IGNORECASE | re.DOTALL,
)


def normalizar_id_conta(value: Any) -> str:
    """Normalize SAP account ids so 0020618571 and 20618571 match."""
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    digits = re.sub(r"\D", "", text)
    if not digits:
        return text

    normalized = digits.lstrip("0")
    return normalized or "0"


def _parse_account(text: str) -> tuple[str, str] | None:
    match = _ACCOUNT_PATTERN.match(str(text))
    if not match:
        return None

    account_id = normalizar_id_conta(match.group(1))
    account_name = match.group(2).strip()
    if not account_id:
        return None
    return account_id, account_name


def extrair_contas_parque(frames: list[pd.DataFrame]) -> dict[str, str]:
    """Return accounts represented by the uploaded current-fleet files."""
    accounts: dict[str, str] = {}

    for frame in frames:
        if "Id" not in frame.columns:
            continue

        names = (
            frame["Razao Social"]
            if "Razao Social" in frame.columns
            else pd.Series("", index=frame.index, dtype="string")
        )

        for raw_id, raw_name in zip(frame["Id"], names):
            account_id = normalizar_id_conta(raw_id)
            if not account_id:
                continue
            account_name = "" if pd.isna(raw_name) else str(raw_name).strip()
            if account_id not in accounts or not accounts[account_id]:
                accounts[account_id] = account_name

    return accounts


def extrair_metadados_filtro_ams(df: pd.DataFrame) -> dict[str, Any]:
    """Read the Power BI filter footer kept in the raw AMS workbook."""
    metadata: dict[str, Any] = {
        "metadata_encontrada": False,
        "ano_filtro": None,
        "contas": {},
    }

    if "Cliente" not in df.columns:
        return metadata

    cliente = df["Cliente"].astype("string")
    filter_rows = cliente[
        cliente.str.contains("Filtros aplicados", case=False, na=False)
    ]
    if filter_rows.empty:
        return metadata

    raw_filter = str(filter_rows.iloc[-1])
    match = _FILTER_PATTERN.search(raw_filter)
    if not match:
        return metadata

    customers_text, year_text = match.groups()
    parts = re.split(r",\s*|\s+ou\s+", customers_text.strip())

    accounts: dict[str, str] = {}
    for part in parts:
        parsed = _parse_account(part)
        if parsed is None:
            continue
        account_id, account_name = parsed
        accounts[account_id] = account_name

    metadata.update(
        {
            "metadata_encontrada": True,
            "ano_filtro": int(year_text),
            "contas": accounts,
        }
    )
    return metadata


def _ano_dados_ams(df: pd.DataFrame) -> int | None:
    if "ano_reparo" not in df.columns:
        return None

    years = pd.to_numeric(df["ano_reparo"], errors="coerce").dropna().unique()
    if len(years) != 1:
        return None
    return int(years[0])


def _account_rows(accounts: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"id": account_id, "nome": accounts[account_id]}
        for account_id in sorted(accounts)
    ]


def validar_carga(
    parque_frames: list[pd.DataFrame],
    ams_sources: list[tuple[str, pd.DataFrame]],
) -> dict[str, Any]:
    """Validate fleet accounts against the customer filters of each AMS file."""
    parque_accounts = extrair_contas_parque(parque_frames)
    ams_details: list[dict[str, Any]] = []

    for filename, frame in ams_sources:
        metadata = extrair_metadados_filtro_ams(frame)
        data_year = _ano_dados_ams(frame)
        ams_details.append(
            {
                "arquivo": filename,
                "ano_dados": data_year,
                "ano_filtro": metadata["ano_filtro"],
                "metadata_encontrada": metadata["metadata_encontrada"],
                "contas": metadata["contas"],
                "qtd_contas": len(metadata["contas"]),
                "ano_coerente": (
                    metadata["ano_filtro"] is None
                    or data_year is None
                    or metadata["ano_filtro"] == data_year
                ),
            }
        )

    details_with_metadata = [
        detail for detail in ams_details if detail["metadata_encontrada"]
    ]
    account_sets = [set(detail["contas"]) for detail in details_with_metadata]
    ams_union = set().union(*account_sets) if account_sets else set()
    ams_intersection = set.intersection(*account_sets) if account_sets else set()

    parque_ids = set(parque_accounts)
    missing_in_ams = parque_ids - ams_intersection if account_sets else set()
    extra_in_ams = ams_union - parque_ids

    filters_consistent = True
    if account_sets:
        filters_consistent = all(
            account_set == account_sets[0] for account_set in account_sets[1:]
        )

    years = [
        detail["ano_filtro"] or detail["ano_dados"]
        for detail in ams_details
        if (detail["ano_filtro"] or detail["ano_dados"]) is not None
    ]
    duplicate_years = sorted(
        year for year in set(years) if years.count(year) > 1
    )
    unique_years = sorted(set(years))
    missing_years: list[int] = []
    if len(unique_years) >= 2:
        expected_years = set(range(unique_years[0], unique_years[-1] + 1))
        missing_years = sorted(expected_years - set(unique_years))

    missing_metadata = [
        detail["arquivo"]
        for detail in ams_details
        if not detail["metadata_encontrada"]
    ]
    incoherent_years = [
        detail["arquivo"]
        for detail in ams_details
        if not detail["ano_coerente"]
    ]

    errors: list[str] = []
    warnings: list[str] = []

    if parque_frames and not ams_sources:
        warnings.append(
            "Nenhum arquivo AMS foi carregado; não foi possível validar o histórico de reparações."
        )
    if ams_sources and not parque_frames:
        warnings.append(
            "Nenhum arquivo de parque foi carregado; não foi possível comparar o universo de contas."
        )
    if missing_metadata:
        warnings.append(
            "Não foi possível ler os filtros aplicados em todos os arquivos AMS."
        )
    if not filters_consistent:
        errors.append(
            "Os arquivos AMS não utilizam a mesma seleção de contas em todos os anos."
        )
    if missing_in_ams and parque_ids and account_sets:
        errors.append(
            "Existem contas do parque ausentes do filtro de pelo menos um arquivo AMS."
        )
    if duplicate_years:
        errors.append("Existem anos AMS duplicados na carga.")
    if incoherent_years:
        errors.append(
            "O ano informado no filtro AMS diverge do ano associado ao arquivo."
        )
    if extra_in_ams:
        warnings.append(
            "Existem contas no filtro AMS sem arquivo correspondente no parque atual."
        )
    if missing_years:
        warnings.append("A sequência de anos AMS possui lacunas.")

    if errors:
        status = "error"
    elif warnings:
        status = "warning"
    else:
        status = "ok"

    detail_rows = [
        {
            "Arquivo": detail["arquivo"],
            "Ano": detail["ano_filtro"] or detail["ano_dados"],
            "Contas no filtro": detail["qtd_contas"],
            "Filtro identificado": "Sim" if detail["metadata_encontrada"] else "Não",
            "Ano coerente": "Sim" if detail["ano_coerente"] else "Não",
        }
        for detail in ams_details
    ]

    fingerprint_payload = {
        "parque": sorted(parque_ids),
        "ams": [
            {
                "arquivo": detail["arquivo"],
                "ano": detail["ano_filtro"] or detail["ano_dados"],
                "contas": sorted(detail["contas"]),
            }
            for detail in ams_details
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]

    return {
        "status": status,
        "bloqueante": bool(errors),
        "errors": errors,
        "warnings": warnings,
        "contas_parque": _account_rows(parque_accounts),
        "contas_ams": _account_rows(
            {
                account_id: next(
                    (
                        detail["contas"][account_id]
                        for detail in details_with_metadata
                        if account_id in detail["contas"]
                    ),
                    "",
                )
                for account_id in ams_union
            }
        ),
        "contas_ausentes_ams": _account_rows(
            {account_id: parque_accounts[account_id] for account_id in missing_in_ams}
        ),
        "contas_extras_ams": _account_rows(
            {
                account_id: next(
                    (
                        detail["contas"][account_id]
                        for detail in details_with_metadata
                        if account_id in detail["contas"]
                    ),
                    "",
                )
                for account_id in extra_in_ams
            }
        ),
        "filtros_consistentes": filters_consistent,
        "anos": unique_years,
        "anos_duplicados": duplicate_years,
        "anos_ausentes": missing_years,
        "arquivos_sem_metadados": missing_metadata,
        "arquivos_ano_incoerente": incoherent_years,
        "detalhes_ams": detail_rows,
        "fingerprint": fingerprint,
    }
