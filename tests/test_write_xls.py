import unittest

import pandas as pd

from dashtoolsrecomendation.services.write_xls import (
    gerar_excel,
    normalizar_coluna_numero_serie,
)


class WriteXlsTests(unittest.TestCase):
    def test_consolida_aliases_do_numero_de_serie(self):
        source = pd.DataFrame(
            {
                "Id": ["1", "2"],
                "Número de série": ["", "123"],
                "Número de Série": ["456", "999"],
            }
        )

        result = normalizar_coluna_numero_serie(source)

        self.assertEqual(result.columns.tolist().count("Número de série"), 1)
        self.assertNotIn("Número de Série", result.columns)
        self.assertEqual(result["Número de série"].tolist(), ["456", "123"])

    def test_gera_excel_quando_as_duas_variacoes_estao_presentes(self):
        source = pd.DataFrame(
            {
                "Id": ["1"],
                "Número de série": [pd.NA],
                "Número de Série": ["456"],
            }
        )

        output = gerar_excel(source)
        exported = pd.read_excel(output)

        self.assertGreater(len(output.getvalue()), 0)
        self.assertEqual(exported.columns.tolist().count("Número de série"), 1)
        self.assertEqual(exported.loc[0, "Número de série"], 456)


if __name__ == "__main__":
    unittest.main()
