import streamlit as st

from dashtoolsrecomendation.database import (
    database
)

def config():

    collection_config = database.get_collection_config()

    st.session_state.config = collection_config.find().to_list()[0]