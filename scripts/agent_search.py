#!/usr/bin/env python3
"""agent_search.py - Search Agent (port 8002) - retrieves context via A2A"""

import os, sys, json, time, uuid
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from a2a import AgentCard, Task, TaskStatus, TaskManager
import agent as _agent

HOST, PORT, AGENT_ID = "0.0.0.0", 8002, "search"
app = FastAPI(title="Search Agent", version="0.1.0")
task_manager = TaskManager()

AGENT_CARD = AgentCard(
    agent_id=AGENT_ID, name="Search Agent", version="0.1.0",
    description="Retrieves relevant context from the knowledge base.",
    capabilities=[{"id": "search", "name": "Search",
        "input": {"query": "string", "history": "array(optional)", "section": "string(optional)"},
        "output": {"context": "array", "sub_queries": "array"}}],
)

@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_ID}

@app.get("/a2a/card")
async def agent_card():
    return AGENT_CARD.to_dict()

@app.post("/a2a/tasks")
async def create_task(request: Request):
    body = await request.json()
    task = Task(task_id=body.get("task_id", f"srch_{uuid.uuid4().hex[:12]}"),
        source=body.get("source", "unknown"), target=AGENT_ID,
        type=body.get("type", "search"), input=body.get("input", {}),
        ttl_seconds=body.get("ttl_seconds", 120))
    task_manager.create_task(task)
    _process_search(task)
    return JSONResponse(task.to_dict())

@app.get("/a2a/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse(task.to_dict())

def _process_search(task: Task):
    start = time.time()
    query = task.input.get("query", "")
    history = task.input.get("history")
    section = task.input.get("section")

    try:
        task.status = TaskStatus.RUNNING
        # Rewrite query
        rw = _agent.rewrite_query(query, history)
        sub_queries = rw.get("search_queries", [query])

        # Search
        candidates = _agent.search_parallel(sub_queries, section, top_k=20)

        if not candidates:
            task.mark_completed({"context": [], "sub_queries": sub_queries})
            return

        # Select context (includes reranker)
        ctx = _agent.select_context(candidates, top_k=6,
            original_query=" ".join(sub_queries),
            search_query=sub_queries[0] if sub_queries else query)

        task.mark_completed({"context": ctx, "sub_queries": sub_queries})
    except Exception as e:
        task.mark_failed("SEARCH_ERROR", str(e))
    finally:
        task.metrics = {"total_ms": int((time.time() - start) * 1000)}

if __name__ == "__main__":
    print(f"[Search Agent] Starting on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
