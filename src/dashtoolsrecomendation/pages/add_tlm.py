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


    st.subheader('Novo modo de noramlização', divider='red')

    df_normal_itens = pd.DataFrame(col.find().to_list())
    df_normal_itens.drop(['_id'], axis=1, inplace=True)
    df_normal_itens['modelo_normalizer'] = (
        df_normal_itens['Modelo']
        .astype('string')
        .str.upper()
        .str.strip()
        .str.replace(' ', '')
        .str.replace('-', '')
    )
    df_normal_itens.rename(columns={'Descrição': 'r_descricao', 'Tipo': 'r_tipo', 'Linha': 'r_linha', 'Modelo': 'r_modelo'}, inplace=True)
    st.dataframe(df_normal_itens)



    df_not_normalizer['decricao_normalizer'] = (
        df_not_normalizer["Descrição"]
        .astype("string")
        .str.upper()
        .str.strip()
        .str.replace(" ", "", regex=False)
        .str.replace("-", "", regex=False)
        .str.replace("AVR", "")
    )

    st.dataframe(df_not_normalizer)

    df_merge = pd.merge(
        df_not_normalizer,
        df_normal_itens,
        how='inner',
        left_on='decricao_normalizer',
        right_on='modelo_normalizer'
    )

    df_merge['Tipo'] = df_merge['r_tipo']
    df_merge['Linha'] = df_merge['r_linha']
    df_merge['Modelo'] = df_merge['r_modelo']

    df_merge = df_merge[['Descrição', 'Tipo', 'Linha', 'Modelo']]

    df_merge = df_merge.drop_duplicates()
    df_merge = df_merge.reset_index(drop=True)

    st.write('Se existirem dados neste df já podem ser normalizados')
    st.dataframe(df_merge)

    dictionary = df_merge.to_dict(orient='records')

    # st.write(dictionary)

    if st.button('Salvar este'):
        col.insert_many(dictionary)
        st.success('Dados salvos com sucesso')

    st.subheader('Terceiro método', divider='red')

    df_not_normalizer.drop(['decricao_normalizer'], axis=1, inplace=True)
    data_filter = st.text_input('Descrição')


    if data_filter:
        df_not_normalizer = df_not_normalizer[df_not_normalizer['Descrição'].str.startswith(data_filter)]    

    options_descriptions = df_not_normalizer['Descrição']
    descricoes = st.multiselect('Descrições', options_descriptions)
    if descricoes:
        df_not_normalizer = df_not_normalizer[df_not_normalizer['Descrição'].isin(descricoes)]    

    col1, col2, col3 = st.columns(3)

    with col1:
        tipo = st.selectbox('Tipo', ['', 'Ferramenta', 'Acessório'])
    with col2:
        linhas = ['']
        values = sorted(list(df_normal_itens['r_linha'].unique()))
        linhas.extend(values)
        linha = st.selectbox('Linha', linhas)
    with col3:
        modelo = st.text_input('Modelo')
        
    if tipo and linha:
        df_not_normalizer['Tipo'] = tipo
        df_not_normalizer['Linha'] = linha
        df_not_normalizer['Modelo'] = df_not_normalizer['Descrição']

    if modelo:
        df_not_normalizer['Modelo'] = modelo

    st.dataframe(df_not_normalizer)
    if data_filter and tipo and linha:
        if st.button('Salvar3'):
            dictionary = df_not_normalizer.to_dict(orient='records')
            col.insert_many(dictionary)
            st.success('Dados inseridos com sucesso')
            st.rerun()


