from __future__ import annotations

import pandas as pd

from dashtoolsrecomendation.components import dashboard_charts


def test_matriz_prioridade_exibe_modelo_no_titulo_e_serie_na_primeira_linha() -> None:
    base = pd.DataFrame(
        {
            "Número de Série": ["1856009"],
            "Modelo": ["TE-700"],
            "Idade atual": [6.8],
            "Reparações no período": [12],
            "Custo com impostos": [10_624.08],
            "Índice de prioridade": [96.6],
            "Recomendação": ["Troca prioritária"],
            "Motivo principal": ["Alta frequência e alto custo"],
        }
    )

    figure = dashboard_charts.grafico_matriz_prioridade(base)
    trace = figure.data[0]

    assert list(trace.hovertext) == ["TE-700"]
    assert trace.customdata[0][0] == "1856009"
    assert trace.hovertemplate.startswith(
        "<b>%{hovertext}</b><br>Nº de série: %{customdata[0]}"
    )


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
