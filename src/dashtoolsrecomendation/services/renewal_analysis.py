from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd


ANALYSIS_START_YEAR = 1900
DEFAULT_TAX_FACTOR = 1.4
SERIAL_COLUMNS = ("Número de Série", "Número de série")


@dataclass(frozen=True)
class RenewalWeights:
    """Pesos do índice relativo de prioridade de renovação."""

    idade: float = 0.25
    frequencia: float = 0.30
    custo: float = 0.30
    recorrencia: float = 0.15

    def validate(self) -> None:
        total = self.idade + self.frequencia + self.custo + self.recorrencia
        if not np.isclose(total, 1.0):
            raise ValueError("Os pesos do índice de prioridade devem somar 1,0.")


def normalizar_numero_serie(serie: pd.Series) -> pd.Series:
    """Normaliza números de série vindos de Excel como texto ou número decimal."""
    result = (
        serie.astype("string")
        .str.strip()
        .str.replace(r"^(\d+)\.0+$", r"\1", regex=True)
    )
    return result.replace(
        {
            "": pd.NA,
            "nan": pd.NA,
            "None": pd.NA,
            "<NA>": pd.NA,
        }
    )


def _serie_canonica(df: pd.DataFrame) -> pd.Series:
    aliases = [column for column in SERIAL_COLUMNS if column in df.columns]
    if not aliases:
        return pd.Series(pd.NA, index=df.index, dtype="string")

    result = normalizar_numero_serie(df[aliases[0]])
    for column in aliases[1:]:
        result = result.fillna(normalizar_numero_serie(df[column]))
    return result


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def _text(df: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="string")
    return (
        df[column]
        .astype("string")
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        .fillna(default)
    )


def preparar_ams_periodo(
    df_ams: pd.DataFrame,
    anos: Iterable[int],
    series: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Normaliza a base AMS e limita a análise à janela e às séries selecionadas."""
    result = df_ams.copy()
    result["Número de Série"] = _serie_canonica(result)
    result["ano_reparo"] = pd.to_numeric(
        result.get("ano_reparo", pd.Series(pd.NA, index=result.index)),
        errors="coerce",
    ).astype("Int64")

    for column in [
        "# Reparos",
        "# Notif.",
        "Custo de Reparos",
        "Pagado pelo Cliente",
        "Economia",
        "Idade em Anos",
    ]:
        result[column] = _numeric(result, column)

    result["Modelo"] = _text(result, "Modelo", "Não identificado")
    result["Razão Social AMS"] = _text(
        result,
        "Razão Social" if "Razão Social" in result.columns else "Razao Social",
        "",
    )

    anos_validos = sorted({int(ano) for ano in anos if pd.notna(ano)})
    if anos_validos:
        result = result[result["ano_reparo"].isin(anos_validos)]
    else:
        result = result.iloc[0:0]

    if series is not None:
        series_validas = {
            str(serie).strip()
            for serie in series
            if pd.notna(serie) and str(serie).strip()
        }
        result = result[result["Número de Série"].isin(series_validas)]

    return result.reset_index(drop=True)


def _anos_observados(
    data_compra: pd.Series,
    anos_selecionados: list[int],
) -> pd.Series:
    if not anos_selecionados:
        return pd.Series(0, index=data_compra.index, dtype="int64")

    compra = pd.to_datetime(data_compra, errors="coerce")
    ano_compra = compra.dt.year
    observed = pd.Series(0, index=data_compra.index, dtype="int64")
    for ano in anos_selecionados:
        observed += (ano_compra.isna() | ano_compra.le(ano)).astype(int)
    return observed.clip(lower=1)


def _percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.empty or numeric.nunique(dropna=False) <= 1:
        return pd.Series(0.0, index=series.index)
    return numeric.rank(method="average", pct=True).fillna(0)


def _classificar_prioridade(row: pd.Series) -> str:
    reparos = float(row["Reparações no período"])
    score = float(row["Índice de prioridade"])
    idade = float(row["Idade atual"])

    if reparos <= 0:
        return "Monitorar" if idade >= 8 else "Manter"
    if score >= 70 and reparos >= 2:
        return "Troca prioritária"
    if score >= 50:
        return "Planejar renovação"
    if score >= 30 or reparos >= 2:
        return "Monitorar"
    return "Manter"


def _motivo_principal(row: pd.Series) -> str:
    alta_freq = row["Percentil frequência"] >= 0.75
    alto_custo = row["Percentil custo"] >= 0.75
    idade_alta = row["Idade atual"] >= 8
    recorrente = row["Recorrência"] >= 0.67

    if alta_freq and alto_custo:
        return "Alta frequência e alto custo"
    if recorrente and alta_freq:
        return "Reparações recorrentes"
    if alto_custo:
        return "Alto custo no período"
    if alta_freq:
        return "Alta frequência no período"
    if idade_alta:
        return "Idade elevada"
    return "Baixo impacto recente"


def preparar_base_maquinas(
    df_parque: pd.DataFrame,
    df_ams: pd.DataFrame,
    anos: Iterable[int],
    *,
    data_corte: date | pd.Timestamp | None = None,
    tax_factor: float = DEFAULT_TAX_FACTOR,
    weights: RenewalWeights = RenewalWeights(),
) -> pd.DataFrame:
    """Cria uma linha analítica por máquina para diagnóstico e priorização.

    O índice de prioridade é relativo ao conjunto filtrado e combina idade,
    frequência, custo e recorrência. Ele não estima falha futura nem economia.
    """
    weights.validate()
    anos_validos = sorted({int(ano) for ano in anos if pd.notna(ano)})
    referencia = pd.Timestamp(data_corte or pd.Timestamp.today()).normalize()

    parque = df_parque.copy()
    parque["Número de Série"] = _serie_canonica(parque)
    parque = parque.dropna(subset=["Número de Série"])
    parque = parque.drop_duplicates("Número de Série", keep="last")

    data_compra = pd.to_datetime(
        parque.get("Data de compra", pd.Series(pd.NaT, index=parque.index)),
        errors="coerce",
    )
    idade_calculada = (referencia - data_compra).dt.days / 365.2425
    idade_existente = _numeric(parque, "idade_int (a)").astype(float)
    parque["Idade atual"] = idade_calculada.where(
        idade_calculada.notna(), idade_existente
    ).clip(lower=0)
    parque["Data de compra"] = data_compra
    parque["Modelo"] = _text(parque, "Modelo", "Não identificado")
    parque["Grupo"] = _text(parque, "Grupo", "Não informado")
    parque["Status da Ferramenta"] = _text(
        parque, "Status da Ferramenta", "Não informado"
    )
    parque["Razão Social"] = _text(
        parque,
        "Razão Social" if "Razão Social" in parque.columns else "Razao Social",
        "",
    )

    ams = preparar_ams_periodo(
        df_ams,
        anos_validos,
        series=parque["Número de Série"],
    )
    ams["Tem reparo"] = ams["# Reparos"].gt(0)

    if ams.empty:
        aggregate = pd.DataFrame(
            columns=[
                "Número de Série",
                "Reparações no período",
                "Notificações no período",
                "Custo líquido",
                "Pago líquido",
                "Valor absorvido líquido",
                "Anos com reparação",
                "Primeiro ano com reparação",
                "Último ano com reparação",
                "Modelo AMS",
            ]
        )
    else:
        aggregate = (
            ams.groupby("Número de Série", as_index=False)
            .agg(
                **{
                    "Reparações no período": ("# Reparos", "sum"),
                    "Notificações no período": ("# Notif.", "sum"),
                    "Custo líquido": ("Custo de Reparos", "sum"),
                    "Pago líquido": ("Pagado pelo Cliente", "sum"),
                    "Valor absorvido líquido": ("Economia", "sum"),
                    "Anos com reparação": (
                        "ano_reparo",
                        lambda values: values[
                            ams.loc[values.index, "Tem reparo"]
                        ].nunique(),
                    ),
                    "Primeiro ano com reparação": (
                        "ano_reparo",
                        lambda values: values[
                            ams.loc[values.index, "Tem reparo"]
                        ].min(),
                    ),
                    "Último ano com reparação": (
                        "ano_reparo",
                        lambda values: values[
                            ams.loc[values.index, "Tem reparo"]
                        ].max(),
                    ),
                    "Modelo AMS": ("Modelo", "last"),
                }
            )
        )

    result = parque.merge(
        aggregate,
        on="Número de Série",
        how="left",
        validate="one_to_one",
    )

    numeric_columns = [
        "Reparações no período",
        "Notificações no período",
        "Custo líquido",
        "Pago líquido",
        "Valor absorvido líquido",
        "Anos com reparação",
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    if "Modelo AMS" in result.columns:
        modelo_ams = result["Modelo AMS"].astype("string").str.strip()
        result["Modelo"] = result["Modelo"].mask(
            result["Modelo"].eq("Não identificado") & modelo_ams.notna(),
            modelo_ams,
        )

    result["Custo com impostos"] = result["Custo líquido"] * tax_factor
    result["Pago pelo cliente com impostos"] = result["Pago líquido"] * tax_factor
    result["Valor absorvido com impostos"] = (
        result["Valor absorvido líquido"] * tax_factor
    )
    result["Máquina reparada"] = result["Reparações no período"].gt(0)
    result["Anos observados"] = _anos_observados(
        result["Data de compra"], anos_validos
    )
    result["Reparações por ano observado"] = (
        result["Reparações no período"]
        / result["Anos observados"].replace(0, np.nan)
    ).fillna(0)
    result["Recorrência"] = (
        result["Anos com reparação"]
        / result["Anos observados"].replace(0, np.nan)
    ).fillna(0).clip(0, 1)

    result["Percentil idade"] = _percentile_score(result["Idade atual"])
    result["Percentil frequência"] = _percentile_score(
        result["Reparações por ano observado"]
    )
    result["Percentil custo"] = _percentile_score(result["Custo com impostos"])
    result["Percentil recorrência"] = _percentile_score(result["Recorrência"])

    result["Índice de prioridade"] = 100 * (
        weights.idade * result["Percentil idade"]
        + weights.frequencia * result["Percentil frequência"]
        + weights.custo * result["Percentil custo"]
        + weights.recorrencia * result["Percentil recorrência"]
    )
    result["Índice de prioridade"] = result["Índice de prioridade"].round(1)
    result["Recomendação"] = result.apply(_classificar_prioridade, axis=1)
    result["Motivo principal"] = result.apply(_motivo_principal, axis=1)

    return result.sort_values(
        ["Índice de prioridade", "Custo com impostos", "Reparações no período"],
        ascending=False,
    ).reset_index(drop=True)


def resumo_executivo(base: pd.DataFrame) -> dict[str, float]:
    maquinas = int(base["Número de Série"].nunique()) if not base.empty else 0
    reparadas = int(base["Máquina reparada"].sum()) if not base.empty else 0
    reparacoes = float(base["Reparações no período"].sum()) if not base.empty else 0
    custo = float(base["Custo com impostos"].sum()) if not base.empty else 0
    pago = (
        float(base["Pago pelo cliente com impostos"].sum())
        if not base.empty
        else 0
    )
    absorvido = (
        float(base["Valor absorvido com impostos"].sum())
        if not base.empty
        else 0
    )
    prioritarias = (
        int(base["Recomendação"].eq("Troca prioritária").sum())
        if not base.empty
        else 0
    )

    return {
        "maquinas": maquinas,
        "maquinas_reparadas": reparadas,
        "percentual_reparadas": reparadas / maquinas if maquinas else 0,
        "reparacoes": reparacoes,
        "reparacoes_por_maquina_parque": reparacoes / maquinas if maquinas else 0,
        "reparacoes_por_maquina_atendida": (
            reparacoes / reparadas if reparadas else 0
        ),
        "custo": custo,
        "pago": pago,
        "absorvido": absorvido,
        "custo_por_maquina_parque": custo / maquinas if maquinas else 0,
        "custo_por_maquina_atendida": custo / reparadas if reparadas else 0,
        "troca_prioritaria": prioritarias,
    }


def analise_faixas_idade(
    base: pd.DataFrame,
    idade_corte: int,
) -> pd.DataFrame:
    idade_maxima = int(np.ceil(base["Idade atual"].max())) if not base.empty else 0
    labels = [f"0 a {idade_corte}", f"{idade_corte + 1} a {idade_maxima}"]
    faixa = np.where(base["Idade atual"].le(idade_corte), labels[0], labels[1])
    work = base.assign(**{"Faixa etária": faixa})

    result = (
        work.groupby("Faixa etária", as_index=False)
        .agg(
            Máquinas=("Número de Série", "nunique"),
            **{
                "Máquinas reparadas": ("Máquina reparada", "sum"),
                "Reparações": ("Reparações no período", "sum"),
                "Custo": ("Custo com impostos", "sum"),
            },
        )
        .set_index("Faixa etária")
        .reindex(labels, fill_value=0)
        .reset_index()
    )
    denominator = result["Máquinas"].replace(0, np.nan)
    result["Reparações por máquina"] = (
        result["Reparações"] / denominator
    ).fillna(0)
    result["Custo por máquina"] = (result["Custo"] / denominator).fillna(0)
    result["Percentual reparadas"] = (
        result["Máquinas reparadas"] / denominator
    ).fillna(0)
    return result


def analise_modelos(base: pd.DataFrame) -> pd.DataFrame:
    if base.empty:
        return pd.DataFrame()
    result = (
        base.groupby("Modelo", as_index=False)
        .agg(
            Máquinas=("Número de Série", "nunique"),
            **{
                "Máquinas reparadas": ("Máquina reparada", "sum"),
                "Reparações": ("Reparações no período", "sum"),
                "Custo": ("Custo com impostos", "sum"),
                "Pago pelo cliente": ("Pago pelo cliente com impostos", "sum"),
                "Valor absorvido": ("Valor absorvido com impostos", "sum"),
                "Idade média": ("Idade atual", "mean"),
                "Troca prioritária": (
                    "Recomendação",
                    lambda values: values.eq("Troca prioritária").sum(),
                ),
            },
        )
    )
    denominator = result["Máquinas"].replace(0, np.nan)
    result["Reparações por máquina"] = (
        result["Reparações"] / denominator
    ).fillna(0)
    result["Custo por máquina"] = (result["Custo"] / denominator).fillna(0)
    result["Percentual reparadas"] = (
        result["Máquinas reparadas"] / denominator
    ).fillna(0)
    return result.sort_values(
        ["Reparações por máquina", "Custo por máquina"], ascending=False
    ).reset_index(drop=True)


def analise_anual(
    df_ams: pd.DataFrame,
    anos: Iterable[int],
    *,
    series: Iterable[str] | None = None,
    data_corte: date | pd.Timestamp | None = None,
    tax_factor: float = DEFAULT_TAX_FACTOR,
    projetar_ano_parcial: bool = False,
) -> pd.DataFrame:
    referencia = pd.Timestamp(data_corte or pd.Timestamp.today()).normalize()
    ams = preparar_ams_periodo(df_ams, anos, series=series)
    if ams.empty:
        return pd.DataFrame(
            columns=[
                "Ano",
                "Reparações realizadas",
                "Custo realizado",
                "Reparações projetadas",
                "Custo projetado",
                "Ano parcial",
            ]
        )

    result = (
        ams.groupby("ano_reparo", as_index=False)
        .agg(
            **{
                "Reparações realizadas": ("# Reparos", "sum"),
                "Custo líquido": ("Custo de Reparos", "sum"),
            }
        )
        .rename(columns={"ano_reparo": "Ano"})
        .sort_values("Ano")
    )
    result["Custo realizado"] = result["Custo líquido"] * tax_factor
    result["Ano parcial"] = result["Ano"].eq(referencia.year)
    result["Reparações projetadas"] = result["Reparações realizadas"].astype(float)
    result["Custo projetado"] = result["Custo realizado"].astype(float)

    if projetar_ano_parcial and referencia.year in set(result["Ano"]):
        inicio = pd.Timestamp(year=referencia.year, month=1, day=1)
        fim = pd.Timestamp(year=referencia.year, month=12, day=31)
        fracao = max((referencia - inicio).days + 1, 1) / ((fim - inicio).days + 1)
        mask = result["Ano"].eq(referencia.year)
        result.loc[mask, "Reparações projetadas"] = (
            result.loc[mask, "Reparações realizadas"] / fracao
        )
        result.loc[mask, "Custo projetado"] = (
            result.loc[mask, "Custo realizado"] / fracao
        )

    result["Reparações projetadas"] = result["Reparações projetadas"].round(1)
    return result.drop(columns=["Custo líquido"])


def composicao_custo(base: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Componente": ["Pago pelo cliente", "Valor absorvido"],
            "Valor": [
                base["Pago pelo cliente com impostos"].sum(),
                base["Valor absorvido com impostos"].sum(),
            ],
        }
    )


def cenario_renovacao(base: pd.DataFrame, quantidade: int) -> tuple[pd.DataFrame, dict[str, float]]:
    quantidade = max(0, min(int(quantidade), len(base)))
    selected = base.head(quantidade).copy()
    total_reparacoes = float(base["Reparações no período"].sum())
    total_custo = float(base["Custo com impostos"].sum())
    reparacoes = float(selected["Reparações no período"].sum())
    custo = float(selected["Custo com impostos"].sum())

    summary = {
        "maquinas": quantidade,
        "reparacoes": reparacoes,
        "percentual_reparacoes": (
            reparacoes / total_reparacoes if total_reparacoes else 0
        ),
        "custo": custo,
        "percentual_custo": custo / total_custo if total_custo else 0,
        "idade_media": float(selected["Idade atual"].mean()) if quantidade else 0,
    }
    return selected, summary


def dados_pareto(base: pd.DataFrame) -> pd.DataFrame:
    data = base.sort_values("Custo com impostos", ascending=False).copy()
    total = data["Custo com impostos"].sum()
    data["Posição"] = np.arange(1, len(data) + 1)
    data["Percentual acumulado"] = (
        data["Custo com impostos"].cumsum() / total if total else 0
    )
    return data


def reconciliar_fontes(
    df_dashboard: pd.DataFrame,
    df_ams: pd.DataFrame,
    anos: Iterable[int],
) -> tuple[pd.DataFrame, dict[str, int]]:
    dashboard = df_dashboard.copy()
    dashboard["Número de Série"] = _serie_canonica(dashboard)

    if "_presente_parque" in dashboard.columns:
        presente_parque = dashboard["_presente_parque"].fillna(False).astype(bool)
    else:
        # Em bases antigas sem marcador, considera o dataframe principal como parque.
        presente_parque = dashboard["Número de Série"].notna()

    parque = dashboard.loc[presente_parque].dropna(subset=["Número de Série"])
    parque_series = set(parque["Número de Série"])

    ams = preparar_ams_periodo(df_ams, anos)
    ams_series = set(ams["Número de Série"].dropna())
    union = sorted(parque_series | ams_series)

    rows = []
    parque_modelos = (
        parque.drop_duplicates("Número de Série")
        .set_index("Número de Série")
        .get("Modelo", pd.Series(dtype="object"))
    )
    ams_modelos = (
        ams.drop_duplicates("Número de Série", keep="last")
        .set_index("Número de Série")
        .get("Modelo", pd.Series(dtype="object"))
    )

    for serie in union:
        in_parque = serie in parque_series
        in_ams = serie in ams_series
        if in_parque and in_ams:
            status = "Presente nas duas fontes"
        elif in_parque:
            status = "Somente no parque atual"
        else:
            status = "Somente no AMS do período"
        modelo = parque_modelos.get(serie, pd.NA)
        if pd.isna(modelo) or not str(modelo).strip():
            modelo = ams_modelos.get(serie, "Não identificado")
        rows.append(
            {
                "Número de Série": serie,
                "Modelo": modelo,
                "Status de conciliação": status,
            }
        )

    details = pd.DataFrame(rows)
    summary = {
        "parque_atual": len(parque_series),
        "ams_periodo": len(ams_series),
        "presentes_duas": len(parque_series & ams_series),
        "somente_parque": len(parque_series - ams_series),
        "somente_ams": len(ams_series - parque_series),
        "universo_conciliado": len(parque_series | ams_series),
    }
    return details, summary
