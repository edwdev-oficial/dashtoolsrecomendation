from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

import pandas as pd
import streamlit as st

from dashtoolsrecomendation.components import create_filter


FilterValue: TypeAlias = str | list[str]


@dataclass(frozen=True)
class FilterSpec:
    column: str
    title: str
    widget_type: Literal["selectbox", "multiselect"]
    key: str


FILTERS = [
    FilterSpec("cliente", "Cliente", "selectbox", "filtro_cliente"),
    FilterSpec("UF", "UF", "selectbox", "filtro_uf"),
    FilterSpec("Grupo", "Grupo", "selectbox", "filtro_grupo"),
    FilterSpec("Status da Ferramenta", "Status", "multiselect", "filtro_status"),
    FilterSpec("Tipo", "Tipo", "selectbox", "filtro_tipo"),
    FilterSpec("Linha", "Linha", "multiselect", "filtro_linha"),
    FilterSpec("Modelo", "Modelo", "multiselect", "filtro_modelo"),
    FilterSpec("reparada", "Reparadas", "selectbox", "filtro_reparadas"),
    FilterSpec("Garantia", "Garantia", "selectbox", "filtro_garantia"),
    FilterSpec(
        "Reparo Rejeitado",
        "Reparo Rejeitado",
        "selectbox",
        "filtro_reparo_rejeitado",
    ),
]

AGE_COLUMN = "idade_int (a)"
AGE_FILTER_KEY = "filter_idade"
INCLUDE_AMS_KEY = "filtro_incluir_somente_ams"
INCLUDE_STOLEN_KEY = "filtro_incluir_baixadas_bo"
CONTRACT_KEY_PREFIX = "filtro_termino_contrato"


def limpar_estado_filtros() -> None:
    """Remove todo o estado dos filtros; os widgets voltam aos padrões no rerun."""
    widget_keys = [spec.key for spec in FILTERS] + [
        AGE_FILTER_KEY,
        INCLUDE_AMS_KEY,
        INCLUDE_STOLEN_KEY,
        f"{CONTRACT_KEY_PREFIX}_incluir_sem_data",
        f"{CONTRACT_KEY_PREFIX}_data_exata",
        f"{CONTRACT_KEY_PREFIX}_date_input",
    ]
    for key in widget_keys:
        st.session_state.pop(key, None)
        st.session_state.pop(f"{key}_persist", None)


def aplicar_selecoes(
    df: pd.DataFrame,
    selections: dict[str, FilterValue],
    ages: list[str] | None = None,
) -> pd.DataFrame:
    """Aplica seleções ao conjunto original; vazio significa sem restrição."""
    result = df.copy()
    specs_by_column = {spec.column: spec for spec in FILTERS}

    for column, selected in selections.items():
        if not selected or column not in result.columns:
            continue

        normalized = result[column].astype("string").str.strip()
        spec = specs_by_column.get(column)
        if spec is not None and spec.widget_type == "multiselect":
            selected_values = selected if isinstance(selected, list) else [selected]
            result = result[normalized.isin(selected_values)]
        else:
            selected_value = selected[0] if isinstance(selected, list) else selected
            result = result[normalized.eq(selected_value)]

    if ages and AGE_COLUMN in result.columns:
        result = result[result[AGE_COLUMN].astype("string").str.strip().isin(ages)]

    return result


def filtrar_termino_contrato(
    df: pd.DataFrame,
    selected_date: date | pd.Timestamp,
    *,
    exact_date: bool,
    include_missing: bool,
    column: str = "Data de Término do Contrato",
) -> pd.DataFrame:
    """Filtra datas apenas para Frota e sempre preserva os demais grupos."""
    if column not in df.columns or "Grupo" not in df.columns:
        return df.copy()

    result = df.copy()
    dates = pd.to_datetime(result[column], errors="coerce").dt.normalize()
    frota = (
        result["Grupo"].astype("string").str.strip().eq("Frota").fillna(False)
    )
    cutoff = pd.Timestamp(selected_date).normalize()
    contract_match = dates.eq(cutoff) if exact_date else dates.le(cutoff)
    if include_missing:
        contract_match |= dates.isna()

    return result[~frota | (frota & contract_match)]


def aplicar_filtro_termino_contrato(
    df: pd.DataFrame,
    grupo: str,
    *,
    options_df: pd.DataFrame | None = None,
    column: str = "Data de Término do Contrato",
    key_prefix: str = CONTRACT_KEY_PREFIX,
) -> pd.DataFrame:
    if grupo == "Comprado" or column not in df.columns or "Grupo" not in df.columns:
        return df

    option_source = options_df if options_df is not None else df
    if column not in option_source.columns or "Grupo" not in option_source.columns:
        return df

    option_groups = option_source["Grupo"].astype("string").str.strip()
    frota_dates = pd.to_datetime(
        option_source.loc[option_groups.eq("Frota"), column], errors="coerce"
    ).dropna()
    if frota_dates.empty:
        return df

    with st.sidebar.container(border=True):
        st.markdown("### Filtro término contrato G.F.")
        include_missing_key = f"{key_prefix}_incluir_sem_data"
        exact_date_key = f"{key_prefix}_data_exata"
        date_input_key = f"{key_prefix}_date_input"

        st.session_state.setdefault(include_missing_key, True)
        st.session_state.setdefault(exact_date_key, False)
        include_missing = st.checkbox(
            "Incluir registros sem data", key=include_missing_key
        )
        exact_date = st.toggle("Data exata", key=exact_date_key)

        min_date = frota_dates.min().date()
        max_date = frota_dates.max().date()
        default_date = (
            (pd.Timestamp.now() + pd.offsets.MonthEnd(0)).date()
            if exact_date
            else max_date
        )
        default_date = min(max(default_date, min_date), max_date)

        stored_date = st.session_state.get(date_input_key, default_date)
        if not isinstance(stored_date, date):
            stored_date = default_date
        st.session_state[date_input_key] = min(max(stored_date, min_date), max_date)

        selected_date = st.date_input(
            f"Término Contrato G.F. {'em:' if exact_date else 'até:'}",
            min_value=min_date,
            max_value=max_date,
            key=date_input_key,
        )

    return filtrar_termino_contrato(
        df,
        selected_date,
        exact_date=exact_date,
        include_missing=include_missing,
        column=column,
    )


def _describe_selection(title: str, selected: FilterValue) -> str | None:
    if not selected:
        return None
    if isinstance(selected, list):
        display = ", ".join(selected[:3])
        if len(selected) > 3:
            display += f" +{len(selected) - 3}"
        return f"{title}: {display}"
    return f"{title}: {selected}"


def _contract_filter_description(options_df: pd.DataFrame, grupo: str) -> str | None:
    if grupo == "Comprado":
        return None

    include_missing = st.session_state.get(
        f"{CONTRACT_KEY_PREFIX}_incluir_sem_data", True
    )
    exact_date = st.session_state.get(f"{CONTRACT_KEY_PREFIX}_data_exata", False)
    selected_date = st.session_state.get(f"{CONTRACT_KEY_PREFIX}_date_input")
    if selected_date is None:
        return None

    groups = options_df.get("Grupo")
    dates = options_df.get("Data de Término do Contrato")
    if groups is None or dates is None:
        return None
    valid_dates = pd.to_datetime(
        dates[groups.astype("string").str.strip().eq("Frota")], errors="coerce"
    ).dropna()
    if valid_dates.empty:
        return None

    selected = pd.Timestamp(selected_date).date()
    is_effective = bool(exact_date or not include_missing or selected < valid_dates.max().date())
    if not is_effective:
        return None
    mode = "em" if exact_date else "até"
    suffix = ", sem datas vazias" if not include_missing else ""
    return f"Contrato G.F. {mode} {selected:%d/%m/%Y}{suffix}"


def _show_active_filters(descriptions: list[str]) -> None:
    st.sidebar.markdown("#### Filtros ativos")
    if descriptions:
        st.sidebar.caption(" · ".join(descriptions))
    else:
        st.sidebar.caption("Nenhum — exibindo todos os registros elegíveis.")


def aplicar_filtros(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    st.sidebar.markdown("### Filtros do parque")
    st.sidebar.button(
        "Limpar filtros",
        key="limpar_filtros_dashboard",
        icon=":material/filter_alt_off:",
        width="stretch",
        on_click=limpar_estado_filtros,
    )

    options_base = df.copy()
    descriptions: list[str] = []

    if "_presente_parque" in options_base.columns and options_base["_presente_parque"].any():
        include_ams_only = st.sidebar.toggle(
            "Incluir registros somente do AMS",
            value=False,
            key=INCLUDE_AMS_KEY,
            help=(
                "Por padrão, os indicadores usam apenas o parque atual. "
                "Ative para auditar máquinas que aparecem somente no histórico AMS."
            ),
        )
        if not include_ams_only:
            options_base = options_base[options_base["_presente_parque"].fillna(False)]
        else:
            descriptions.append("Registros somente do AMS incluídos")

    if "Status da Ferramenta" in options_base.columns:
        include_stolen = st.sidebar.toggle(
            "Incluir baixadas por B.O.", value=False, key=INCLUDE_STOLEN_KEY
        )
        if not include_stolen:
            options_base = options_base[options_base["Status da Ferramenta"] != "Roubado"]
        else:
            descriptions.append("Baixadas por B.O. incluídas")

    selections: dict[str, FilterValue] = {}
    cascading_options = options_base
    for spec in FILTERS:
        selected = create_filter.create_filter(
            df=cascading_options,
            coluna=spec.column,
            tilte=spec.title,
            sidebar=True,
            type=spec.widget_type,
            key=spec.key,
        )
        selections[spec.column] = selected
        description = _describe_selection(spec.title, selected)
        if description:
            descriptions.append(description)
        cascading_options = aplicar_selecoes(
            cascading_options,
            {spec.column: selected},
        )

    ages = create_filter.create_filter(
        df=cascading_options,
        coluna=AGE_COLUMN,
        tilte="Idade",
        sidebar=True,
        type="multiselect",
        key=AGE_FILTER_KEY,
    )
    age_description = _describe_selection("Idade", ages)
    if age_description:
        descriptions.append(age_description)

    result = aplicar_selecoes(options_base, selections, ages)
    grupo = selections.get("Grupo", "")
    grupo_value = grupo if isinstance(grupo, str) else ""
    result = aplicar_filtro_termino_contrato(
        result,
        grupo=grupo_value,
        options_df=result,
    )

    contract_description = _contract_filter_description(result, grupo_value)
    if contract_description:
        descriptions.append(contract_description)
    _show_active_filters(descriptions)

    modelos = selections.get("Modelo", [])
    return result.reset_index(drop=True), modelos if isinstance(modelos, list) else []
