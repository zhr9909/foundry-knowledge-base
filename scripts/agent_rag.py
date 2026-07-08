#!/usr/bin/env python3
"""agent_rag.py - Independent RAG Agent Service (port 8001)"""

import os, sys, json, time, uuid
from pathlib import Path

# Ensure scripts/ is in path
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# ── FastAPI ──
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

# ── A2A Protocol ──
from a2a import (
    AgentCard, Task, TaskStatus, TaskManager,
    text_part, token_part, context_part, mermaid_part, comparison_part, error_part
)

# ── RAG Engine ──
# Import existing functions from agent.py
# These trigger search.py import which loads embedding model
import agent as _agent

LLM_API = _agent.LLM_API
LLM_MODEL = _agent.LLM_MODEL
LLM_KEY = _agent.LLM_KEY

# ── Config ──
HOST = "0.0.0.0"
PORT = 8001
AGENT_ID = "rag"

# ── App ──
app = FastAPI(title="RAG Agent", version="0.1.0")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# ── Task Manager ──
task_manager = TaskManager()

# ── Agent Card ──
AGENT_CARD = AgentCard(
    agent_id=AGENT_ID,
    name="RAG Knowledge Base Agent",
    version="0.1.0",
    description="Based on ASM Handbooks, supports natural language search of technical documents.",
    capabilities=[
        {"id": "chat", "name": "Knowledge QA",
         "input": {"query": "string", "history": "array(optional)", "stream": "boolean(optional)"},
         "output": {"answer": "string", "citations": "array"}},
        {"id": "search", "name": "Knowledge Retrieval",
         "input": {"query": "string", "top_k": "int"},
         "output": {"results": "array"}},
    ],
)


# ════════════════════════════════
#  Endpoints
# ════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_ID, "version": "0.1.0"}


@app.get("/a2a/card")
async def agent_card():
    return AGENT_CARD.to_dict()


@app.post("/a2a/tasks")
async def create_task(request: Request):
    body = await request.json()
    task_id = body.get("task_id", f"rag_{uuid.uuid4().hex[:12]}")

    task = Task(
        task_id=task_id,
        source=body.get("source", "unknown"),
        target=AGENT_ID,
        type=body.get("type", "chat"),
        input=body.get("input", {}),
        stream=body.get("input", {}).get("stream", False),
        ttl_seconds=body.get("ttl_seconds", 120),
    )
    task_manager.create_task(task)

    if task.stream:
        return StreamingResponse(_task_stream(task), media_type="text/event-stream")
    else:
        _process_task(task)
        return JSONResponse(task.to_dict())


@app.get("/a2a/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return JSONResponse({"error": {"code": "TASK_NOT_FOUND", "message": "Task not found"}}, status_code=404)
    return JSONResponse(task.to_dict())


@app.delete("/a2a/tasks/{task_id}")
async def cancel_task(task_id: str):
    task = task_manager.cancel_task(task_id)
    if not task:
        return JSONResponse({"error": {"code": "TASK_NOT_FOUND", "message": "Task not found"}}, status_code=404)
    return JSONResponse(task.to_dict())


@app.get("/search")
async def search_get(query: str = "", top_k: int = 10, section: str = None):
    from search import search
    if not query.strip():
        return JSONResponse({"error": "query is required"}, status_code=400)

@app.get("/chat/stream")
async def chat_stream_get(query: str, section: str = None):
    """Direct SSE - strips event: headers for browser."""
    async def _event_gen():
        try:
            for event in _agent.stream_chat(query, section):
                etype = event.get("type", "")
                step = event.get("step", "")
                if etype == "result":
                    d = event.get("data", {})
                    p = json.dumps({"type":"result","data":{"answer":d.get("answer",""),"citations":d.get("citations",[]),"thinking":d.get("thinking","")}}, ensure_ascii=False)
                    yield "data: " + p + "\n\n"
                    yield 'data: {"type": "done"}\n\n'
                    return
                elif etype == "error":
                    p = json.dumps({"type":"error","message":event.get("message","?")}, ensure_ascii=False)
                    yield "data: " + p + "\n\n"
                    yield 'data: {"type": "done"}\n\n'
                    return
                elif step:
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                elif etype == "log":
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"type":"error","message":str(e)}, ensure_ascii=False) + "\n\n"
        finally:
            yield 'data: {"type": "done"}\n\n'
    return StreamingResponse(_event_gen(), media_type="text/event-stream")
# ════════════════════════════════
#  Task Processing
# ════════════════════════════════

def _process_task(task: Task):
    """Process a chat task: rewrite -> search -> select_ctx -> generate."""
    start = time.time()
    query = task.input.get("query", "")
    history = task.input.get("history")
    section = task.input.get("section")

    task.status = TaskStatus.RUNNING
    try:
        # Step 1: Rewrite
        task.status = TaskStatus.REWRITING
        rw = _agent.rewrite_query(query, history)
        sub_queries = rw.get("search_queries", [query])

        # Step 2: Search
        task.status = TaskStatus.SEARCHING
        candidates = _agent.search_parallel(sub_queries, section, top_k=20)

        if not candidates:
            task.mark_completed({
                "answer": "The knowledge base does not contain relevant information.",
                "citations": [],
                "thinking": "",
            })
            return

        # Step 3: Select context (includes reranker)
        ctx = _agent.select_context(
            candidates, top_k=6,
            original_query=" ".join(sub_queries),
            search_query=sub_queries[0] if sub_queries else query,
        )

        # Step 4: Generate
        task.status = TaskStatus.GENERATING
        result = _agent.generate_answer(query, ctx, history)

        task.mark_completed({
            "answer": result.get("answer", ""),
            "citations": result.get("citations", ctx),
            "thinking": result.get("thinking", ""),
        })

    except Exception as e:
        task.mark_failed("RAG_PROCESS_ERROR", str(e))

    finally:
        elapsed = int((time.time() - start) * 1000)
        task.metrics = {"total_ms": elapsed}


async def _task_stream(task: Task):
    """Stream SSE events for a chat task."""
    query = task.input.get("query", "")
    section = task.input.get("section")

    def _progress(event):
        task_manager.update_task(task.task_id, status=TaskStatus.RUNNING)

    try:
        for event in _agent.stream_chat(query, section):
            etype = event.get("type", "")
            if etype == "token":
                yield f"event: task.token\ndata: {json.dumps({'task_id': task.task_id, 'content': event['content']}, ensure_ascii=False)}\n\n"
            elif etype == "result":
                data = event.get("data", {})
                task.mark_completed(data)
                yield f"event: task.result\ndata: {json.dumps(task.to_dict(), ensure_ascii=False)}\n\n"
            elif etype == "error":
                task.mark_failed("RAG_STREAM_ERROR", event.get("message", ""))
                yield f"event: task.error\ndata: {json.dumps(task.to_dict(), ensure_ascii=False)}\n\n"
            else:
                # Progress events (rewritten, searched, context_ready, checked)
                yield f"event: task.status\ndata: {json.dumps({'task_id': task.task_id, 'status': etype, 'data': event}, ensure_ascii=False)}\n\n"
    except Exception as e:
        task.mark_failed("RAG_STREAM_ERROR", str(e))
        yield f"event: task.error\ndata: {json.dumps(task.to_dict(), ensure_ascii=False)}\n\n"
    finally:
        yield "event: task.done\ndata: {}\n\n"


# ════════════════════════════════
#  Main
# ════════════════════════════════

if __name__ == "__main__":
    print(f"[RAG Agent] Starting on {HOST}:{PORT}")
    print(f"[RAG Agent] Agent Card: GET http://127.0.0.1:{PORT}/a2a/card")
    print(f"[RAG Agent] Create Task: POST http://127.0.0.1:{PORT}/a2a/tasks")
    uvicorn.run(app, host=HOST, port=PORT)
