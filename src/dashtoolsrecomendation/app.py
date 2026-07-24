import streamlit as st
from streamlit_option_menu import option_menu

from dashtoolsrecomendation import auth
from dashtoolsrecomendation.utils import loaders
from dashtoolsrecomendation.components import header

from dashtoolsrecomendation.pages import (
    load_data,
    listas,
    dashboard,
    add_tlm,
    config,
    teste,
)

from dashtoolsrecomendation.services import get_config

def main():
    st.set_page_config(
        page_title='Dash Tools',
        page_icon=':material/analytics:',
        layout='wide'
    )

    loaders.load('style', 'css')
    get_config.config()

    if not auth.is_authenticated():
        auth.render_login()
        return

    pages = {
        'Carregar Dados': {
            'icon': 'speedometer',
            'title': 'Carregar dados',
            'subtitle': 'Carregue os dados a serem analisados',
            'show': load_data.show
        },
        'Listas': {
            'icon': 'card-list',
            'title': 'Listas',
            'subtitle': 'Base de dados',
            'show': listas.show            
        },
        'Dashboard': {
            'icon': 'graph-up-arrow',
            'title': 'Dashboard',
            'subtitle': 'Analytic Tools',
            'show': dashboard.show
        }

    }

    if auth.has_role('adm'):
        pages['Add TLM'] = {
            'icon': 'database-add',
            'title': 'Adicionar TLM',
            'subtitle': 'Adicione tipo linha e modelo para os itens listados',
            'show': add_tlm.show
        }
        pages['Config'] = {
            'icon': 'gear',
            'title': 'Configurações',
            'subtitle': 'Configurações administradas',
            'show': config.show
        }
        pages['Teste'] = {
            'icon': 'folder',
            'title': 'Teste',
            'subtitle': 'Área restrita aos administradores',
            'show': teste.show
        }

    with st.sidebar:
        st.caption(
            f":material/account_circle: "
            f"{st.session_state[auth.AUTHENTICATED_USER_KEY]} · "
            f"{st.session_state[auth.AUTHENTICATED_ROLE_KEY]}"
        )
        st.button(
            'Sair',
            icon=':material/logout:',
            key='logout_button',
            on_click=auth.logout,
            width='stretch'
        )

    with st.sidebar.expander('Menu', expanded=True):
        
        selected = option_menu(
            'Páginas',
            list(pages.keys()),
            icons=[page['icon'] for page in pages.values()]
        )

    current_page = pages[selected]
    header.render(current_page['title'], current_page['subtitle'])
    current_page['show']()
