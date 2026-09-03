import unittest
from cnpj_extractor.web.components import (
    formatar_cnpj,
    formatar_moeda,
    formatar_data,
    renderizar_badge_situacao,
)

class TestWebComponents(unittest.TestCase):
    def test_formatar_cnpj(self):
        self.assertEqual(formatar_cnpj("00000000000191"), "00.000.000/0001-91")
        self.assertEqual(formatar_cnpj("00000000"), "00.000.000")

    def test_formatar_moeda(self):
        self.assertEqual(formatar_moeda(1500.50), "R$ 1.500,50")

    def test_formatar_data(self):
        self.assertEqual(formatar_data("20200515"), "15/05/2020")
        self.assertEqual(formatar_data(None), "-")

    def test_badge_situacao(self):
        self.assertIn("badge-ativa", renderizar_badge_situacao("Ativa"))
        self.assertIn("badge-baixada", renderizar_badge_situacao("Baixada"))

if __name__ == "__main__":
    unittest.main()
