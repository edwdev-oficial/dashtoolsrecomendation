import pandas as pd
import streamlit as st
from dashtoolsrecomendation.services import write_xls

def download(df:pd.DataFrame, key:str, name_file:str=''):

    arquivo_excel = write_xls.gerar_excel(df)

    return st.download_button(
        label="Baixar Excel",
        data=arquivo_excel,
        file_name=f'{pd.to_datetime('now').strftime(f"{name_file}_%Y_%m_%d_%H_%M_%S")}.xlsx',
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
        type='primary'
    )