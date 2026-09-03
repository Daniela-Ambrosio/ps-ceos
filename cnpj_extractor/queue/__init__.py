"""
Subpacote de Mensageria e Filas RabbitMQ (cnpj_extractor.queue)
==============================================================
"""

from .connection import obter_conexao_rabbitmq
from .producer import TaskProducer
from .worker import TaskWorker

__all__ = ["obter_conexao_rabbitmq", "TaskProducer", "TaskWorker"]
