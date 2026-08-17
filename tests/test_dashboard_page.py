from __future__ import annotations

import pandas as pd

from dashtoolsrecomendation.pages import dashboard


def test_tabela_adm_expoe_insumos_e_calculos_de_frequencia_e_recorrencia() -> None:
    base = pd.DataFrame(
        {
            "Número de Série": ["1001", "1002"],
            "Modelo": ["TE 1", "TE 2"],
            "Grupo": ["Perfuração", "Corte"],
            "Data de compra": pd.to_datetime(["2022-01-01", "2023-01-01"]),
            "Idade atual": [4.0, 3.0],
            "Percentil idade": [1.0, 0.5],
            "Reparações no período": [4, 1],
            "Anos observados": [4, 2],
            "Reparações por ano observado": [1.0, 0.5],
            "Percentil frequência": [1.0, 0.5],
            "Anos com reparação": [3, 1],
            "Primeiro ano com reparação": [2023, 2025],
            "Último ano com reparação": [2026, 2025],
            "Recorrência": [0.75, 0.5],
            "Percentil recorrência": [1.0, 0.5],
            "Custo com impostos": [5_000.0, 1_000.0],
            "Percentil custo": [1.0, 0.5],
            "Índice de prioridade": [90.0, 40.0],
            "Recomendação": ["Troca prioritária", "Planejar renovação"],
            "Motivo principal": ["Reparações recorrentes", "Acompanhar evolução"],
        }
    )

    result = dashboard._analytical_table_adm(base, limit=1)

    assert len(result) == 1
    assert list(result.columns) == [
        "Número de Série",
        "Modelo",
        "Grupo",
        "Data de compra",
        "Idade atual",
        "Percentil idade",
        "Reparações no período",
        "Anos observados",
        "Reparações por ano observado",
        "Percentil frequência",
        "Anos com reparação",
        "Primeiro ano com reparação",
        "Último ano com reparação",
        "Recorrência",
        "Percentil recorrência",
        "Custo com impostos",
        "Percentil custo",
        "Índice de prioridade",
        "Recomendação",
        "Motivo principal",
    ]
    assert result.iloc[0]["Reparações por ano observado"] == 1.0
    assert result.iloc[0]["Recorrência"] == 0.75
