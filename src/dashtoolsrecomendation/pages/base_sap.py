import streamlit as st

from dashtoolsrecomendation.components import (
    create_filter
)

from dashtoolsrecomendation.utils import(
    df_config
)

def show():
    st.subheader('', divider='red')

    keys = st.session_state.keys()
    keys = [k for k in keys if str(k).startswith('df')]

    st.write(keys)

    serie = st.text_input('Nº de Série')

    df_pq_row = st.session_state.get("df_pq_row").copy()
    if serie:
        df_pq_row = df_pq_row[df_pq_row['Número de série'] == serie]
    st.write('df_pq_row')
    st.dataframe(df_pq_row)

    df_sap_group = st.session_state.get('df_sap_group').copy()
    if serie:
        df_sap_group = df_sap_group[df_sap_group['Serial Number'] == serie]
    st.write('df_sap_group')
    st.dataframe(df_sap_group)
    df_config.footer_df(
        df_sap_group,
        'registros localizados'
    )

    df_sap_split = st.session_state.get('df_sap_split').copy()
    if serie:
        df_sap_split = df_sap_split[df_sap_split['(n) Serial Number'] == serie]
    st.write('df_sap_split')
    st.dataframe(df_sap_split)
    df_config.footer_df(
        df_sap_split,
        'registros localizados'
    )