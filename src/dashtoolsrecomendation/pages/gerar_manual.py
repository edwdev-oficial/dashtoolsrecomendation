import streamlit as st

from dashtoolsrecomendation.reports import generator_manual

def show():
    st.subheader('Gerar Manual', divider='red')

    st.download_button(
        label="Baixar manual em PDF",
        data=generator_manual.generate_manual_bytes,
        file_name=generator_manual.OUTPUT_FILENAME,
        mime="application/pdf",
        type="primary",
        icon=":material/download:",
        on_click="ignore",
    )    