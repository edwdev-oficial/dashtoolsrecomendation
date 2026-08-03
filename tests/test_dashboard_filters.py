from datetime import date

import pandas as pd

from dashtoolsrecomendation.components.dashboard_filters import (
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
