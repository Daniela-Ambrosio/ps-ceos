#!/usr/bin/env bash
echo "==================================================="
echo "🏢 Iniciando o Sistema de Consulta de CNPJs..."
echo "==================================================="

docker compose up -d web

echo ""
echo "✅ Interface Web iniciada com sucesso!"
echo "🌐 Abrindo o navegador em http://localhost:8501..."

if which xdg-open > /dev/null; then
    xdg-open "http://localhost:8501"
elif which open > /dev/null; then
    open "http://localhost:8501"
else
    echo "Acesse a interface no navegador: http://localhost:8501"
fi
