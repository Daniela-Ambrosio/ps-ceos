import unittest
from cnpj_extractor.config import Config, extrair_token_e_base_url

class TestConfig(unittest.TestCase):
    def test_extrair_token(self):
        token, webdav, base = extrair_token_e_base_url("https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9")
        self.assertEqual(token, "YggdBLfdninEJX9")

    def test_defaults(self):
        cfg = Config.carregar()
        self.assertEqual(cfg.share_token, "YggdBLfdninEJX9")
        self.assertEqual(cfg.batch_size, 20000)

if __name__ == "__main__":
    unittest.main()
