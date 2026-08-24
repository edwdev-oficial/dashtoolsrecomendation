from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from pypdf import PdfReader

from dashtoolsrecomendation.reports import (
    PdfReportConfig,
    gerar_manual_metodologia_pdf,
    gerar_relatorio_pdf,
)
from dashtoolsrecomendation.reports import generator, generator_manual


def _base_sintetica(quantidade: int = 35) -> pd.DataFrame:
    rng = np.random.default_rng(123)
    return pd.DataFrame(
        {
            "Número de Série": [str(1000 + index) for index in range(quantidade)],
            "Modelo": rng.choice(["TE-700", "TE-500", "TE-3 ML"], quantidade),
            "Grupo": rng.choice(["Comprado", "Frota"], quantidade),
            "Razão Social": ["Cliente Teste"] * quantidade,
            "Idade atual": rng.uniform(0.5, 8.5, quantidade),
            "Reparações no período": rng.integers(0, 8, quantidade),
            "Anos com reparação": rng.integers(0, 5, quantidade),
            "Custo com impostos": rng.uniform(0, 10_000, quantidade),
            "Índice de prioridade": np.linspace(99, 20, quantidade),
            "Recomendação": ["Troca prioritária"] * 15
            + ["Planejar renovação"] * 10
            + ["Manter"] * 10,
            "Motivo principal": ["Alta frequência e alto custo"] * quantidade,
            "Máquina reparada": [True] * 28 + [False] * 7,
            "Pago pelo cliente com impostos": rng.uniform(0, 4_000, quantidade),
            "Valor absorvido com impostos": rng.uniform(0, 6_000, quantidade),
        }
    )


def _ams_sintetico(base: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ano in range(2022, 2027):
        for index, serie in enumerate(base["Número de Série"]):
            rows.append(
                {
                    "Número de Série": serie,
                    "ano_reparo": ano,
                    "# Reparos": index % 3,
                    "# Notif.": 1,
                    "Custo de Reparos": float((index + 1) * 25),
                    "Pagado pelo Cliente": 0.0,
                    "Economia": 0.0,
                    "Modelo": base.loc[index, "Modelo"],
                }
            )
    return pd.DataFrame(rows)


def test_gerar_relatorio_pdf_retorna_pdf_valido() -> None:
    base = _base_sintetica()
    config = PdfReportConfig(
        cliente="Cliente Teste",
        responsavel="Responsável Teste",
        cargo_responsavel="Rental Hilti do Brasil",
        data_emissao=date(2026, 7, 28),
        data_inicio=date(2022, 1, 1),
        data_fim=date(2026, 7, 24),
        idade_corte=5,
        fator_impostos=1.4,
        quantidade_cenario=15,
        incluir_base_completa=True,
    )

    pdf = gerar_relatorio_pdf(
        base=base,
        df_ams=_ams_sintetico(base),
        anos=[2022, 2023, 2024, 2025, 2026],
        config=config,
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 25_000
    assert b"%%EOF" in pdf[-2_048:]
    texto = "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(pdf)).pages
    )
    assert "Idade (anos)" in texto
    assert "Idade Atual (anos)" not in texto
    assert "Anos c/ reparo" in texto
    assert "Custo c/ impostos" in texto


def test_config_rejeita_quantidade_invalida() -> None:
    config = PdfReportConfig(
        cliente="Cliente Teste",
        responsavel="Teste",
        cargo_responsavel="Teste",
        data_emissao=date(2026, 7, 28),
        data_inicio=date(2022, 1, 1),
        data_fim=date(2026, 7, 24),
        idade_corte=5,
        fator_impostos=1.4,
        quantidade_cenario=0,
    )

    try:
        config.validate()
    except ValueError as error:
        assert "ao menos uma máquina" in str(error)
    else:
        raise AssertionError("Era esperado ValueError para cenário vazio.")


def _quantidade_paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf))


def test_alinhamentos_das_colunas_padronizadas_do_pdf() -> None:
    headers = [
        "Série",
        "Idade (anos)",
        "Reparações",
        "Anos c/ reparo",
        "Custo c/ impostos",
        "Índice",
    ]

    assert generator._pdf_table_column_alignments(headers) == [
        "LEFT",
        "CENTER",
        "CENTER",
        "CENTER",
        "RIGHT",
        "CENTER",
    ]


def test_manual_metodologia_e_opcional_e_acrescenta_anexo_e() -> None:
    base = _base_sintetica()
    config = PdfReportConfig(
        cliente="Cliente Teste",
        responsavel="Responsável Teste",
        cargo_responsavel="Rental Hilti do Brasil",
        data_emissao=date(2026, 8, 16),
        data_inicio=date(2022, 1, 1),
        data_fim=date(2026, 8, 16),
        idade_corte=5,
        fator_impostos=1.4,
        quantidade_cenario=10,
        incluir_base_completa=False,
        incluir_manual_metodologia=False,
    )

    sem_manual = gerar_relatorio_pdf(
        base=base,
        df_ams=_ams_sintetico(base),
        anos=[2022, 2023, 2024, 2025, 2026],
        config=config,
    )
    com_manual = gerar_relatorio_pdf(
        base=base,
        df_ams=_ams_sintetico(base),
        anos=[2022, 2023, 2024, 2025, 2026],
        config=replace(config, incluir_manual_metodologia=True),
    )

    assert _quantidade_paginas(com_manual) == _quantidade_paginas(sem_manual) + 10
    assert len(com_manual) > len(sem_manual)


def test_gerar_manual_metodologia_pdf_retorna_dez_paginas_validas() -> None:
    config = PdfReportConfig(
        cliente="Cliente Teste",
        responsavel="Responsável Teste",
        cargo_responsavel="Rental Hilti do Brasil",
        data_emissao=date(2026, 8, 16),
        data_inicio=date(2022, 1, 1),
        data_fim=date(2026, 8, 16),
        idade_corte=5,
        fator_impostos=1.4,
        quantidade_cenario=1,
    )

    pdf = gerar_manual_metodologia_pdf(config=config)

    assert pdf.startswith(b"%PDF-")
    assert _quantidade_paginas(pdf) == 10
    assert b"%%EOF" in pdf[-2_048:]

    gerado = PdfReader(BytesIO(pdf))
    assert len(gerado.pages) == 10
    assert sum(len(list(page.images)) for page in gerado.pages) >= 1
    texto = "\n".join(page.extract_text() for page in gerado.pages)
    assert "MANUAL DE METODOLOGIA" in texto
    assert "EXEMPLOS DE INTERPRETAÇÃO" in texto
    assert "Idade (anos)" in texto
    assert "Idade Atual (anos)" not in texto


def test_manual_metodologia_delega_para_o_gerador_em_codigo(monkeypatch) -> None:
    esperado = b"%PDF-manual-gerado-em-codigo"
    monkeypatch.setattr(generator_manual, "generate_manual_bytes", lambda: esperado)
    config = PdfReportConfig(
        cliente="Cliente Teste",
        responsavel="Responsável Teste",
        cargo_responsavel="Rental Hilti do Brasil",
        data_emissao=date(2026, 8, 16),
        data_inicio=date(2022, 1, 1),
        data_fim=date(2026, 8, 16),
        idade_corte=5,
        fator_impostos=1.4,
        quantidade_cenario=1,
    )

    assert gerar_manual_metodologia_pdf(config=config) == esperado
