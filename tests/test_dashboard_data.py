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
