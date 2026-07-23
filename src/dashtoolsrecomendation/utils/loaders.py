import base64
from pathlib import Path

import pandas as pd
import streamlit as st

DIR_BASE = Path(__file__).parents[1]

def load(name_file: str, file_type: str, sheet_name=0):
    file_path = DIR_BASE / "assets" / f"{name_file}.{file_type}"

    if file_type in {"xlsx", "xls", "xlsm"}:
        return pd.read_excel(file_path, sheet_name=sheet_name)

    if file_type == "css":
        st.html(f"<style>{file_path.read_text(encoding='utf-8')}</style>")
        return None

    if file_type == "base64":
        image_path = DIR_BASE / "assets" / f"{name_file}.png"
        return base64.b64encode(image_path.read_bytes()).decode()

    raise ValueError(f"Tipo de arquivo não suportado: {file_type}")
