import unittest

import pandas as pd

from dashtoolsrecomendation.services.data_processing import (
    AMS_ORIGIN_ID_COLUMN,
    AMS_ORIGIN_NAME_COLUMN,
    agrupar_ams,
    consolidar_conta_atual,
    detectar_maquinas_duplicadas_parque,
    detectar_series_multiconta,
    preparacoes_por_ano,
    preparar_ams,
)


class DataProcessingTests(unittest.TestCase):
    def test_preparar_e_agrupar_ams(self):
        raw = pd.DataFrame(
            {
                "Cliente": ["0001 - Cliente", "Total"],
                "Número de Série": [123.0, 999.0],
                "# Notif.": ["2", "1"],
                "# Reparos": [1, 1],
                "Idade em Anos": [2, 1],
                "Material": ["MAT", "TOTAL"],
                "Nome do Material": ["Item", "Total"],
                "FM Frota": ["N", "N"],
                "Custo de Reparos": [10.0, 1.0],
                "Pagado pelo Cliente": [4.0, 1.0],
                "Economia": [6.0, 0.0],
            }
        )

        prepared = preparar_ams(raw)
        grouped = agrupar_ams(prepared)

        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared.loc[0, "Número de Série"], "123")
        self.assertEqual(grouped.loc[0, "# Notif."], 2)
        self.assertEqual(grouped.loc[0, "Custo de Reparos"], 10.0)


    def test_preparar_ams_preserva_origem_e_consolida_conta_como_par(self):
        raw = pd.DataFrame(
            {
                "Cliente": [
                    "0001 - Cliente Antigo",
                    "0002 - Cliente Atual",
                ],
                "Número de Série": [123.0, 123.0],
                "# Notif.": [1, 1],
                "# Reparos": [1, 1],
                "Idade em Anos": [3, 2],
                "Material": ["MAT", "MAT"],
                "Nome do Material": ["Item", "Item"],
                "FM Frota": ["N", "N"],
                "Custo de Reparos": [10.0, 20.0],
                "Pagado pelo Cliente": [4.0, 8.0],
                "Economia": [6.0, 12.0],
                "ano_reparo": [2025, 2026],
            }
        )

        prepared = preparar_ams(raw).reset_index(drop=True)

        self.assertEqual(
            prepared[AMS_ORIGIN_ID_COLUMN].tolist(),
            ["0001", "0002"],
        )
        self.assertEqual(
            prepared[AMS_ORIGIN_NAME_COLUMN].tolist(),
            ["Cliente Antigo", "Cliente Atual"],
        )
        self.assertEqual(prepared["Id"].tolist(), ["0002", "0002"])
        self.assertEqual(
            prepared["Razao Social"].tolist(),
            ["Cliente Atual", "Cliente Atual"],
        )

    def test_preparar_ams_nao_mistura_mesma_serie_de_materiais_diferentes(self):
        raw = pd.DataFrame(
            {
                "Cliente": ["0001 - Cliente A", "0002 - Cliente B"],
                "Número de Série": [99.0, 99.0],
                "# Notif.": [1, 1],
                "# Reparos": [1, 1],
                "Idade em Anos": [2, 2],
                "Material": ["MAT-A", "MAT-B"],
                "Nome do Material": ["Martelo TE 7", "Rompedor TE 700"],
                "FM Frota": ["N", "N"],
                "Custo de Reparos": [100.0, 800.0],
                "Pagado pelo Cliente": [40.0, 500.0],
                "Economia": [60.0, 300.0],
                "ano_reparo": [2026, 2026],
            }
        )

        prepared = preparar_ams(raw).set_index("Nome do Material")

        self.assertEqual(prepared.loc["Martelo TE 7", "Id"], "0001")
        self.assertEqual(prepared.loc["Rompedor TE 700", "Id"], "0002")
        self.assertEqual(
            prepared.loc["Martelo TE 7", "Razao Social"],
            "Cliente A",
        )
        self.assertEqual(
            prepared.loc["Rompedor TE 700", "Razao Social"],
            "Cliente B",
        )

    def test_detectar_series_multiconta_usa_conta_de_origem(self):
        raw = pd.DataFrame(
            {
                "Cliente": [
                    "20618571 - TRIADE AMERICANA COMERCIO DE",
                    "30405191 - VT4 AGUAS DE LINDOIA ALUGUEL LTDA",
                ],
                "Número de Série": [139477.0, 139477.0],
                "# Notif.": [1, 1],
                "# Reparos": [1, 1],
                "Idade em Anos": [2, 2],
                "Material": ["MAT", "MAT"],
                "Nome do Material": [
                    "Breaker TE 800-AVR 220V",
                    "Breaker TE 800-AVR 220V",
                ],
                "FM Frota": ["N", "N"],
                "Custo de Reparos": [3270.328, 2879.138],
                "Pagado pelo Cliente": [0.0, 0.0],
                "Economia": [3270.328, 2879.138],
                "ano_reparo": [2026, 2026],
            }
        )

        prepared = preparar_ams(raw)
        audit = detectar_series_multiconta(prepared)

        self.assertEqual(len(audit), 1)
        self.assertEqual(audit.loc[0, "Número de Série"], "139477")
        self.assertEqual(audit.loc[0, "qtd_ids"], 2)
        self.assertEqual(
            audit.loc[0, "ids"],
            ["20618571", "30405191"],
        )
        self.assertEqual(audit.loc[0, "primeiro_ano"], 2026)
        self.assertEqual(audit.loc[0, "ultimo_ano"], 2026)

    def test_agrupar_ams_mantem_uma_maquina_e_soma_historico_multiconta(self):
        raw = pd.DataFrame(
            {
                "Cliente": [
                    "0001 - Cliente Antigo",
                    "0002 - Cliente Atual AMS",
                ],
                "Número de Série": [123.0, 123.0],
                "# Notif.": [1, 2],
                "# Reparos": [1, 3],
                "Idade em Anos": [3, 2],
                "Material": ["MAT", "MAT"],
                "Nome do Material": ["Item", "Item"],
                "FM Frota": ["N", "N"],
                "Custo de Reparos": [100.0, 300.0],
                "Pagado pelo Cliente": [40.0, 120.0],
                "Economia": [60.0, 180.0],
                "ano_reparo": [2025, 2026],
            }
        )

        prepared = preparar_ams(raw)
        prepared["Modelo"] = "TE 700"
        grouped = agrupar_ams(prepared)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped.loc[0, "Número de Série"], "123")
        self.assertEqual(grouped.loc[0, "Id"], "0002")
        self.assertEqual(grouped.loc[0, "Razao Social"], "Cliente Atual AMS")
        self.assertEqual(grouped.loc[0, "# Reparos"], 4)
        self.assertEqual(grouped.loc[0, "Custo de Reparos"], 400.0)

    def test_consolidar_conta_atual_prioriza_parque_e_usa_ams_como_fallback(self):
        merged = pd.DataFrame(
            {
                "Id_x": ["0099", pd.NA],
                "Razao Social_x": ["Conta Atual Parque", pd.NA],
                "Id_y": ["0002", "0003"],
                "Razao Social_y": ["Conta Recente AMS", "Somente AMS"],
            }
        )

        result = consolidar_conta_atual(merged)

        self.assertEqual(result.loc[0, "Id"], "0099")
        self.assertEqual(result.loc[0, "Razão Social"], "Conta Atual Parque")
        self.assertEqual(result.loc[1, "Id"], "0003")
        self.assertEqual(result.loc[1, "Razão Social"], "Somente AMS")

    def test_detectar_maquinas_duplicadas_parque_bloqueia_unidade_repetida(self):
        parque = pd.DataFrame(
            {
                "Número de série": ["123", "123", "456"],
                "Modelo": ["TE 700", "TE 700", "TE 500"],
                "Id": ["0001", "0002", "0003"],
                "Razao Social": ["Conta A", "Conta B", "Conta C"],
            }
        )

        result = detectar_maquinas_duplicadas_parque(parque)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "Número de série"], "123")
        self.assertEqual(result.loc[0, "qtd_registros"], 2)
        self.assertEqual(result.loc[0, "qtd_ids"], 2)
        self.assertEqual(result.loc[0, "ids"], ["0001", "0002"])

    def test_serie_igual_em_modelos_diferentes_permanece_separada(self):
        ams = pd.DataFrame(
            {
                "Número de Série": ["99", "99"],
                "Modelo": ["TE-7", "TE-700"],
                "Id": ["1", "1"],
                "Razao Social": ["Cliente", "Cliente"],
                "Nome do Material": ["Martelo TE 7", "Rompedor TE 700"],
                "FM Frota": ["No", "Fleet"],
                "# Notif.": [2, 5],
                "# Reparos": [1, 4],
                "Custo de Reparos": [100.0, 800.0],
                "Pagado pelo Cliente": [40.0, 500.0],
                "Economia": [60.0, 300.0],
                "ano_reparo": [2026, 2026],
            }
        )
        parque = pd.DataFrame(
            {
                "Número de Série": ["99", "99"],
                "Modelo": ["TE-7", "TE-700"],
            }
        )

        grouped = agrupar_ams(ams)
        por_ano = preparacoes_por_ano(parque, ams, [2026]).set_index("Modelo")

        self.assertEqual(len(grouped), 2)
        self.assertEqual(por_ano.loc["TE-7", "Reparos_no_período"], 1)
        self.assertEqual(por_ano.loc["TE-700", "Reparos_no_período"], 4)
        self.assertEqual(por_ano.loc["TE-7", "Custo_no_período"], 100)
        self.assertEqual(por_ano.loc["TE-700", "Custo_no_período"], 800)


if __name__ == "__main__":
    unittest.main()
