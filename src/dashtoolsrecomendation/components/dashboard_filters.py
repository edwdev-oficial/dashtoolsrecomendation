from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from dashtoolsrecomendation.components import create_filter


@dataclass(frozen=True)
class FilterSpec:
    column: str
    title: str
    widget_type: str
    key: str
    default_all: bool = False


FILTERS = [
    FilterSpec("cliente", "Cliente", "selectbox", "filtro_cliente"),
    FilterSpec("UF", "UF", "selectbox", "filtro_uf"),
    FilterSpec("Grupo", "Grupo", "selectbox", "filtro_grupo"),
    FilterSpec("Status da Ferramenta", "Status", "multiselect", "filtro_status", True),
    FilterSpec("Tipo", "Tipo", "selectbox", "filtro_tipo"),
    FilterSpec("Linha", "Linha", "multiselect", "filtro_linha", True),
    FilterSpec("Modelo", "Modelo", "multiselect", "filtro_modelo", True),
    FilterSpec("reparada", "Reparadas", "selectbox", "filtro_reparadas"),
    FilterSpec("Garantia", "Garantia", "selectbox", "filtro_garantia"),
    FilterSpec(
        "Reparo Rejeitado",
        "Reparo Rejeitado",
        "selectbox",
        "filtro_reparo_rejeitado",
    ),
]


def aplicar_filtro_termino_contrato(
    df: pd.DataFrame,
    grupo: str,
    column: str = "Data de Término do Contrato",
    key_prefix: str = "filtro_termino_contrato",
) -> pd.DataFrame:
    if grupo == "Comprado":
        return df

    result = df.copy()
    result[column] = pd.to_datetime(result[column], errors="coerce")

    with st.sidebar.container(border=True):
        st.markdown("### Filtro término contrato G.F.")
        valid_dates = result[column].dropna()
        include_missing_key = f"{key_prefix}_incluir_sem_data"
        exact_date_key = f"{key_prefix}_data_exata"
        date_input_key = f"{key_prefix}_date_input"

        st.session_state.setdefault(include_missing_key, True)
        st.session_state.setdefault(exact_date_key, False)

        include_missing = st.checkbox(
            "Incluir registros sem data", key=include_missing_key
        )
        exact_date = st.toggle("Data exata", key=exact_date_key)

        if valid_dates.empty:
            st.warning("Não existem datas válidas em Data de Término do Contrato.")
            return result if include_missing else result[result[column].notna()]

        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        if exact_date:
            filter_label = "em:"
            default_date = (pd.Timestamp.now() + pd.offsets.MonthEnd(0)).date()
        else:
            filter_label = "até:"
            default_date = max_date

        default_date = min(max(default_date, min_date), max_date)
        st.session_state.setdefault(date_input_key, default_date)
        st.session_state[date_input_key] = min(
            max(st.session_state[date_input_key], min_date), max_date
        )

        selected_date = pd.to_datetime(
            st.date_input(
                f"Término Contrato G.F. {filter_label}",
                min_value=min_date,
                max_value=max_date,
                key=date_input_key,
            )
        )
        normalized = result[column].dt.normalize()
        mask = normalized.eq(selected_date) if exact_date else normalized.le(selected_date)
        if include_missing:
            mask |= result[column].isna()

    return result[mask]


def aplicar_filtros(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    st.sidebar.markdown("### Filtros do parque")
    result = df.copy()

    if "_presente_parque" in result.columns and result["_presente_parque"].any():
        incluir_somente_ams = st.sidebar.toggle(
            "Incluir registros somente do AMS",
            value=False,
            help=(
                "Por padrão, os indicadores usam apenas o parque atual. "
                "Ative para auditar máquinas que aparecem somente no histórico AMS."
            ),
        )
        if not incluir_somente_ams:
            result = result[result["_presente_parque"].fillna(False)]

    if (
        "Status da Ferramenta" in result.columns
        and not st.sidebar.toggle("Incluir baixadas por B.O.")
    ):
        result = result[result["Status da Ferramenta"] != "Roubado"]

    selections: dict[str, object] = {}
    for spec in FILTERS:
        selected = create_filter.create_filter(
            df=result,
            coluna=spec.column,
            tilte=spec.title,
            sidebar=True,
            type=spec.widget_type,
            key=spec.key,
            default_all=spec.default_all,
        )
        selections[spec.column] = selected
        if selected:
            if spec.widget_type == "multiselect":
                result = result[result[spec.column].isin(selected)]
            else:
                result = result[result[spec.column] == selected]

    result = aplicar_filtro_termino_contrato(
        result,
        grupo=selections["Grupo"],
    )

    ages = create_filter.create_filter(
        df=result,
        coluna="idade_int (a)",
        tilte="Idade",
        sidebar=True,
        type="multiselect",
        key="filter_idade",
        default_all=True,
    )
    if ages:
        result = result[result["idade_int (a)"].astype(str).isin(ages)]

    return result.reset_index(drop=True), selections["Modelo"]
