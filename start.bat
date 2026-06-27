@echo off
cd /d E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base
start /B python scripts\app_server.py > logs\server_startup.log 2>&1
echo Server PID: %ERRORLEVEL%
