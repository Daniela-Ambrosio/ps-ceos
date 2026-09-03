"""
Gerenciamento de Conexão com RabbitMQ (cnpj_extractor.queue.connection)
=======================================================================
"""

import logging
import time
from typing import Optional

try:
    import pika
except ImportError:
    pika = None

from ..config import Config

logger = logging.getLogger("cnpj_extractor.queue")


def obter_conexao_rabbitmq(
    config: Optional[Config] = None,
    max_retries: int = 15,
    retry_interval: int = 3,
):
    if pika is None:
        raise ImportError("A biblioteca 'pika' é necessária para integração com RabbitMQ.")

    cfg = config or Config.carregar()
    credentials = pika.PlainCredentials(cfg.rabbitmq_user, cfg.rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=cfg.rabbitmq_host,
        port=cfg.rabbitmq_port,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )

    ultimo_erro = None
    for tentativa in range(1, max_retries + 1):
        try:
            return pika.BlockingConnection(parameters)
        except Exception as e:
            ultimo_erro = e
            if tentativa < max_retries:
                time.sleep(retry_interval)

    raise ConnectionError(f"Falha ao conectar no RabbitMQ: {ultimo_erro}")


def declarar_fila(channel, nome_fila: str, durable: bool = True) -> None:
    channel.queue_declare(queue=nome_fila, durable=durable, arguments={"x-max-priority": 10})
