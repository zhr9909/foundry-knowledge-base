@echo off
title Foundry KB
cd /d %~dp0
echo Starting RAG Agent...
start "RAG Agent" cmd /c "01_rag.bat"
ping -n 3 127.1 > nul
echo Starting Orchestrator...
start "Orchestrator" cmd /c "02_orchestrator.bat"
echo.
echo Both services started.
echo Wait 15s for model, then open: http://127.0.0.1:8000
echo.
echo Close this window - the service windows will keep running.
ping -n 3 127.1 > nul
