from types import SimpleNamespace
from unittest.mock import patch

from dashtoolsrecomendation import auth


def _streamlit_stub(*, users, session_state=None):
    return SimpleNamespace(
        secrets={"auth": {"users": users}},
        session_state=session_state if session_state is not None else {},
    )


def test_authenticated_identity_includes_configured_name():
    streamlit_stub = _streamlit_stub(
        users=[
            {
                "user": "login.teste",
                "password": "segredo",
                "name": "Nome Completo",
                "role": "adm",
            }
        ]
    )

    with patch.object(auth, "st", streamlit_stub):
        identity = auth._get_authenticated_identity(
            "login.teste", "segredo"
        )

    assert identity == ("adm", "Nome Completo")


def test_authenticated_name_populates_existing_session_from_secrets():
    session_state = {
        auth.AUTHENTICATED_KEY: True,
        auth.AUTHENTICATED_USER_KEY: "login.teste",
        auth.AUTHENTICATED_ROLE_KEY: "user",
    }
    streamlit_stub = _streamlit_stub(
        users=[
            {
                "user": "login.teste",
                "password": "segredo",
                "name": "Nome Completo",
                "role": "user",
            }
        ],
        session_state=session_state,
    )

    with patch.object(auth, "st", streamlit_stub):
        name = auth.get_authenticated_name()

    assert name == "Nome Completo"
    assert (
        session_state[auth.AUTHENTICATED_NAME_KEY] == "Nome Completo"
    )


def test_authenticated_name_falls_back_to_user_when_name_is_absent():
    streamlit_stub = _streamlit_stub(
        users=[
            {
                "user": "login.teste",
                "password": "segredo",
                "role": "user",
            }
        ]
    )

    with patch.object(auth, "st", streamlit_stub):
        identity = auth._get_authenticated_identity(
            "login.teste", "segredo"
        )

    assert identity == ("user", "login.teste")
