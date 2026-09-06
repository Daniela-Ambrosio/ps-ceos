import unittest
from cnpj_extractor.web.components import (
    formatar_cnpj,
    formatar_data,
    formatar_moeda,
)


class TestWebComponents(unittest.TestCase):

    def test_formatar_cnpj(self):
        self.assertEqual(formatar_cnpj("00000000000191"), "00.000.000/0001-91")
        self.assertEqual(formatar_cnpj("00000000"), "00.000.000")
        self.assertEqual(formatar_cnpj(""), "-")
        self.assertEqual(formatar_cnpj(None), "-")

    def test_formatar_moeda(self):
        self.assertEqual(formatar_moeda(1500.50), "R$ 1.500,50")
        self.assertEqual(formatar_moeda(0.0), "R$ 0,00")
        self.assertEqual(formatar_moeda(None), "R$ 0,00")

    def test_formatar_data(self):
        self.assertEqual(formatar_data("20200515"), "15/05/2020")
        self.assertEqual(formatar_data(None), "-")
        self.assertEqual(formatar_data(""), "-")


if __name__ == "__main__":
    unittest.main()
