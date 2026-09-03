"""
Testes do Módulo de Extração e Parsing (tests/test_extraction.py)
"""

import io
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import zipfile

from cnpj_extractor.config import Config
from cnpj_extractor.extraction import (
    ArquivoRemoto,
    ReceitaFederalClient,
    _sanitizar_float,
    _sanitizar_texto,
    abrir_csv_do_zip_remoto,
    gerar_lotes_dados,
    iterar_linhas_csv,
    normalizar_linha,
)


class TestExtraction(unittest.TestCase):

    def _criar_zip_em_memoria(self, arquivos_dict: dict) -> bytes:
        """Cria um arquivo ZIP em memória para simulação de stream HTTP."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for nome, conteudo in arquivos_dict.items():
                zf.writestr(nome, conteudo)
        return buf.getvalue()

    def test_abrir_csv_do_zip_remoto_sucesso_e_limpeza(self):
        conteudo_csv = b"12345678;EMPRESA TESTE;2062;49;5000,00;01;\n"
        zip_bytes = self._criar_zip_em_memoria({"empresas.csv": conteudo_csv})

        temp_path_usado = None
        with abrir_csv_do_zip_remoto(io.BytesIO(zip_bytes), encoding="latin1") as text_stream:
            linhas = list(text_stream)
            self.assertEqual(len(linhas), 1)
            self.assertIn("EMPRESA TESTE", linhas[0])

        # Verifica se o arquivo temporário foi removido do disco
        if temp_path_usado:
            self.assertFalse(os.path.exists(temp_path_usado))

    def test_abrir_csv_do_zip_remoto_multiplas_entradas(self):
        # ZIP com arquivo CSV e arquivo auxiliar
        arquivos = {
            "LEIAME.txt": b"Instrucoes",
            "estabelecimentos.csv": b'"12345678";"0001";"90";"1"\n',
        }
        zip_bytes = self._criar_zip_em_memoria(arquivos)

        with abrir_csv_do_zip_remoto(io.BytesIO(zip_bytes), encoding="latin1") as text_stream:
            linhas = list(text_stream)
            self.assertEqual(len(linhas), 1)
            self.assertIn("12345678", linhas[0])

    def test_abrir_csv_do_zip_remoto_arquivo_corrompido_lanca_erro(self):
        # Bytes corrompidos
        bytes_corrompidos = b"PK\x03\x04dados_corrompidos_incompletos"
        with self.assertRaises(zipfile.BadZipFile):
            with abrir_csv_do_zip_remoto(io.BytesIO(bytes_corrompidos)) as text_stream:
                list(text_stream)

    def test_sanitizar_texto(self):
        self.assertEqual(_sanitizar_texto("  teste  "), "teste")
        self.assertIsNone(_sanitizar_texto(""))
        self.assertIsNone(_sanitizar_texto(None))
        self.assertEqual(_sanitizar_texto("texto\x00com\x00null"), "textocomnull")

    def test_sanitizar_float(self):
        self.assertEqual(_sanitizar_float("5000,00"), 5000.0)
        self.assertEqual(_sanitizar_float("1.500.000,50"), 1500000.50)
        self.assertIsNone(_sanitizar_float(""))
        self.assertIsNone(_sanitizar_float(None))
        self.assertIsNone(_sanitizar_float("invalido"))
        self.assertIsNone(_sanitizar_float("abc,def"))

    def test_normalizar_linha_empresas(self):
        row = ["12345678", "EMPRESA TESTE", "2062", "49", "1000,00", "01", ""]
        res = normalizar_linha("empresas", row)
        self.assertEqual(res, ("12345678", "EMPRESA TESTE", "2062", "49", 1000.0, "01", None))

    def test_normalizar_linha_estabelecimentos(self):
        row = ["12345678", "0001", "90", "1", "FANTASIA", "02", "20200101", "00", "", "", "20200101", "6201500", "", "AV", "PAULISTA", "1000", "", "CENTRO", "01001000", "sp", "7107", "11", "99999999", "", "", "", "", "CONTATO@EMPRESA.COM", "", ""]
        res = normalizar_linha("estabelecimentos", row)
        self.assertEqual(len(res), 30)
        self.assertEqual(res[0], "12345678")
        self.assertEqual(res[19], "SP")  # UF normalizado para uppercase
        self.assertEqual(res[27], "contato@empresa.com")  # Email normalizado para lowercase

    def test_normalizar_linha_socios(self):
        row = ["12345678", "2", "FULANO DE TAL", "***123456**", "49", "20200101", "", "", "", "", "4"]
        res = normalizar_linha("socios", row)
        self.assertEqual(len(res), 11)
        self.assertEqual(res[0], "12345678")
        self.assertEqual(res[2], "FULANO DE TAL")

    def test_normalizar_linha_simples(self):
        row = ["12345678", "S", "20200101", "", "N", "", ""]
        res = normalizar_linha("simples", row)
        self.assertEqual(len(res), 7)
        self.assertEqual(res[0], "12345678")
        self.assertEqual(res[1], "S")

    def test_normalizar_linha_lookup_cnaes(self):
        row = ["6201500", "Desenvolvimento de programas de computador"]
        res = normalizar_linha("cnaes", row)
        self.assertEqual(res, ("6201500", "Desenvolvimento de programas de computador"))

    def test_normalizar_linha_tabela_invalida_lanca_erro(self):
        with self.assertRaises(ValueError):
            normalizar_linha("estabelecimento", ["123", "456"])  # sem 's'

        with self.assertRaises(ValueError):
            normalizar_linha("tabela_inexistente", ["123", "456"])

    def test_iterar_linhas_csv_com_linhas_invalidas_e_filtro(self):
        csv_conteudo = (
            '"12345678";"0001";"90";"1";"FANTASIA SP";"02";"20200101";"00";"";"";"20200101";"6201500";"";"AV";"A";"1";"";"B";"01001000";"SP"\n'
            'linha;malformada;com;poucas;colunas\n'
            '"87654321";"0001";"90";"1";"FANTASIA RJ";"02";"20200101";"00";"";"";"20200101";"6201500";"";"AV";"B";"2";"";"C";"20000000";"RJ"\n'
        )
        stream = io.StringIO(csv_conteudo)
        linhas = list(iterar_linhas_csv(stream, tabela="estabelecimentos", filtro_uf="SP"))
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0][0], "12345678")
        self.assertEqual(linhas[0][19], "SP")

    def test_gerar_lotes(self):
        items = list(range(5))
        lotes = list(gerar_lotes_dados(iter(items), 2))
        self.assertEqual(len(lotes), 3)

    def test_client_validacao_mes_invalido(self):
        cfg = Config(share_token="MeuToken")
        client = ReceitaFederalClient(cfg)
        with self.assertRaises(ValueError):
            client.listar_arquivos("2026")  # Formato incompleto, esperado AAAA-MM

        with self.assertRaises(ValueError):
            client.listar_arquivos("")

    def test_client_validacao_token_vazio(self):
        cfg = Config(share_token="")
        with self.assertRaises(ValueError):
            ReceitaFederalClient(cfg)

    @patch("urllib.request.urlopen")
    def test_client_tratamento_http_401_permissao(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://example.com",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        cfg = Config(share_token="TokenInvalido")
        client = ReceitaFederalClient(cfg)
        with self.assertRaises(PermissionError):
            client.listar_meses_disponiveis()


if __name__ == "__main__":
    unittest.main()
