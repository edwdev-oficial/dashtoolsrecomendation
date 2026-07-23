import pandas as pd
import streamlit as st


def create_filter(
    df: pd.DataFrame,
    coluna: str,
    tilte: str,
    sidebar: bool = True,
    type: str = "selectbox",
    key: str | None = None,
    default_all: bool = False,
):
    df_use = df.copy()

    if coluna not in df_use.columns:
        return [] if type == "multiselect" else ""

    df_use[coluna] = df_use[coluna].astype("string")

    tem_numero = df_use[coluna].str.contains(r"\d", na=False).any()

    if tem_numero:
        df_use["prefixo"] = (
            df_use[coluna]
            .str.extract(r"([A-Za-z]+(?:-[A-Za-z]+)?)")[0]
            .fillna("")
        )

        df_use["numero"] = pd.to_numeric(
            df_use[coluna].str.extract(r"(\d+)")[0],
            errors="coerce"
        ).fillna(999999)

        df_use = (
            df_use
            .sort_values(["prefixo", "numero", coluna])
            .drop(columns=["prefixo", "numero"])
        )
    else:
        df_use = df_use.sort_values(coluna)

    values = (
        df_use[coluna]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    widget_area = st.sidebar if sidebar else st

    if key is None:
        key = f"filter_{coluna}_{type}"

    state_key = f"{key}_persist"

    # =====================================================
    # SELECTBOX
    # =====================================================
    if type == "selectbox":
        options = [""] + values

        if state_key not in st.session_state:
            st.session_state[state_key] = ""

        # Se o valor salvo não existe mais após filtros anteriores, limpa
        if st.session_state[state_key] not in options:
            st.session_state[state_key] = ""

        index = options.index(st.session_state[state_key])

        valor = widget_area.selectbox(
            tilte,
            options,
            index=index,
            key=key
        )

        st.session_state[state_key] = valor

        return valor

    # =====================================================
    # MULTISELECT
    # =====================================================
    elif type == "multiselect":
        options = values

        if state_key not in st.session_state:
            st.session_state[state_key] = options.copy() if default_all else []

        # Mantém apenas os selecionados que ainda existem após filtros acima
        st.session_state[state_key] = [
            item for item in st.session_state[state_key]
            if item in options
        ]

        valor = widget_area.multiselect(
            tilte,
            options,
            default=st.session_state[state_key],
            key=key
        )

        st.session_state[state_key] = valor

        return valor

    return [] if type == "multiselect" else ""
