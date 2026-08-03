from __future__ import annotations

import re
from typing import Literal, overload

import pandas as pd
import streamlit as st


def _sorted_values(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []

    values = (
        df[column]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    def sort_key(value: str) -> tuple[str, int, str]:
        prefix_match = re.search(r"[A-Za-z]+(?:-[A-Za-z]+)?", value)
        number_match = re.search(r"\d+", value)
        prefix = prefix_match.group(0) if prefix_match else ""
        number = int(number_match.group(0)) if number_match else 999999
        return prefix.casefold(), number, value.casefold()

    return sorted((str(value) for value in values), key=sort_key)


@overload
def create_filter(
    df: pd.DataFrame,
    coluna: str,
    tilte: str,
    sidebar: bool = True,
    type: Literal["selectbox"] = "selectbox",
    key: str | None = None,
    default_all: bool = False,
) -> str: ...


@overload
def create_filter(
    df: pd.DataFrame,
    coluna: str,
    tilte: str,
    sidebar: bool = True,
    type: Literal["multiselect"] = "multiselect",
    key: str | None = None,
    default_all: bool = False,
) -> list[str]: ...


def create_filter(
    df: pd.DataFrame,
    coluna: str,
    tilte: str,
    sidebar: bool = True,
    type: Literal["selectbox", "multiselect"] = "selectbox",
    key: str | None = None,
    default_all: bool = False,
) -> str | list[str]:
    """Cria um filtro cujo valor vazio significa ausência de restrição.

    ``default_all`` foi mantido para compatibilidade com as chamadas existentes.
    Selecionar todos os itens e não selecionar nenhum item têm a mesma semântica,
    portanto o estado canônico de "Todos" é sempre vazio.
    """
    key = key or f"filter_{coluna}_{type}"
    del default_all

    # Remove a segunda fonte de estado usada pela implementação anterior.
    st.session_state.pop(f"{key}_persist", None)

    if coluna not in df.columns:
        st.session_state.pop(key, None)
        return [] if type == "multiselect" else ""

    options = _sorted_values(df, coluna)
    widget_area = st.sidebar if sidebar else st

    if type == "selectbox":
        select_options = [""] + options
        if st.session_state.get(key) not in select_options:
            st.session_state[key] = ""

        return widget_area.selectbox(
            tilte,
            select_options,
            key=key,
            format_func=lambda value: "Todos (sem restrição)" if value == "" else value,
        )

    current = st.session_state.get(key, [])
    if not isinstance(current, list):
        current = []
    current = [str(item) for item in current if str(item) in options]

    # Normaliza também seleções explícitas de todas as opções para "sem restrição".
    if options and set(current) == set(options):
        current = []
    st.session_state[key] = current

    return widget_area.multiselect(
        tilte,
        options,
        key=key,
        placeholder="Todos (sem restrição)",
    )
