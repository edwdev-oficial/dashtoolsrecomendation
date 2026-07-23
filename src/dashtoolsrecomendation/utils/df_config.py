import pandas as pd
import streamlit as st

from dashtoolsrecomendation.utils import formatters

def date_colums_config(cols_data: list):
    return {
        col: st.column_config.DateColumn(format='DD/MM/YYYY')
        for col in cols_data
    }

def sum_column(df:pd.DataFrame, colum:str, type_str:bool=False):
    if type_str:
        return formatters.br_num(df[colum].sum(), 2)
    return df[colum].sum()

def footer_df(df, texto:str=''):
    qtd = f"{len(df):,.0f}".replace(",", ".")
    st.markdown(
        f"""
            <div style='text-align: right; font-style: italic; margin-top: -20px; margin-bottom: 20px'>
                {qtd} {texto}
            </div>
        """,
        unsafe_allow_html=True
    )

def insert_coluna_apos(
        df,
        coluna_referencia,
        nova_coluna,
        valor
):
    posicao = df.columns.get_loc(coluna_referencia) + 1
    df.insert(posicao, nova_coluna, valor)