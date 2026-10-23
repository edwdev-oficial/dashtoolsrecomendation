from datetime import date
from types import SimpleNamespace

import pandas as pd

from dashtoolsrecomendation.components import dashboard_filters
from dashtoolsrecomendation.components.dashboard_filters import (
    aplicar_escopo_analitico,
    aplicar_selecoes,
    filtrar_termino_contrato,
)


def _fleet() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "Grupo": ["Frota", "Frota", "Comprado", "Comprado", "Frota"],
            "Linha": ["Rompedor", "Serra", "Rompedor", "Furadeira", "Serra"],
            "Modelo": ["A", "B", "A", "C", "C"],
            "Número de Série": ["1001", "1002", "1003", "1004", "1005"],
            "idade_int (a)": [1, 2, 3, 4, 5],
            "Data de Término do Contrato": [
                "2024-01-01",
                "2026-01-01",
                "2020-01-01",
                None,
                None,
            ],
        }
    )


def test_limpar_grupo_restaura_toda_a_base() -> None:
    base = _fleet()

    completo = aplicar_selecoes(base, {"Grupo": ""}, ages=[])
    somente_frota = aplicar_selecoes(base, {"Grupo": "Frota"}, ages=[])
    restaurado = aplicar_selecoes(base, {"Grupo": ""}, ages=[])

    assert len(somente_frota) == 3
    assert restaurado["id"].tolist() == completo["id"].tolist()


def test_multiselect_vazio_significa_sem_restricao() -> None:
    base = _fleet()

    sem_selecao = aplicar_selecoes(base, {"Modelo": []}, ages=[])
    selecao_explicita = aplicar_selecoes(base, {"Modelo": ["A"]}, ages=["3"])

    assert sem_selecao["id"].tolist() == base["id"].tolist()
    assert selecao_explicita["id"].tolist() == [3]


def test_linha_restringe_as_opcoes_disponiveis_de_modelo() -> None:
    base = _fleet()

    contexto_modelo = aplicar_selecoes(base, {"Linha": ["Rompedor"]})

    assert contexto_modelo["Modelo"].drop_duplicates().tolist() == ["A"]


def test_numero_de_serie_pode_filtrar_uma_ou_varias_maquinas() -> None:
    base = _fleet()

    result = aplicar_selecoes(
        base,
        {"Número de Série": ["1002", "1005"]},
    )

    assert result["id"].tolist() == [2, 5]


def test_filtro_de_contrato_afeta_apenas_frota() -> None:
    base = _fleet()

    result = filtrar_termino_contrato(
        base,
        date(2025, 1, 1),
        exact_date=False,
        include_missing=False,
    )

    assert result["id"].tolist() == [1, 3, 4]


def test_filtro_de_contrato_pode_incluir_frota_sem_data() -> None:
    base = _fleet()

    result = filtrar_termino_contrato(
        base,
        date(2025, 1, 1),
        exact_date=False,
        include_missing=True,
    )

    assert result["id"].tolist() == [1, 3, 4, 5]


def test_tipo_nao_reduz_faixa_de_datas_do_filtro_contratual(monkeypatch) -> None:
    base = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "Tipo": ["Ferramenta", "Ferramenta", "AcessÃ³rio"],
            "Grupo": ["Frota", "Frota", "Frota"],
            "Data de TÃ©rmino do Contrato": [
                "2026-01-01",
                "2027-01-01",
                "2025-01-01",
            ],
        }
    )
    captured: dict[str, pd.DataFrame] = {}

    class SidebarStub:
        def markdown(self, *_args, **_kwargs) -> None:
            pass

        def button(self, *_args, **_kwargs) -> bool:
            return False

        def caption(self, *_args, **_kwargs) -> None:
            pass

    streamlit_stub = SimpleNamespace(sidebar=SidebarStub(), session_state={})

    def fake_create_filter(*, coluna, type, **_kwargs):
        if coluna == "Tipo":
            return "Ferramenta"
        return [] if type == "multiselect" else ""

    def capture_contract_options(df, grupo, *, options_df=None, **_kwargs):
        del grupo
        captured["filter"] = options_df.copy()
        return df

    def capture_description(options_df, _grupo):
        captured["description"] = options_df.copy()
        return None

    monkeypatch.setattr(dashboard_filters, "st", streamlit_stub)
    monkeypatch.setattr(
        dashboard_filters.create_filter,
        "create_filter",
        fake_create_filter,
    )
    monkeypatch.setattr(
        dashboard_filters,
        "aplicar_filtro_termino_contrato",
        capture_contract_options,
    )
    monkeypatch.setattr(
        dashboard_filters,
        "_contract_filter_description",
        capture_description,
    )

    result, _ = dashboard_filters.aplicar_filtros(base)

    assert result["id"].tolist() == [1, 2]
    assert captured["filter"]["id"].tolist() == [1, 2, 3]
    assert captured["description"]["id"].tolist() == [1, 2, 3]

def test_escopo_analitico_separa_elegibilidade_de_filtros_visuais() -> None:
    base = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "_presente_parque": [True, True, False, True],
            "Status da Ferramenta": ["Ativo", "Roubado", "Ativo", "Ativo"],
            "Modelo": ["A", "B", "C", "D"],
        }
    )

    padrao = aplicar_escopo_analitico(base)
    ampliado = aplicar_escopo_analitico(
        base,
        include_ams_only=True,
        include_stolen=True,
    )

    assert padrao["id"].tolist() == [1, 4]
    assert ampliado["id"].tolist() == [1, 2, 3, 4]
