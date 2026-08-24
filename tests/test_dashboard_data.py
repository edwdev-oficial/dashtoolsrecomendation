import unittest

import pandas as pd

from dashtoolsrecomendation.services.dashboard_data import (
    dados_faixas_idade,
    dados_graficos,
    dados_graficos_ams,
    idade_anos_completos,
    preparar_dashboard,
)


class DashboardDataTests(unittest.TestCase):
    def test_idade_anos_completos_considera_aniversario(self):
        hoje = pd.Timestamp("2026-07-20")
        self.assertEqual(idade_anos_completos(pd.Timestamp("2020-07-20"), hoje), 6)
        self.assertEqual(idade_anos_completos(pd.Timestamp("2020-07-21"), hoje), 5)

    def test_preparar_dashboard_preserva_origem_e_cria_indicadores(self):
        source = pd.DataFrame(
            {
                "Id": ["1"],
                "Data de compra": ["2020-07-21"],
                "Último Reparo": [""],
                "Quantidade de reparos": [2],
                "# Reparos": [1],
                "# Notif.": [2],
                "Garantia": ["fora"],
                "Grupo": ["Comprado"],
                "Modelo": ["M1"],
            }
        )
        ids = pd.DataFrame({"Id": ["1"], "UF": ["SP"], "cliente": ["Cliente"]})

        result = preparar_dashboard(source, ids, hoje=pd.Timestamp("2026-07-20"))

        self.assertNotIn("idade_int (a)", source.columns)
        self.assertEqual(result.loc[0, "idade_int (a)"], 5)
        self.assertEqual(result.loc[0, "reparada"], "Sim")
        self.assertEqual(result.loc[0, "Garantia"], "Não")
        self.assertEqual(result.loc[0, "Reparo Rejeitado"], "Sim")

    def test_garantia_considera_reparo_de_comprado_e_status_roubado(self):
        source = pd.DataFrame(
            {
                "Id": ["1", "2", "3", "4", "5"],
                "Grupo": ["Comprado", "Comprado", "Frota", "Frota", "Comprado"],
                "Último Reparo": [None, "01/06/2026", None, None, "01/06/2026"],
                "Garantia": ["dentro", "dentro", "fora", "fora", "dentro"],
                "Status da Ferramenta": [
                    "Ativa",
                    "Ativa",
                    "Roubado",
                    "Ativa",
                    "  ROUBADO  ",
                ],
            }
        )
        ids = pd.DataFrame({"Id": source["Id"]})

        result = preparar_dashboard(source, ids)

        self.assertEqual(
            result["Garantia"].tolist(),
            ["Não", "Sim", "Não", "Sim", "Não"],
        )

    def test_garantia_trata_na_introduzido_pelo_merge(self):
        source = pd.DataFrame({"Id": ["1"]})
        ids = pd.DataFrame(
            {
                "Id": ["1"],
                "Grupo": pd.Series([pd.NA], dtype="string"),
                "Último Reparo": pd.Series([pd.NA], dtype="string"),
                "Garantia": pd.Series([pd.NA], dtype="string"),
                "Status da Ferramenta": pd.Series([pd.NA], dtype="string"),
            }
        )

        result = preparar_dashboard(source, ids)

        self.assertEqual(result.loc[0, "Garantia"], "Não")

    def test_fim_periodo_futuro_fica_nulo_quando_nao_ha_garantia(self):
        source = pd.DataFrame(
            {
                "Id": ["1", "2", "3", "4"],
                "Grupo": ["Comprado", "Comprado", "Comprado", "Frota"],
                "Último Reparo": [None, "01/06/2026", None, "01/06/2026"],
                "Garantia": ["dentro", "dentro", "dentro", "dentro"],
                "Status da Ferramenta": ["Ativa", "Ativa", "Ativa", "Roubado"],
                "Data de Término do Contrato": ["", "", "", "05/08/2026"],
                "Fim do período sem custo": [
                    "01/08/2026",
                    "01/08/2026",
                    "19/07/2026",
                    "valor substituído",
                ],
            }
        )
        ids = pd.DataFrame({"Id": source["Id"]})

        result = preparar_dashboard(
            source,
            ids,
            hoje=pd.Timestamp("2026-07-20"),
        )

        self.assertEqual(
            result["Garantia"].tolist(),
            ["Não", "Sim", "Não", "Não"],
        )
        self.assertIsNone(result.loc[0, "Fim do período sem custo"])
        self.assertEqual(result.loc[1, "Fim do período sem custo"], "01/08/2026")
        self.assertEqual(result.loc[2, "Fim do período sem custo"], "19/07/2026")
        self.assertIsNone(result.loc[3, "Fim do período sem custo"])
        self.assertEqual(
            result["Fim período sem custo (dias)"].tolist(),
            [0, 12, 0, 0],
        )

    def test_fim_periodo_sem_custo_usa_termino_apenas_para_frota(self):
        source = pd.DataFrame(
            {
                "Id": ["1", "2", "3"],
                "Grupo": ["Frota", "  FROTA  ", "Comprado"],
                "Data de Término do Contrato": [
                    "2027-01-10",
                    "2027-02-20",
                    "2027-03-30",
                ],
                "Fim do período sem custo": [
                    "valor anterior 1",
                    "valor anterior 2",
                    "valor preservado",
                ],
            }
        )
        ids = pd.DataFrame({"Id": ["1", "2", "3"]})

        result = preparar_dashboard(source, ids)

        self.assertEqual(
            result["Fim do período sem custo"].tolist(),
            ["2027-01-10", "2027-02-20", "valor preservado"],
        )

    def test_fim_periodo_sem_custo_em_dias(self):
        source = pd.DataFrame(
            {
                "Id": ["1", "2", "3", "4", "5"],
                "Grupo": ["Frota", "Comprado", "Comprado", "Comprado", "Comprado"],
                "Data de Término do Contrato": [
                    "01/08/2026",
                    "",
                    "",
                    "",
                    "",
                ],
                "Fim do período sem custo": [
                    "valor substituído",
                    "19/07/2026",
                    None,
                    "",
                    "20/07/2026",
                ],
            }
        )
        ids = pd.DataFrame({"Id": source["Id"]})

        result = preparar_dashboard(
            source,
            ids,
            hoje=pd.Timestamp("2026-07-20"),
        )

        self.assertEqual(
            result["Fim período sem custo (dias)"].tolist(),
            [12, 0, 0, 0, 0],
        )

    def test_agregacoes_e_faixas(self):
        df = pd.DataFrame(
            {
                "Modelo": ["A", "A", "B"],
                "Grupo": ["Comprado", "Comprado", "Frota"],
                "Quantidade de reparos": [1, 2, 3],
                "idade_int (a)": [2, 4, 7],
            }
        )
        charts = dados_graficos(df)
        repairs, machines = dados_faixas_idade(df, 4)

        self.assertEqual(charts["modelos"].loc[0, "qtd"], 2)
        self.assertEqual(
            charts["maquinas_idade"]["Quantidade de máquinas"].tolist(),
            [1, 1, 1],
        )
        self.assertEqual(repairs["Quantidade de reparos"].tolist(), [3, 3])
        self.assertEqual(machines["Quantidade de máquinas"].tolist(), [2, 1])

    def test_agregacoes_ams_normalizam_por_maquina(self):
        ams = pd.DataFrame(
            {
                "ano_reparo": [2025, 2026, 2026],
                "Modelo": ["A", "A", "B"],
                "Número de Série": ["1", "1", "2"],
                "# Reparos": [1, 2, 4],
                "Custo de Reparos": [100, 300, 800],
                "Pagado pelo Cliente": [40, 100, 300],
                "Economia": [60, 200, 500],
                "Idade em Anos": [5, 6, 8],
            }
        )

        result = dados_graficos_ams(ams)
        modelo_a = result["por_modelo"].set_index("Modelo").loc["A"]

        self.assertEqual(result["por_ano"]["Reparações"].tolist(), [1, 6])
        self.assertEqual(result["totais"]["maquinas"], 2)
        self.assertEqual(result["totais"]["reparacoes_por_maquina"], 3.5)
        self.assertEqual(modelo_a["Máquinas"], 1)
        self.assertEqual(modelo_a["Reparações por máquina"], 3)
        self.assertEqual(modelo_a["Custo por máquina"], 400)


if __name__ == "__main__":
    unittest.main()
