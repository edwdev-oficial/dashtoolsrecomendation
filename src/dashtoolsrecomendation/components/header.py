from __future__ import annotations

import streamlit as st

from dashtoolsrecomendation.utils import loaders


GRAPH_TITLES = {"Dashboard", "Dashboard 2"}


def render(title: str, subtitle: str) -> None:
    logo_base64 = loaders.load("logoHilti", "base64")
    title_class = "header-title-graph" if title in GRAPH_TITLES else "header-title"
    st.markdown(
        f"""
        <div class="header-container">
            <img src="data:image/png;base64,{logo_base64}">
            <div class="{title_class}">
                {title}
                <p>{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
