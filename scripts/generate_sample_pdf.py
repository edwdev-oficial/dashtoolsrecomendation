from datetime import date
import numpy as np
import pandas as pd
from pathlib import Path

from dashtoolsrecomendation.reports import PdfReportConfig, gerar_relatorio_pdf


def _base_sintetica(quantidade: int = 80) -> pd.DataFrame:
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
            "Recomendação": ["Troca prioritária"] * 20 + ["Planejar renovação"] * 30 + ["Manter"] * 30,
            "Motivo principal": ["Alta frequência e alto custo"] * quantidade,
            "Máquina reparada": [True] * 60 + [False] * 20,
            "Pago pelo cliente com impostos": rng.uniform(0, 4_000, quantidade),
            "Valor absorvido com impostos": rng.uniform(0, 6_000, quantidade),
        }
    )


def _ams_sintetico(base: pd.DataFrame) -> pd.DataFrame:
    rows = []
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


if __name__ == '__main__':
    base = _base_sintetica(quantidade=80)
    df_ams = _ams_sintetico(base)
    config = PdfReportConfig(
        cliente="Cliente Teste",
        responsavel="Responsável Teste",
        cargo_responsavel="Rental Hilti do Brasil",
        data_emissao=date.today(),
        data_inicio=date(2022, 1, 1),
        data_fim=date(2026, 7, 24),
        idade_corte=5,
        fator_impostos=1.4,
        quantidade_cenario=25,
        incluir_base_completa=True,
    )

    pdf = gerar_relatorio_pdf(base=base, df_ams=df_ams, anos=[2022, 2023, 2024, 2025, 2026], config=config)
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "sample_report.pdf"
    out_path.write_bytes(pdf)
    print(f"WROTE:{out_path.resolve()}")
