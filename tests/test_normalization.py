import unittest
from unittest.mock import patch

import pandas as pd

from dashtoolsrecomendation.services.normalization import itens_nao_normalizados, normalizar


class NormalizationTests(unittest.TestCase):
    @patch("dashtoolsrecomendation.services.normalization.carregar_normalizacao")
    def test_somente_tlm_nao_gera_sufixos(self, load_mapping):
        load_mapping.return_value = pd.DataFrame(
            {
                "Descrição": ["Item"],
                "Tipo": ["Tipo novo"],
                "Linha": ["Linha nova"],
                "Modelo": ["Modelo novo"],
                "Valor": [999],
            }
        )
        source = pd.DataFrame(
            {
                "Descrição": ["Item"],
                "Tipo": ["antigo"],
                "Linha": ["antiga"],
                "Modelo": ["antigo"],
                "Valor": [10],
            }
        )

        result = normalizar(source, somente_tlm=True)

        self.assertFalse(any(column.endswith("_x") for column in result.columns))
        self.assertEqual(result.loc[0, "Valor"], 10)
        self.assertEqual(result.loc[0, "Tipo"], "Tipo novo")

    def test_identifica_item_nao_normalizado(self):
        df = pd.DataFrame(
            {"Tipo": ["", "T"], "Linha": ["L", "L"], "Modelo": ["M", "M"]}
        )
        self.assertEqual(len(itens_nao_normalizados(df)), 1)


if __name__ == "__main__":
    unittest.main()
