import pandas as pd
import streamlit as st

from dashtoolsrecomendation import auth
from dashtoolsrecomendation.database.database import get_collection_normal_itens

def show():
    if not auth.has_role("adm"):
        st.error(
            "Você não tem permissão para acessar esta página.",
            icon=":material/block:",
        )
        st.stop()

    if "df_descricoes_not_normalizer" not in st.session_state:
        st.info("Não existem itens pendentes de normalização.")
        return

    col = get_collection_normal_itens()

    with st.container(border=True):
        st.subheader(":material/folder: Dados Referência")
        st.write("Conteúdo disponível somente para usuários administradores.")
        
        with st.expander('Itens cadastrados'):
            df_normal_itens = pd.DataFrame(col.find().to_list())
            df_normal_itens_unicos = df_normal_itens[['Descrição', 'Tipo', 'Linha', 'Modelo']].drop_duplicates().dropna().reset_index(drop=True)
            df_normal_itens_unicos['Descrição'] = df_normal_itens_unicos['Descrição'].astype('string')
            df_normal_itens_unicos.sort_values(by='Descrição', ascending=True, inplace=True)
            st.dataframe(df_normal_itens_unicos)

    df_not_normalizer = st.session_state.df_descricoes_not_normalizer
    df_not_normalizer['Tipo'] = ''
    df_not_normalizer['Linha'] = ''
    df_not_normalizer['Modelo'] = ''

    df_not_normalizer = df_not_normalizer[['Descrição', 'Tipo', 'Linha', 'Modelo']]
    df_not_normalizer.drop_duplicates(inplace=True)

    df_editado = st.data_editor(
        df_not_normalizer,
        key='edited_itens',
        width='stretch'
    )

    if st.button('Salvar', type="primary"):
        editados = st.session_state['edited_itens']['edited_rows']

        itens_to_mongo = []

        for row_idx in editados.keys():
            row_idx = int(row_idx)

            item = df_editado.iloc[row_idx].to_dict()

            itens_to_mongo.append(item)

        if not itens_to_mongo:
            st.info("Nenhuma alteração para salvar.")
            return

        col.insert_many(itens_to_mongo)
        st.success('Dados inseridos com sucesso!')
