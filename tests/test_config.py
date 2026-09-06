import os
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
        self.assertEqual(cfg.postgres_host, "localhost")
        self.assertEqual(cfg.postgres_port, 5432)
        self.assertEqual(cfg.postgres_db, "cnpj_db")

    def test_postgres_env_override(self):
        with unittest.mock.patch.dict(os.environ, {
            "POSTGRES_HOST": "db.production.local",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "receita_cnpj",
        }):
            cfg = Config.carregar()
            self.assertEqual(cfg.postgres_host, "db.production.local")
            self.assertEqual(cfg.postgres_port, 5433)
            self.assertEqual(cfg.postgres_db, "receita_cnpj")


if __name__ == "__main__":
    unittest.main()
