from __future__ import annotations

import pandas as pd

from dashtoolsrecomendation.components import dashboard_charts


def test_custo_anual_exibe_rotulos_inteiros_acima_das_barras() -> None:
    annual = pd.DataFrame(
        {
            "Ano": [2025, 2026],
            "Custo realizado": [123_456.78, 234_567.89],
            "Custo projetado": [123_456.78, 234_567.89],
        }
    )

    figure = dashboard_charts.grafico_evolucao_custos(annual)
    realized = figure.data[0]

    assert realized.texttemplate == "%{text}"
    assert realized.textposition == "outside"
    assert realized.cliponaxis is False
    assert list(realized.text) == ["R$ 123.457", "R$ 234.568"]


def test_custo_anual_rotula_total_projetado_sem_duplicar_realizado() -> None:
    annual = pd.DataFrame(
        {
            "Ano": [2025, 2026],
            "Custo realizado": [100_000.0, 120_000.0],
            "Custo projetado": [100_000.0, 180_000.0],
        }
    )

    figure = dashboard_charts.grafico_evolucao_custos(annual)
    realized, projected = figure.data

    assert list(realized.text) == ["R$ 100.000", None]
    assert list(projected.text) == [None, "R$ 180.000"]
    assert projected.texttemplate == "%{text}"
