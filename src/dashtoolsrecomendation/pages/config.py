import streamlit as st

from dashtoolsrecomendation.database import (
    database
)

def show():
    st.subheader('Configurações', divider='red')

    # db = get_database()
    collection_config = database.get_collection_config()

    with st.container(border=True):

        config = collection_config.find().to_list()[0]

        default_show_relacao_idade_reparos = config['relacaoReparosIdade']

        show_relacao_idade_reparos = st.toggle(
            'Exibir Gráfico Relação % Reparos Idade',
            value=default_show_relacao_idade_reparos
        )

        if show_relacao_idade_reparos:
            collection_config.update_one(
                {},
                {'$set': {
                    'relacaoReparosIdade': True 
                }}
            )
        else:
            collection_config.update_one(
                {},
                {'$set': {
                    'relacaoReparosIdade': False 
                }}
            )
