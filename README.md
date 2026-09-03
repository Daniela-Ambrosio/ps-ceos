# 🚀 CNPJ Streamer & Plataforma de Consulta Web

> **Coletor em Streaming e Interface Web de Consulta dos Dados Abertos de CNPJ da Receita Federal**  
> Arquitetura modular limpa com separação por responsabilidades: **Banco de Dados**, **Extração/Parsing** e **Interface Web**.

---

## 🏛️ Arquitetura Modular do Projeto

O projeto é estruturado seguindo o princípio da **responsabilidade única (SRP)**:

```text
ps-ceos/
│
├── cnpj_extractor/
│   ├── database/                 # 💾 MÓDULO 1: BANCO DE DADOS
│   │   ├── connection.py         # Conexão SQLite (WAL mode, busy_timeout, pragmas)
│   │   ├── schema.py             # DDLs, tabelas autorizadas (whitelist), índices e mapeamentos
│   │   ├── repository.py         # Prepared Statements, inserção em lotes e consultas seguras
│   │   └── manager.py            # Fachada DatabaseManager
│   │
│   ├── extraction/               # ⚡ MÓDULO 2: EXTRAÇÃO E PARSING
│   │   ├── client.py             # Cliente WebDAV / HTTP da Receita Federal
│   │   ├── stream_reader.py      # Descompressão Deflate em streaming contínuo de ZIP (on-the-fly)
│   │   ├── parser.py             # Parser CSV com sanitização, normalização e filtros por UF
│   │   └── pipeline.py           # Orquestrador do fluxo de carga (Client -> Stream -> Parser -> DB)
│   │
│   ├── web/                      # 🌐 MÓDULO 3: INTERFACE WEB (Streamlit)
│   │   ├── components.py         # Formatadores (CNPJ, R$, datas), badges e estilos CSS
│   │   └── views.py              # Telas e abas (Busca por CNPJ, Busca por Filtros, Sidebar)
│   │
│   ├── queue/                    # 🐰 MÓDULO 4: FILAS DISTRIBUÍDAS (RabbitMQ)
│   │   ├── connection.py         # Conexão e retry do RabbitMQ
│   │   ├── producer.py           # Despacho ordenado de tarefas
│   │   └── worker.py             # Processamento paralelo de arquivos
│   │
│   ├── config.py                 # Configurações centralizadas (.env, caminhos, defaults)
│   └── cli.py                    # Interface de linha de comando
│
├── app.py                        # Ponto de entrada da interface web (Streamlit)
├── main.py                       # Ponto de entrada da CLI
├── Dockerfile                    # Container Docker otimizado
├── docker-compose.yml            # Orquestração de serviços (Web, RabbitMQ, Worker, Producer)
├── iniciar.bat / iniciar.sh      # Inicializadores de 1-Clique para usuários finais
└── tests/                        # 🧪 Suíte completa de testes unitários
    ├── test_config.py
    ├── test_database.py
    ├── test_extraction.py
    ├── test_queue.py
    └── test_web.py
```

---

## 🌐 Como Usar a Interface Web

### Opção 1: Inicialização em 1 Clique (Mais Fácil para Usuários)
* **No Windows:** Dê dois cliques em **`iniciar.bat`**.
* **No Linux / macOS:** Execute **`./iniciar.sh`**.
* O navegador abrirá automaticamente em **`http://localhost:8501`**.

---

### Opção 2: Com Docker Compose
```bash
docker compose up -d web
```
Acesse no navegador: **`http://localhost:8501`**

---

### Opção 3: Executar Diretamente com Python
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 💻 Comandos da Linha de Comando (CLI)

```bash
# Ingestão padrão (todas as tabelas)
python main.py

# Ingestão apenas das tabelas de domínio (CNAE, Municípios, etc.)
python main.py --tables lookup

# Ingestão com filtro por UF (apenas SP)
python main.py --tables empresas,estabelecimentos --uf SP

# Consultar CNPJ no terminal
python main.py --search-cnpj 00000000

# Executar como Produtor de Fila (RabbitMQ)
python main.py --mode producer --tables all

# Executar como Worker (RabbitMQ)
python main.py --mode worker
```

---

## 🧪 Testes Automatizados

```bash
python -m unittest discover tests
```
