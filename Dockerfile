FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data

COPY cnpj_extractor/ /app/cnpj_extractor/
COPY main.py .
COPY app.py .

VOLUME ["/app/data"]
EXPOSE 8501

CMD ["--help"]
