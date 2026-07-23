import hmac
from pathlib import Path

import streamlit as st


AUTHENTICATED_KEY = "authenticated"
AUTHENTICATED_USER_KEY = "authenticated_user"
AUTHENTICATED_ROLE_KEY = "authenticated_role"
LOGO_PATH = Path(__file__).parent / "assets" / "logoHilti.png"


def is_authenticated() -> bool:
    """Return whether the current browser session is authenticated."""
    return bool(st.session_state.get(AUTHENTICATED_KEY, False))


def _get_authenticated_role(user: str, password: str) -> str | None:
    try:
        configured_users = st.secrets["auth"]["users"]
    except (KeyError, TypeError):
        st.error(
            "As credenciais de acesso não foram configuradas corretamente.",
            icon=":material/error:",
        )
        return None

    for credentials in configured_users:
        user_matches = hmac.compare_digest(user, str(credentials["user"]))
        password_matches = hmac.compare_digest(
            password, str(credentials["password"])
        )
        if user_matches and password_matches:
            return str(credentials["role"])

    return None


def has_role(role: str) -> bool:
    """Return whether the authenticated user has the requested role."""
    return is_authenticated() and hmac.compare_digest(
        str(st.session_state.get(AUTHENTICATED_ROLE_KEY, "")), role
    )


def render_login() -> None:
    """Render the login gate and authenticate the current session."""
    st.session_state.setdefault(AUTHENTICATED_KEY, False)

    with st.container(key="login_layout", horizontal_alignment="center"):
        with st.container(
            key="login_card",
            width=460,
            border=True,
            horizontal_alignment="center",
        ):
            st.image(LOGO_PATH, width=124)
            st.markdown(
                """
                <div class="login-heading">
                    <h1>Bem-vindo</h1>
                    <p>Entre com suas credenciais para acessar o Dash Tools.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("login_form", border=False):
                user = st.text_input(
                    "Usuário",
                    placeholder="Digite seu usuário",
                    icon=":material/person:",
                    autocomplete="username",
                )
                password = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="Digite sua senha",
                    icon=":material/lock:",
                    autocomplete="current-password",
                )
                submitted = st.form_submit_button(
                    "Entrar",
                    type="primary",
                    icon=":material/login:",
                    width="stretch",
                )

            if submitted:
                authenticated_role = _get_authenticated_role(user.strip(), password)
                if authenticated_role is not None:
                    st.session_state[AUTHENTICATED_KEY] = True
                    st.session_state[AUTHENTICATED_USER_KEY] = user.strip()
                    st.session_state[AUTHENTICATED_ROLE_KEY] = authenticated_role
                    st.rerun()

                st.error(
                    "Usuário ou senha inválidos. Verifique os dados e tente novamente.",
                    icon=":material/lock:",
                )

            st.caption(
                ":material/security: Acesso restrito e protegido",
                text_alignment="center",
            )


def logout() -> None:
    """Remove authentication and all user-specific data from the session."""
    st.session_state.clear()
