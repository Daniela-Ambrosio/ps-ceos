"""
Testes do Módulo de Banco de Dados (tests/test_database.py)
"""

from pathlib import Path
import tempfile
import unittest

from cnpj_extractor.database import (
    DatabaseManager,
    TABELAS_PERMITIDAS,
    identificar_tabela_por_arquivo,
    obter_comando_insert,
    validar_tabela,
)


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.tmp.name) / "test.db"))
        self.db.inicializar_tabelas()

    def tearDown(self):
        self.db.fechar()
        self.tmp.cleanup()

    def test_whitelist(self):
        self.assertEqual(validar_tabela("empresas"), "empresas")
        with self.assertRaises(ValueError):
            validar_tabela("malicious; DROP TABLE empresas;--")

    def test_identificar_tabela(self):
        self.assertEqual(identificar_tabela_por_arquivo("Empresas0.zip"), "empresas")
        self.assertEqual(identificar_tabela_por_arquivo("Cnaes.zip"), "cnaes")

    def test_insert_cmd_idempotente(self):
        cmd = obter_comando_insert("empresas")
        self.assertIn("INSERT OR REPLACE INTO empresas VALUES (?, ?, ?, ?, ?, ?, ?);", cmd)

        cmd_est = obter_comando_insert("estabelecimentos")
        self.assertIn("INSERT OR REPLACE INTO estabelecimentos VALUES", cmd_est)

    def test_idempotencia_reprocessamento_sem_duplicacao(self):
        lote_inicial = [("12345678", "EMPRESA TESTE LTDA", "2062", "49", 50000.0, "01", None)]
        self.db.inserir_lote("empresas", lote_inicial)
        self.assertEqual(self.db.contar_linhas("empresas"), 1)

        # Reprocessamento do mesmo lote (simulando falha parcial de arquivo)
        lote_reprocessado = [
            ("12345678", "EMPRESA TESTE LTDA (ATUALIZADA)", "2062", "49", 60000.0, "01", None),
            ("87654321", "SEGUNDA EMPRESA LTDA", "2062", "49", 20000.0, "01", None),
        ]
        self.db.inserir_lote("empresas", lote_reprocessado)

        # Deve haver exatamente 2 registros, sem duplicar a empresa 12345678
        self.assertEqual(self.db.contar_linhas("empresas"), 2)
        emp = self.db.buscar_empresa_detalhada("12345678")
        self.assertEqual(emp["razao_social"], "EMPRESA TESTE LTDA (ATUALIZADA)")
        self.assertEqual(emp["capital_social"], 60000.0)

    def test_verificar_e_garantir_indices_autonomo(self):
        # Cria tabelas
        self.db.inicializar_tabelas(["empresas", "estabelecimentos"])

        # Primeira verificação: deve criar os índices que não existiam
        criados_1 = self.db.verificar_e_garantir_indices(["empresas", "estabelecimentos"])
        self.assertGreater(len(criados_1), 0)

        # Segunda verificação imediata (sem linhas novas): não deve recriar nada
        criados_2 = self.db.verificar_e_garantir_indices(["empresas", "estabelecimentos"])
        self.assertEqual(len(criados_2), 0)

    def test_insert_and_search_detalhada(self):
        self.db.inserir_lote("empresas", [("12345678", "EMPRESA TESTE LTDA", "2062", "49", 50000.0, "01", None)])
        self.db.inserir_lote("estabelecimentos", [
            ("12345678", "0001", "90", "1", "MATRIZ SP", "02", "20200101", "00", None, None, "20200101", "6201500", None, "AV", "PAULISTA", "1000", None, "BELA VISTA", "01310100", "SP", "7107", "11", "99999999", None, None, None, None, "contato@empresa.com", None, None)
        ])
        emp = self.db.buscar_empresa_detalhada("12345678")
        self.assertIsNotNone(emp)
        self.assertEqual(emp["razao_social"], "EMPRESA TESTE LTDA")
        self.assertEqual(len(emp["estabelecimentos"]), 1)

    def test_filtros_busca(self):
        self.db.inserir_lote("empresas", [("12345678", "EMPRESA TESTE LTDA", "2062", "49", 50000.0, "01", None)])
        self.db.inserir_lote("estabelecimentos", [
            ("12345678", "0001", "90", "1", "MATRIZ SP", "02", "20200101", "00", None, None, "20200101", "6201500", None, "AV", "PAULISTA", "1000", None, "BELA VISTA", "01310100", "SP", "7107", "11", "99999999", None, None, None, None, "contato@empresa.com", None, None)
        ])
        res = self.db.buscar_empresas_por_filtros(termo_busca="TESTE", uf="SP")
        self.assertEqual(len(res), 1)


if __name__ == "__main__":
    unittest.main()
