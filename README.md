
## Requisitos

Docker e Docker Compose (plugin docker compose)

--- 
## Arquitetura
```bash
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  producer   │──1──▶│   RabbitMQ   │──2──▶│   worker(s) │──3──▶ PostgreSQL
│ (descobre e │      │ (fila com    │      │ (baixa, faz │        ▲
│  publica    │      │  prioridade  │      │  parse e    │        │
│  tarefas)   │      │  + DLQ)      │      │  UPSERT)    │        │
└─────────────┘      └──────────────┘      └─────────────┘        │
                                                                    │
┌──────────────────────────────────────────────────────────────────┘
│  web (Streamlit) — consulta o PostgreSQL diretamente, sem passar
│  pela fila
└─────────────────────────────────────────────────────────────────

```
---
## Para executar
```bash 
# 1. Clone o repositório
git clone https://github.com/Daniela-Ambrosio/ps-ceos

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Abra o .env e defina POSTGRES_PASSWORD e RABBITMQ_PASSWORD

# 3. Subir a aplicação
docker compose up -d --build

# 4. Escalar os workers para processar em paralelo
docker compose up -d --scale worker=4 worker


# 6. Para acessar a interface web
# http://localhost:8501