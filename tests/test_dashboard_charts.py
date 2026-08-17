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
    assert figure.layout.margin.t == 72
    assert figure.layout.margin.b == 45
    assert figure.layout.height == 455
    assert figure.layout.legend.title.side == "left"
    assert figure.layout.legend.y == -0.30
    assert figure.layout.legend.yanchor == "top"


def test_pareto_separa_titulo_do_eixo_x_da_legenda() -> None:
    base = pd.DataFrame(
        {
            "Posição": [1, 2],
            "Custo com impostos": [1_000.0, 500.0],
            "Percentual acumulado": [2 / 3, 1.0],
            "Número de Série": ["1001", "1002"],
            "Modelo": ["TE 1", "TE 2"],
            "Índice de prioridade": [90.0, 70.0],
            "Reparações no período": [4, 2],
            "Recomendação": ["Troca prioritária", "Planejar renovação"],
        }
    )

    figure = dashboard_charts.grafico_pareto_custo_maquina(base)

    assert figure.layout.legend.y == -0.30
    assert figure.layout.legend.yanchor == "top"
    assert figure.layout.margin.t == 82
    assert figure.layout.margin.b == 60
    assert figure.layout.height == 470
    assert figure.layout.yaxis2.range == (0, 105)


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


def test_custo_manutencoes_por_idade_soma_custos_da_mesma_idade() -> None:
    base = pd.DataFrame(
        {
            "Idade atual": [2.2, 2.9, 5.1],
            "Custo com impostos": [100.0, 250.0, 400.0],
        }
    )

    figure = dashboard_charts.grafico_custo_manutencoes_por_idade(base)
    trace = figure.data[0]

    assert list(trace.x) == [2, 5]
    assert list(trace.y) == [350.0, 400.0]
    assert trace.texttemplate == "R$ %{text:,.0f}"
    assert figure.layout.title.text == "Custo de manutenções por idade"
