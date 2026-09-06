"""
Gerenciamento de Conexão e Filas com Dead-Letter no RabbitMQ (cnpj_extractor.queue.connection)
=============================================================================================
Gerencia conexões resilientes com RabbitMQ e declaração de filas com suporte a
prioridade (x-max-priority) e Dead-Letter Exchange (DLX) para mensagens venenosas.
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

    raise ConnectionError(f"Falha ao conectar no RabbitMQ ({cfg.rabbitmq_host}:{cfg.rabbitmq_port}): {ultimo_erro}")


def declarar_fila(channel, nome_fila: str, durable: bool = True) -> None:
    """
    Declara a fila principal com:
    - Prioridade de mensagens (x-max-priority: 10)
    - Dead-Letter Exchange (DLX) e Dead-Letter Queue (DLQ) para isolar mensagens com falha permanente.
    """
    dlx_name = f"{nome_fila}_dlx"
    dlq_name = f"{nome_fila}_dead_letter"

    # 1. Declara a exchange e a fila de Dead-Letter
    channel.exchange_declare(exchange=dlx_name, exchange_type="direct", durable=durable)
    channel.queue_declare(queue=dlq_name, durable=durable)
    channel.queue_bind(exchange=dlx_name, queue=dlq_name, routing_key=nome_fila)

    # 2. Declara a fila principal roteando rejeições definitivas para a DLX
    channel.queue_declare(
        queue=nome_fila,
        durable=durable,
        arguments={
            "x-max-priority": 10,
            "x-dead-letter-exchange": dlx_name,
            "x-dead-letter-routing-key": nome_fila,
        },
    )
