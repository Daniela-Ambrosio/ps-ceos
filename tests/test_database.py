"""
Testes do Módulo de Banco de Dados PostgreSQL (tests/test_database.py)
"""

import unittest
from unittest.mock import MagicMock, patch

from cnpj_extractor.config import Config
from cnpj_extractor.database import (
    CNPJRepository,
    TABELAS_DDL,
    TABELAS_PERMITIDAS,
    identificar_tabela_por_arquivo,
    obter_comando_upsert,
    validar_tabela,
)


class TestDatabase(unittest.TestCase):

    def test_whitelist(self):
        self.assertEqual(validar_tabela("empresas"), "empresas")
        self.assertEqual(validar_tabela("estabelecimentos"), "estabelecimentos")
        self.assertEqual(validar_tabela("cnaes"), "cnaes")
        with self.assertRaises(ValueError):
            validar_tabela("malicious; DROP TABLE empresas;--")
        with self.assertRaises(ValueError):
            validar_tabela("tabela_inventada")

    def test_identificar_tabela(self):
        self.assertEqual(identificar_tabela_por_arquivo("Empresas0.zip"), "empresas")
        self.assertEqual(identificar_tabela_por_arquivo("Cnaes.zip"), "cnaes")
        self.assertEqual(identificar_tabela_por_arquivo("Estabelecimentos9.zip"), "estabelecimentos")
        self.assertEqual(identificar_tabela_por_arquivo("Socios0.zip"), "socios")
        self.assertEqual(identificar_tabela_por_arquivo("Simples.zip"), "simples")
        self.assertIsNone(identificar_tabela_por_arquivo("arquivo_estranho.zip"))

    def test_ddl_numeric_e_pk_socios(self):
        # 1. Capital social NUMERIC(15, 2)
        ddl_emp = TABELAS_DDL["empresas"]
        self.assertIn("capital_social NUMERIC(15, 2)", ddl_emp)

        # 2. Sócios com data_entrada_sociedade na PK
        ddl_soc = TABELAS_DDL["socios"]
        self.assertIn("PRIMARY KEY (cnpj_basico, identificador_socio, nome_socio_razao_social, qualificacao_socio, data_entrada_sociedade)", ddl_soc)

    def test_upsert_cmd_postgresql_parametrizado(self):
        # 1. Empresas
        cmd_emp = obter_comando_upsert("empresas")
        self.assertIn("INSERT INTO empresas", cmd_emp)
        self.assertIn("%s", cmd_emp)
        self.assertNotIn("?", cmd_emp)
        self.assertIn("ON CONFLICT (cnpj_basico) DO UPDATE SET", cmd_emp)

        # 2. Estabelecimentos
        cmd_est = obter_comando_upsert("estabelecimentos")
        self.assertIn("INSERT INTO estabelecimentos", cmd_est)
        self.assertIn("ON CONFLICT (cnpj_basico, cnpj_ordem, cnpj_dv) DO UPDATE SET", cmd_est)

        # 3. Socios (com data_entrada_sociedade)
        cmd_soc = obter_comando_upsert("socios")
        self.assertIn("ON CONFLICT (cnpj_basico, identificador_socio, nome_socio_razao_social, qualificacao_socio, data_entrada_sociedade) DO UPDATE SET", cmd_soc)

        # 4. Simples
        cmd_sim = obter_comando_upsert("simples")
        self.assertIn("ON CONFLICT (cnpj_basico) DO UPDATE SET", cmd_sim)

        # 5. Lookups (cnaes, etc.)
        cmd_cnae = obter_comando_upsert("cnaes")
        self.assertIn("ON CONFLICT (codigo) DO UPDATE SET", cmd_cnae)

    def test_verificar_arquivos_pendentes(self):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Simula que apenas Empresas0.zip foi concluído
        mock_cursor.fetchall.return_value = [("Empresas0.zip",)]

        repo = CNPJRepository(mock_pool)
        esperados = ["Empresas0.zip", "Empresas1.zip", "Empresas2.zip"]
        pendentes = repo.verificar_arquivos_pendentes("2026-08", esperados)

        self.assertEqual(pendentes, ["Empresas1.zip", "Empresas2.zip"])
        self.assertFalse(repo.todos_arquivos_concluidos("2026-08", esperados))

        # Simula que todos foram concluídos
        mock_cursor.fetchall.return_value = [("Empresas0.zip",), ("Empresas1.zip",), ("Empresas2.zip",)]
        self.assertTrue(repo.todos_arquivos_concluidos("2026-08", esperados))


if __name__ == "__main__":
    unittest.main()
