import unittest

import pandas as pd

from dashtoolsrecomendation.services.data_processing import agrupar_ams, preparar_ams


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


if __name__ == "__main__":
    unittest.main()
