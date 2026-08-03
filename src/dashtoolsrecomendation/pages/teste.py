import pandas as pd
import streamlit as st

from dashtoolsrecomendation import auth

from dashtoolsrecomendation.utils import (
    download_xlsx
)

def _percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.empty or numeric.nunique(dropna=False) <= 1:
        return pd.Series(0.0, index=series.index)
    return numeric.rank(method="average", pct=True).fillna(0)



def show():
    if not auth.has_role("adm"):
        st.error(
            "Você não tem permissão para acessar esta página.",
            icon=":material/block:",
        )
        st.stop()

    with st.container(border=True):
        st.subheader(":material/folder: Área de testes")
        st.write("Conteúdo disponível somente para usuários administradores.")

    st.divider()

    columns = list(st.session_state.base.columns)
    columns.sort(key=str.lower)

    st.write(columns)


    df = st.session_state.base[[
        "Modelo",
        "Número de Série",
        "Data de compra",
        "Idade atual",
        "Reparações no período",
        "Anos observados",
        "Reparações por ano observado",
        "Anos com reparação",
        "Recorrência",
        "Custo líquido",
        "Custo com impostos",
    ]]

    result = df.copy()

    result["Percentil idade"] = _percentile_score(
        result["Idade atual"]
    )

    result["Percentil frequência"] = _percentile_score(
        result["Reparações por ano observado"]
    )

    result["Percentil custo"] = _percentile_score(
        result["Custo com impostos"]
    )

    result["Percentil recorrência"] = _percentile_score(
        result["Recorrência"]
    )

    # result = result[result['Número de Série'] == '116879']

    st.dataframe(result)
    download_xlsx.download(result, 'bar', 'calculo_percentils')

    serie_idade = result["Idade atual"].to_frame()

    st.write(serie_idade)
    download_xlsx.download(serie_idade, 'foo', 'serie_idades')
