@echo off
title Sistema de Consulta de CNPJ - Receita Federal
echo ===================================================
echo 🏢 Iniciando o Sistema de Consulta de CNPJs...
echo ===================================================

docker compose up -d web

echo.
echo ✅ Interface Web iniciada com sucesso!
echo 🌐 Abrindo o navegador em http://localhost:8501...
timeout /t 2 >nul
start http://localhost:8501
pause
