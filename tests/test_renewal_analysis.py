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

    def test_percentil_normaliza_valores_distintos_entre_zero_e_um(self):
        values = pd.Series([10, 20, 30], index=["a", "b", "c"])

        result = renewal_analysis._percentile_score(values)

        expected = pd.Series([0.0, 0.5, 1.0], index=values.index)
        pd.testing.assert_series_equal(result, expected)

    def test_percentil_usa_posicao_media_em_empates(self):
        cases = [
            ([0, 0, 10], [0.25, 0.25, 1.0]),
            ([0, 10, 10], [0.0, 0.75, 0.75]),
        ]

        for values, expected_values in cases:
            with self.subTest(values=values):
                result = renewal_analysis._percentile_score(pd.Series(values))
                expected = pd.Series(expected_values)
                pd.testing.assert_series_equal(result, expected)

    def test_percentil_retorna_zero_quando_nao_existe_variacao(self):
        cases = [
            pd.Series(dtype="float64"),
            pd.Series([5]),
            pd.Series([5, 5, 5]),
        ]

        for values in cases:
            with self.subTest(values=values.tolist()):
                result = renewal_analysis._percentile_score(values)
                expected = pd.Series(0.0, index=values.index)
                pd.testing.assert_series_equal(result, expected)

    def test_indice_e_recomendacao_seguem_metodologia_normalizada(self):
        parque = pd.DataFrame(
            {
                "Número de Série": ["A", "B", "C"],
                "Modelo": ["M1", "M2", "M3"],
                "Grupo": ["Comprado"] * 3,
                "Status da Ferramenta": ["Ativo"] * 3,
                "Data de compra": ["2016-01-01", "2021-01-01", "2025-01-01"],
                "idade_int (a)": [10, 5, 1],
            }
        )
        ams = pd.DataFrame(
            {
                "Número de Série": ["A", "B"],
                "ano_reparo": [2026, 2026],
                "Modelo": ["M1", "M2"],
                "# Reparos": [3, 2],
                "# Notif.": [3, 2],
                "Custo de Reparos": [300.0, 200.0],
                "Pagado pelo Cliente": [300.0, 200.0],
                "Economia": [0.0, 0.0],
            }
        )

        base = renewal_analysis.preparar_base_maquinas(
            parque,
            ams,
            [2026],
            data_corte=pd.Timestamp("2026-12-31"),
            tax_factor=1,
        ).set_index("Número de Série")

        pd.testing.assert_frame_equal(
            base.loc[
                ["A", "B", "C"],
                [
                    "Percentil idade",
                    "Percentil frequência",
                    "Percentil custo",
                    "Percentil recorrência",
                ],
            ],
            pd.DataFrame(
                {
                    "Percentil idade": [1.0, 0.5, 0.0],
                    "Percentil frequência": [1.0, 0.5, 0.0],
                    "Percentil custo": [1.0, 0.5, 0.0],
                    "Percentil recorrência": [0.75, 0.75, 0.0],
                },
                index=pd.Index(["A", "B", "C"], name="Número de Série"),
            ),
            check_dtype=False,
            check_index_type=False,
        )
        self.assertEqual(
            base["Índice de prioridade"].to_dict(),
            {"A": 96.3, "B": 53.8, "C": 0.0},
        )
        self.assertEqual(
            base["Recomendação"].to_dict(),
            {
                "A": "Troca prioritária",
                "B": "Planejar renovação",
                "C": "Manter",
            },
        )

    def test_indice_25_com_uma_reparacao_permanece_manter(self):
        maquina = pd.Series(
            {
                "Grupo": "Comprado",
                "Status da Ferramenta": "Ativo",
                "Reparações no período": 1,
                "Índice de prioridade": 25.0,
                "Idade atual": 6.8,
            }
        )

        recomendacao = renewal_analysis._classificar_prioridade(maquina)

        self.assertEqual(recomendacao, "Manter")

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

    def test_mesma_serie_em_modelos_diferentes_preserva_as_duas_maquinas(self):
        parque = pd.DataFrame(
            {
                "Número de Série": ["99", "99"],
                "Modelo": ["TE-7", "TE-700"],
                "Grupo": ["Comprado", "Comprado"],
                "Status da Ferramenta": ["Ativo", "Ativo"],
                "Data de compra": ["2020-01-01", "2021-01-01"],
            }
        )
        ams = pd.DataFrame(
            {
                "Número de Série": ["99", "99"],
                "Modelo": ["TE-7", "TE-700"],
                "ano_reparo": [2026, 2026],
                "# Reparos": [2, 5],
                "# Notif.": [3, 6],
                "Custo de Reparos": [100.0, 900.0],
                "Pagado pelo Cliente": [40.0, 500.0],
                "Economia": [60.0, 400.0],
            }
        )

        base = renewal_analysis.preparar_base_maquinas(
            parque,
            ams,
            [2026],
            data_corte=pd.Timestamp("2026-12-31"),
            tax_factor=1,
        ).set_index("Modelo")

        self.assertEqual(len(base), 2)
        self.assertEqual(base.loc["TE-7", "Reparações no período"], 2)
        self.assertEqual(base.loc["TE-700", "Reparações no período"], 5)
        self.assertEqual(base.loc["TE-7", "Custo líquido"], 100)
        self.assertEqual(base.loc["TE-700", "Custo líquido"], 900)
        self.assertEqual(
            renewal_analysis.resumo_executivo(base.reset_index())["maquinas"],
            2,
        )

    def test_frota_ativa_tem_recomendacao_manter_independentemente_do_indice(self):
        parque = self.parque.copy()
        parque.loc[parque["Número de Série"].eq("1"), "Grupo"] = " Frota "
        parque.loc[
            parque["Número de Série"].eq("1"),
            "Status da Ferramenta",
        ] = "ATIVO"

        base = renewal_analysis.preparar_base_maquinas(
            parque,
            self.ams,
            [2024, 2025, 2026],
            data_corte=pd.Timestamp("2026-07-21"),
        ).set_index("Número de Série")

        maquina = base.loc["1"]
        self.assertGreaterEqual(maquina["Índice de prioridade"], 70)
        self.assertGreaterEqual(maquina["Reparações no período"], 2)
        self.assertEqual(maquina["Recomendação"], "Manter")
        self.assertEqual(maquina["Motivo principal"], "Gestão de Frotas")

    def test_troca_prioritaria_sem_gatilho_isolado_usa_motivo_combinado(self):
        maquina = pd.Series(
            {
                "Grupo": "Comprado",
                "Status da Ferramenta": "Ativo",
                "Recomendação": "Troca prioritária",
                "Percentil frequência": 0.74,
                "Percentil custo": 0.74,
                "Idade atual": 7.9,
                "Recorrência": 0.66,
            }
        )

        motivo = renewal_analysis._motivo_principal(maquina)

        self.assertEqual(
            motivo,
            "Prioridade combinada dos fatores analisados",
        )

    def test_recorrencia_relevante_e_motivo_mesmo_sem_alta_frequencia(self):
        maquina = pd.Series(
            {
                "Grupo": "Comprado",
                "Status da Ferramenta": "Ativo",
                "Recomendação": "Monitorar",
                "Percentil frequência": 0.50,
                "Percentil custo": 0.50,
                "Idade atual": 5,
                "Recorrência": 0.67,
            }
        )

        motivo = renewal_analysis._motivo_principal(maquina)

        self.assertEqual(motivo, "Reparações recorrentes")

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

    def test_reconciliacao_nao_confunde_modelos_com_a_mesma_serie(self):
        parque = pd.DataFrame(
            {
                "Número de Série": ["99"],
                "Modelo": ["TE-7"],
                "_presente_parque": [True],
            }
        )
        ams = pd.DataFrame(
            {
                "Número de Série": ["99"],
                "Modelo": ["TE-700"],
                "ano_reparo": [2026],
            }
        )

        details, summary = renewal_analysis.reconciliar_fontes(
            parque,
            ams,
            [2026],
        )

        self.assertEqual(summary["presentes_duas"], 0)
        self.assertEqual(summary["somente_parque"], 1)
        self.assertEqual(summary["somente_ams"], 1)
        self.assertEqual(set(details["Modelo"]), {"TE-7", "TE-700"})

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

    def test_cenario_ignora_manter_e_limita_ao_total_elegivel(self):
        base = pd.DataFrame(
            {
                "Número de Série": ["frota", "prioritaria", "planejada", "manter"],
                "Índice de prioridade": [95.0, 90.0, 60.0, 20.0],
                "Recomendação": [
                    "Manter",
                    "Troca prioritária",
                    "Planejar renovação",
                    "Manter",
                ],
                "Reparações no período": [10, 8, 4, 1],
                "Custo com impostos": [1000.0, 800.0, 400.0, 100.0],
                "Idade atual": [2.0, 9.0, 7.0, 3.0],
            }
        )

        selected, summary = renewal_analysis.cenario_renovacao(base, 10)

        self.assertEqual(
            selected["Número de Série"].tolist(),
            ["prioritaria", "planejada"],
        )
        self.assertFalse(selected["Recomendação"].eq("Manter").any())
        self.assertEqual(summary["maquinas"], 2)

    def test_quantidade_padrao_do_cenario_usa_trocas_prioritarias(self):
        base = pd.DataFrame(
            {
                "Idade atual": [12, 11, 10, 2],
                "Recomendação": [
                    "Troca prioritária",
                    "Planejar renovação",
                    "Troca prioritária",
                    "Manter",
                ],
            }
        )

        quantidade = renewal_analysis.quantidade_padrao_cenario(base)

        self.assertEqual(quantidade, 2)


if __name__ == "__main__":
    unittest.main()
