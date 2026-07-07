#!/usr/bin/env python3
"""gateway.py - API Gateway (port 8000) - routes via A2A protocol"""

import os, sys, json, asyncio, httpx
from pathlib import Path
from typing import Optional

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

HOST = "0.0.0.0"
PORT = 8000
RAG_AGENT_URL = "http://127.0.0.1:8001"
STATIC_DIR = _scripts_dir.parent / "app"

app = FastAPI(title="API Gateway", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class ChatRequest(BaseModel):
    query: str
    search_results: list = []
    history: list = []
    section: Optional[str] = None

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
async def health():
    try:
        r = httpx.get(f"{RAG_AGENT_URL}/health", timeout=5)
        rag = r.json()
        return {"status": "ok", "gateway": "0.1.0", "agents": {"rag": rag["status"]}}
    except:
        return {"status": "degraded", "agents": {"rag": "unreachable"}}

@app.get("/sections")
async def get_sections():
    try:
        import psycopg2
        conn = psycopg2.connect(**{"host": "127.0.0.1", "port": 15432, "dbname": "foundry_kb", "user": "findmyjob", "password": "findmyjob_dev_password"})
        cur = conn.cursor()
        cur.execute("SELECT id, title, parent_id FROM document_sources ORDER BY parent_id, id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"sections": [{"id": r[0], "title": r[1], "parent_id": r[2]} for r in rows]}
    except:
        return {"sections": []}

@app.get("/search")
async def search(query: str = "", top_k: int = 10, section: str = None):
    if not query.strip():
        raise HTTPException(400, "query is required")
    try:
        r = httpx.get(f"{RAG_AGENT_URL}/search", params={"query": query, "top_k": top_k}, timeout=30)
        return r.json()
    except Exception as e:
        raise HTTPException(502, f"RAG Agent error: {str(e)}")

@app.post("/chat")
async def chat(req: ChatRequest):
    task = {"source": "gateway", "type": "chat", "ttl_seconds": 120,
            "input": {"query": req.query, "history": req.history or [], "stream": False}}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{RAG_AGENT_URL}/a2a/tasks", json=task)
            if r.status_code != 200:
                return {"answer": f"Agent error (HTTP {r.status_code})", "citations": []}
            t = r.json()
            if t.get("status") == "completed":
                out = t.get("output", {})
                return {"answer": out.get("answer", ""), "citations": out.get("citations", []), "search_results": [], "thinking": ""}
            elif t.get("status") == "failed":
                return {"answer": f"Error: {t.get('error', {}).get('message', '?')}", "citations": []}
            return {"answer": "Processing...", "citations": []}
    except Exception as e:
        return {"answer": f"Gateway error: {str(e)}", "citations": []}

@app.get("/chat/stream")
async def chat_stream(query: str, section: str = None):
    task = {"source": "gateway", "type": "chat", "ttl_seconds": 120,
            "input": {"query": query, "section": section, "stream": True}}
    async def event_gen():
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", f"{RAG_AGENT_URL}/a2a/tasks", json=task) as resp:
                    evt = ""
                    async for line in resp.aiter_lines():
                        if not line: continue
                        if line.startswith("event: "):
                            evt = line[7:].strip()
                            continue
                        if line.startswith("data: "):
                            pl = line[6:].strip()
                            if not pl: continue
                            try:
                                data = json.loads(pl)
                            except:
                                continue
                            if evt == "task.result":
                                out = data.get("output", {})
                                yield "data: " + json.dumps({"type": "result", "data": {"answer": out.get("answer",""), "citations": out.get("citations",[])}}, ensure_ascii=False) + "\n\n"
                            elif evt == "task.error":
                                yield "data: " + json.dumps({"type": "error", "message": data.get("error",{}).get("message","?")}, ensure_ascii=False) + "\n\n"
                            elif evt == "task.status":
                                sd = data.get("data", {})
                                step = sd.get("step") or data.get("status","")
                                if step in ("rewritten","searched","context_ready","checked"):
                                    yield "data: " + json.dumps(sd, ensure_ascii=False) + "\n\n"
                                elif sd.get("type") == "log":
                                    yield "data: " + json.dumps(sd, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n\n"
        finally:
            yield 'data: {"type": "done"}\n\n'
    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/pdf/{source_id}")
async def serve_pdf(source_id: int):
    pdf_dir = _scripts_dir.parent / "raw"
    for p in pdf_dir.glob("*.pdf"):
        if str(source_id) in p.name:
            return FileResponse(str(p), media_type="application/pdf")
    raise HTTPException(404, "PDF not found")

if __name__ == "__main__":
    print(f"[Gateway] Starting on {HOST}:{PORT}")
    print(f"[Gateway] RAG Agent: {RAG_AGENT_URL}")
    uvicorn.run(app, host=HOST, port=PORT)