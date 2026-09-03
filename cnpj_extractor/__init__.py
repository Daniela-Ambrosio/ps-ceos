"""
CNPJ Extractor & Web Intelligence
=================================
Módulos organizados:
- cnpj_extractor.database: Gerenciamento do banco de dados SQLite, esquemas e repositório.
- cnpj_extractor.extraction: Cliente WebDAV/HTTP da Receita, stream reader e parsing CSV.
- cnpj_extractor.queue: Mensageria distribuída com RabbitMQ (Producer/Worker).
- cnpj_extractor.web: Interface visual com Streamlit.
"""

__version__ = "2.0.0"
