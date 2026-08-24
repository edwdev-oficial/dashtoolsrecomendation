import unittest

import pandas as pd

from dashtoolsrecomendation.services.data_processing import (
    agrupar_ams,
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
