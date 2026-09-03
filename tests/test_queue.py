import unittest
import sys
from unittest.mock import MagicMock, patch

if "pika" not in sys.modules:
    mock_pika = MagicMock()
    mock_pika.BasicProperties = MagicMock()
    sys.modules["pika"] = mock_pika

from cnpj_extractor.config import Config
from cnpj_extractor.queue.producer import TaskProducer
from cnpj_extractor.queue.worker import TaskWorker

class TestQueue(unittest.TestCase):
    @patch("cnpj_extractor.queue.producer.declarar_fila")
    @patch("cnpj_extractor.queue.producer.obter_conexao_rabbitmq")
    def test_producer(self, mock_conn, mock_decl):
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel
        mock_client = MagicMock()
        mock_client.obter_mes_mais_recente.return_value = "2026-08"
        mock_arq = MagicMock(nome="Cnaes.zip", url="http://x", tamanho_bytes=100)
        mock_client.listar_arquivos.return_value = [mock_arq]
        mock_db = MagicMock()
        mock_db.arquivo_ja_processado.return_value = False

        cfg = Config(rabbitmq_queue="test_q", db_path="data/test.db")
        producer = TaskProducer(config=cfg, client=mock_client, db=mock_db)
        total = producer.publicar_tarefas(tabelas=["lookup"])
        self.assertEqual(total, 1)

if __name__ == "__main__":
    unittest.main()
