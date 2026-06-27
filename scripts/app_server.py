#!/usr/bin/env python3
"""app_server.py - FastAPI server with frontend + /chat endpoint."""
import os, sys, json, time
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from search import search, list_sections

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

# ── LLM Config ──
LLM_API = "http://127.0.0.1:15721/v1"
LLM_MODEL = "deepseek-v4-flash"
LLM_KEY = "PROXY_MANAGED"

app = FastAPI(title="铸造知识库", version="0.3.0")

# Serve frontend static files
app_dir = Path(__file__).parent.parent / "app"
app.mount("/static", StaticFiles(directory=str(app_dir)), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "db": "pgvector"}

@app.get("/sections")
def sections():
    return {"sections": list_sections()}

# ── Search endpoint ──
@app.get("/search")
def search_get(query: str = "", top_k: int = 10, hybrid: bool = True, section: Optional[str] = None):
    if not query.strip():
        raise HTTPException(400, "query is required")
    return search(query, top_k, hybrid, section)

# ── Chat endpoint ──
class ChatRequest(BaseModel):
    query: str
    search_results: Optional[list] = None
    history: Optional[list] = None
    section: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    search_results: list = []
    thinking: str = ""
    model: str = ""
    latency_ms: int = 0
    attempts: int = 1

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(400, "query is required")
    
    from agent import agent_chat
    
    result = agent_chat(req.query, section=req.section or None, history=req.history)
    
    return ChatResponse(
        answer=result.get("answer", ""),
        search_results=result.get("citations", []),
        thinking=result.get("thinking", ""),
        model=result.get("model", ""),
        latency_ms=result.get("latency_ms", 0),
        attempts=result.get("attempts", 1),
    )


if __name__ == "__main__":
    # Server started
    uvicorn.run(app, host="0.0.0.0", port=8002)

