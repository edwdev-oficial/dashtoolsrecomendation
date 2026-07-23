from urllib.parse import quote_plus

import streamlit as st
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient

@st.cache_resource
def get_client():
    user = quote_plus(st.secrets["mongo_atlas"]["user"])
    password = quote_plus(st.secrets["mongo_atlas"]["password"])
    uri = f"mongodb+srv://{user}:{password}@sandbox.bfpzo.mongodb.net/"
    return MongoClient(uri, server_api=ServerApi("1"))

def get_database():
    return get_client()["hilti"]

def get_gollection_tlm():
    return get_collection_tlm()


def get_collection_tlm():
    return get_database()["tlm"]

def get_collection_normal_itens():
    return get_database()["normal_itens"]
