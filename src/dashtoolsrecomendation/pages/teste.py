import streamlit as st

from dashtoolsrecomendation import auth


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
