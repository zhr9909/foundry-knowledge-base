#!/usr/bin/env python3
"""Orchestrator Gateway (port 8000)"""

import os, sys, json, asyncio, logging
from pathlib import Path
from typing import Optional
import httpx

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

RAG_URL = "http://127.0.0.1:8001"
HOST = "0.0.0.0"
PORT = 8000
STATIC_DIR = _scripts_dir.parent / "app"
PDF_DIR = _scripts_dir.parent / "raw"

logging.basicConfig(level=logging.INFO, format='%(asctime)s [ORCH] %(message)s', datefmt='%H:%M:%S', force=True)
_log = logging.getLogger('orchestrator')

app = FastAPI(title="Foundry KB Orchestrator", version="0.3.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class ChatRequest(BaseModel):
    query: str
    search_results: list = []
    history: list = []
    section: Optional[str] = None

_client = None
async def _acall(method, url, **kwargs):
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    try:
        return await _client.request(method, url, **kwargs)
    except Exception:
        await _client.aclose()
        _client = httpx.AsyncClient()
        return await _client.request(method, url, **kwargs)

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
async def health():
    rag = "unknown"
    try:
        r = await _acall("get", f"{RAG_URL}/health", timeout=5)
        rag = r.json().get("status", "ok")
    except:
        rag = "unreachable"
    return {"status": "ok" if rag == "ok" else "degraded", "orchestrator": "0.3.0", "agents": {"rag": rag}}

@app.get("/sections")
async def get_sections():
    try:
        import psycopg2
        conn = psycopg2.connect(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")
        cur = conn.cursor()
        cur.execute("SELECT id, title, parent_id FROM document_sources ORDER BY parent_id, id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"sections": [{"id": r[0], "title": r[1], "parent_id": r[2]} for r in rows]}
    except Exception as e:
        _log.warning(f"Sections error: {e}")
        return {"sections": []}

@app.get("/search")
async def search(query: str = "", top_k: int = 10, section: str = None):
    if not query.strip():
        raise HTTPException(400, "query is required")
    try:
        r = await _acall("get", f"{RAG_URL}/search", params={"query": query, "top_k": top_k, "section": section}, timeout=30)
        return r.json()
    except Exception as e:
        _log.error(f"Search error: {e}")
        raise HTTPException(502, f"Search error: {str(e)}")

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        task = {"source": "orchestrator", "type": "chat",
                "input": {"query": req.query, "history": req.history or [], "section": req.section, "stream": False}}
        r = await _acall("post", f"{RAG_URL}/a2a/tasks", json=task, timeout=120)
        t = r.json()
        out = t.get("output", {})
        return {
            "answer": out.get("answer", t.get("error", {}).get("message", "")),
            "citations": out.get("citations", []),
            "search_results": [],
            "thinking": out.get("thinking", ""),
        }
    except Exception as e:
        _log.error(f"Chat error: {e}")
        return {"answer": f"Orchestrator error: {str(e)}", "citations": [], "search_results": [], "thinking": ""}

@app.get("/chat/stream")
@app.get("/chat/stream")
@app.get("/chat/stream")
async def chat_stream(query: str, section: str = None):
    """Proxy RAG Agent SSE stream (real-time)."""
    task = {"source": "orchestrator", "type": "chat",
            "input": {"query": query, "section": section, "stream": True}}
    async def event_gen():
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", f"{RAG_URL}/a2a/tasks", json=task) as resp:
                    evt = ""
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line: continue
                        if line.startswith("event: "):
                            evt = line[7:].strip()
                            continue
                        if line.startswith("data: "):
                            pl = line[6:].strip()
                            if not pl: continue
                            try: data = json.loads(pl)
                            except: continue
                            if evt == "task.result":
                                out = data.get("output", {})
                                ans = out.get("answer","")
                                cit = out.get("citations",[])
                                thi = out.get("thinking","")
                                payload = json.dumps({"type":"result","data":{"answer":ans,"citations":cit,"thinking":thi}}, ensure_ascii=False)
                                yield "data: " + payload + "\n\n"
                                yield 'data: {"type": "done"}\n\n'
                                return
                            elif evt == "task.error":
                                err = data.get("error",{}).get("message","?")
                                payload = json.dumps({"type":"error","message":err}, ensure_ascii=False)
                                yield "data: " + payload + "\n\n"
                                yield 'data: {"type": "done"}\n\n'
                                return
                            elif evt == "task.token":
                                payload = json.dumps({"type":"token","content":data.get("content","")}, ensure_ascii=False)
                                yield "data: " + payload + "\n\n"
                            elif evt == "task.status":
                                sd = data.get("data", {})
                                payload = json.dumps(sd, ensure_ascii=False)
                                yield "data: " + payload + "\n\n"
                            elif evt == "task.done":
                                yield 'data: {"type": "done"}\n\n'
                                return
                            else:
                                yield "data: " + pl + "\n\n"
        except Exception as e:
            _log.error(f"Stream error: {e}")
            payload = json.dumps({"type":"error","message":str(e)}, ensure_ascii=False)
            yield "data: " + payload + "\n\n"
        finally:
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/pdf/{source_id}")
async def serve_pdf(source_id: int):
    for p in PDF_DIR.glob("*.pdf"):
        if str(source_id) in p.name:
            return FileResponse(str(p), media_type="application/pdf")
    raise HTTPException(404, "PDF not found")

if __name__ == "__main__":
    print(f"[Orchestrator] Starting on {HOST}:{PORT}")
    print(f"[Orchestrator] RAG Agent: {RAG_URL}")
    uvicorn.run(app, host=HOST, port=PORT)
