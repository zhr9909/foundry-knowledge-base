@echo off
cd /d "E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\scripts"
echo Starting RAG Agent...
start "RAG Agent" python agent_rag.py
timeout /t 5 /nobreak >nul
echo Starting Orchestrator...
start "Orchestrator" python gateway.py
echo Done.
timeout /t 3 /nobreak >nul
