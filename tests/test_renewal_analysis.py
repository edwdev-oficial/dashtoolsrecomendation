import unittest

import pandas as pd

from dashtoolsrecomendation.services import renewal_analysis


class RenewalAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.parque = pd.DataFrame(
            {
                "Número de Série": ["1", "2", "3"],
                "Modelo": ["A", "A", "B"],
                "Grupo": ["Comprado", "Comprado", "Frota"],
                "Status da Ferramenta": ["Ativo", "Ativo", "Ativo"],
                "Data de compra": ["2018-01-01", "2025-01-01", "2020-01-01"],
                "idade_int (a)": [8, 1, 6],
                "_presente_parque": [True, True, True],
            }
        )
        self.ams = pd.DataFrame(
            {
                "Número de Série": ["1", "1", "2", "4"],
                "ano_reparo": [2024, 2026, 2026, 2025],
                "Modelo": ["A", "A", "A", "C"],
                "# Reparos": [2, 1, 1, 3],
                "# Notif.": [2, 1, 1, 3],
                "Custo de Reparos": [100, 200, 50, 500],
                "Pagado pelo Cliente": [70, 150, 50, 400],
                "Economia": [30, 50, 0, 100],
            }
        )

    def test_resumo_usa_todo_o_parque_como_denominador(self):
        base = renewal_analysis.preparar_base_maquinas(
            self.parque,
            self.ams,
            [2024, 2025, 2026],
            data_corte=pd.Timestamp("2026-07-21"),
            tax_factor=1.4,
        )
        summary = renewal_analysis.resumo_executivo(base)

        self.assertEqual(summary["maquinas"], 3)
        self.assertEqual(summary["maquinas_reparadas"], 2)
        self.assertEqual(summary["reparacoes"], 4)
        self.assertAlmostEqual(summary["reparacoes_por_maquina_parque"], 4 / 3)
        self.assertAlmostEqual(summary["custo"], 350 * 1.4)

    def test_modelos_usam_maquinas_do_parque(self):
        base = renewal_analysis.preparar_base_maquinas(
            self.parque,
            self.ams,
            [2024, 2025, 2026],
            data_corte=pd.Timestamp("2026-07-21"),
        )
        models = renewal_analysis.analise_modelos(base).set_index("Modelo")

        self.assertEqual(models.loc["A", "Máquinas"], 2)
        self.assertEqual(models.loc["A", "Reparações"], 4)
        self.assertEqual(models.loc["A", "Reparações por máquina"], 2)
        self.assertEqual(models.loc["B", "Reparações por máquina"], 0)

    def test_reconciliacao_separa_fontes(self):
        details, summary = renewal_analysis.reconciliar_fontes(
            self.parque,
            self.ams,
            [2024, 2025, 2026],
        )

        self.assertEqual(summary["parque_atual"], 3)
        self.assertEqual(summary["ams_periodo"], 3)
        self.assertEqual(summary["presentes_duas"], 2)
        self.assertEqual(summary["somente_parque"], 1)
        self.assertEqual(summary["somente_ams"], 1)
        self.assertEqual(len(details), 4)

    def test_ano_parcial_pode_ser_projetado(self):
        annual = renewal_analysis.analise_anual(
            self.ams,
            [2024, 2025, 2026],
            data_corte=pd.Timestamp("2026-07-01"),
            projetar_ano_parcial=True,
            tax_factor=1,
        ).set_index("Ano")

        self.assertTrue(annual.loc[2026, "Ano parcial"])
        self.assertGreater(
            annual.loc[2026, "Reparações projetadas"],
            annual.loc[2026, "Reparações realizadas"],
        )
        self.assertEqual(
            annual.loc[2025, "Reparações projetadas"],
            annual.loc[2025, "Reparações realizadas"],
        )

    def test_cenario_reporta_concentracao_sem_chamar_de_economia(self):
        base = renewal_analysis.preparar_base_maquinas(
            self.parque,
            self.ams,
            [2024, 2025, 2026],
            data_corte=pd.Timestamp("2026-07-21"),
        )
        selected, summary = renewal_analysis.cenario_renovacao(base, 1)

        self.assertEqual(len(selected), 1)
        self.assertGreater(summary["percentual_custo"], 0)
        self.assertLessEqual(summary["percentual_custo"], 1)


if __name__ == "__main__":
    unittest.main()
