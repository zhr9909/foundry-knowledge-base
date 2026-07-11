#!/usr/bin/env python3
"""Orchestrator Gateway (port 8000)"""

import os, sys, json, asyncio, logging, mimetypes, mimetypes
from pathlib import Path
import hashlib
from typing import Optional
import httpx
from auth_handler import (
    init_auth_db, create_user, authenticate_user, create_session_token,
    get_current_user, require_user, create_verification_code,
    verify_code, send_verification_code,
    get_google_auth_url, google_login, validate_email,
    create_conversation, list_conversations, get_conv_messages,
    save_message, delete_conversation, update_conv_title,
    create_project, list_projects, get_project, update_project, save_project_artifact
)
from auth_handler import decode_token as _decode_jwt
from pydantic import BaseModel

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Direct import for SSE streaming (bypasses proxy buffering)
import agent as _agent

RAG_URL = "http://127.0.0.1:8001"
HOST = "0.0.0.0"
PORT = 8000
STATIC_DIR = _scripts_dir.parent / "app-vue" / "dist"
PDF_DIR = _scripts_dir.parent / "raw"

logging.basicConfig(level=logging.INFO, format='%(asctime)s [ORCH] %(message)s', datefmt='%H:%M:%S', force=True)
_log = logging.getLogger('orchestrator')

app = FastAPI(title="Foundry KB Orchestrator", version="0.3.0")
# Fix Windows MIME types
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

# Fix MIME types
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

from starlette.middleware.base import BaseHTTPMiddleware

class SSEHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            response.headers["Connection"] = "keep-alive"
        return response

app.add_middleware(SSEHeadersMiddleware)
 
class ChatRequest(BaseModel):
    query: str
    search_results: list = []
    history: list = []
    section: Optional[str] = None
    mode: Optional[str] = "qa"

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
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title, parent_id FROM document_sources ORDER BY parent_id, id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"sections": [{"id": r[0], "title": r[1], "parent_id": r[2]} for r in rows]}
    except Exception as e:
        _log.warning(f"Sections error: {e}")
        return {"sections": []}
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
                "input": {"query": req.query, "history": req.history or [], "section": req.section, "mode": req.mode or "qa", "stream": False}}
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
async def chat_stream(query: str, section: str = None, conv_id: str = None, token: str = None, history: str = None, mode: str = "qa", project_id: str = None):
    """Direct SSE from agent.py - no proxy, no buffering.
    Supports: token (JWT) for auth, conv_id for conversation tracking.
    """
    # Decode auth if token provided
    auth_user = None
    if token:
        payload = _decode_jwt(token)
        if payload:
            auth_user = {"id": int(payload["sub"]), "email": payload.get("email", "")}
    
    # Resolve conversation
    conversation_id = None
    user_saved = False
    answer_saved = False
    if auth_user:
        if conv_id and conv_id != "null" and conv_id != "undefined":
            try:
                c = get_conv_messages(int(conv_id), auth_user["id"])
                if c:
                    conversation_id = int(conv_id)
            except:
                pass
        if not conversation_id:
            # Auto-create conversation with first query as title
            title = query[:60] if len(query) > 60 else query
            c = create_conversation(auth_user["id"], title, project_id)
            conversation_id = c["id"]
            conv_id = str(conversation_id)
        
        # Save user message
        try:
            save_message(conversation_id, "user", query, {"mode": mode or "qa", "project_id": project_id})
            user_saved = True
        except Exception as e:
            _log.warning(f"Failed to save user message: {e}")
    
    async def event_gen():
        nonlocal answer_saved
        full_answer = ""
        full_citations = []
        full_graph = {}
        full_retrieval = {}
        full_mode = mode or "qa"
        full_structured_output = {}
        try:
            if conversation_id:
                yield f"data: {json.dumps({'type': 'conv_id', 'conv_id': conversation_id}, ensure_ascii=False)}\n\n"
            
            # Build history from conversation messages
            hist_from_conv = []
            request_history = []
            if history:
                try:
                    parsed_history = json.loads(history)
                    if isinstance(parsed_history, list):
                        for msg in parsed_history[-8:]:
                            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant") and msg.get("content"):
                                request_history.append({"role": msg["role"], "content": str(msg.get("content", ""))[:1200]})
                except Exception as e:
                    _log.warning(f"Invalid request history ignored: {e}")
            if conversation_id:
                try:
                    from auth_handler import get_conv_messages
                    cm = get_conv_messages(conversation_id, auth_user["id"])
                    if cm and cm.get("messages"):
                        for msg in cm["messages"][-10:]:
                            metadata = msg.get("metadata") or {}
                            msg_mode = metadata.get("mode") or "qa"
                            if msg_mode != full_mode:
                                continue
                            if msg.get("role") in ("user", "assistant"):
                                hist_from_conv.append({"role": msg["role"], "content": msg.get("content", "")})
                        if hist_from_conv and hist_from_conv[-1].get("role") == "user" and hist_from_conv[-1].get("content") == query:
                            hist_from_conv.pop()
                except Exception:
                    pass
            effective_history = request_history or hist_from_conv
            for event in _agent.stream_chat(query, section, history=effective_history if effective_history else None, mode=full_mode):
                if event is None:
                    continue
                etype = event.get("type", "")
                step = event.get("step", "")
                if etype == "result":
                    data = event.get("data", {})
                    full_answer = data.get("answer", "")
                    full_citations = data.get("citations", [])
                    full_graph = data.get("graph", {})
                    full_retrieval = data.get("retrieval", {})
                    full_mode = data.get("mode", full_mode)
                    full_structured_output = data.get("structured_output", {}) or {}
                    payload = json.dumps({"type": "result", "data": {"answer": full_answer, "citations": full_citations, "thinking": data.get("thinking",""), "graph": full_graph, "retrieval": full_retrieval, "mode": full_mode, "structured_output": full_structured_output}}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                    break
                elif etype == "error":
                    payload = json.dumps({"type": "error", "message": event.get("message","?")}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                    break
                elif step:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif etype == "log":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            _log.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            # Save assistant answer
            if auth_user and user_saved and full_answer and conversation_id:
                try:
                    save_message(conversation_id, "assistant", full_answer, {"citations": full_citations, "graph": full_graph, "retrieval": full_retrieval, "mode": full_mode, "structured_output": full_structured_output, "project_id": project_id})
                    answer_saved = True
                except Exception as e:
                    _log.warning(f"Failed to save assistant message: {e}")
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/pdf/{source_id}")
async def serve_pdf(source_id: int):
    for p in PDF_DIR.glob("*.pdf"):
        if str(source_id) in p.name:
            return FileResponse(str(p), media_type="application/pdf")
    raise HTTPException(404, "PDF not found")

@app.on_event("startup")
async def startup():
    init_auth_db()

    # ==================== Auth Routes ====================
class AuthRegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class AuthLoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/register")
async def auth_register(req: AuthRegisterRequest):
    if not validate_email(req.email):
        raise HTTPException(400, "邮箱格式不正确")
    if len(req.password) < 6:
        raise HTTPException(400, "密码长度至少6位")
    if not req.username.strip():
        raise HTTPException(400, "用户名不能为空")
    user = create_user(req.email, req.username, req.password)
    code = create_verification_code(user["id"])
    send_verification_code(req.email, code, req.username)
    session = create_session_token(user["id"], user["email"])
    return {"user": user, "token": session, "code": code, "message": "注册成功，请查收验证码"}

@app.post("/api/auth/login")
async def auth_login(req: AuthLoginRequest):
    if not req.email or not req.password:
        raise HTTPException(400, "请输入邮箱和密码")
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(401, "邮箱或密码错误")
    token = create_session_token(user["id"], user["email"])
    return {"user": user, "token": token}

@app.post("/api/auth/verify-code")
async def auth_verify_code(req: dict):
    email = req.get("email", "")
    code = req.get("code", "")
    if not email or not code:
        raise HTTPException(400, "缺少邮箱或验证码")
    success = verify_code(email, code)
    if not success:
        raise HTTPException(400, "验证码错误或已过期")
    return {"message": "验证成功"}

@app.post("/api/auth/resend-verification")
async def auth_resend_verification(user: dict = Depends(require_user)):
    token = create_verification_token(user["id"])
    send_verification_email(user["email"], token, user["username"])
    return {"message": "验证邮件已重新发送"}

@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"user": user}

@app.get("/api/auth/google/url")
async def auth_google_url():
    return {"url": get_google_auth_url()}

@app.get("/api/auth/google/callback")
async def auth_google_callback(code: str = ""):
    if not code:
        return RedirectResponse(url="/static/index.html?auth=fail")
    user = google_login(code)
    if not user:
        return RedirectResponse(url="/static/index.html?auth=fail")
    token = create_session_token(user["id"], user["email"])
    return RedirectResponse(url=f"/static/index.html?token={token}")

# ==================== Conversation History API ====================
@app.get("/api/conversations")
async def api_list_conversations(user: dict = Depends(require_user)):
    """List all conversations for the current user."""
    return {"conversations": list_conversations(user["id"])}

@app.post("/api/conversations")
async def api_create_conversation(req: Optional[dict] = None, user: dict = Depends(require_user)):
    """Create a new conversation."""
    req = req or {}
    c = create_conversation(user["id"], req.get("title", ""), req.get("project_id"))
    return {"conversation": c}

@app.get("/api/conversations/{conv_id}")
async def api_get_conversation(conv_id: int, user: dict = Depends(require_user)):
    """Get conversation with all messages."""
    c = get_conv_messages(conv_id, user["id"])
    if not c:
        raise HTTPException(404, "会话不存在")
    return {"conversation": c}

@app.put("/api/conversations/{conv_id}")
async def api_update_conversation(conv_id: int, req: dict, user: dict = Depends(require_user)):
    """Update conversation title."""
    title = req.get("title", "")
    ok = update_conv_title(conv_id, user["id"], title)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"message": "updated"}

@app.delete("/api/conversations/{conv_id}")
async def api_delete_conversation(conv_id: int, user: dict = Depends(require_user)):
    """Delete a conversation."""
    ok = delete_conversation(conv_id, user["id"])
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"message": "deleted"}

@app.post("/api/conversations/{conv_id}/messages")
async def api_save_message(conv_id: int, req: dict, user: dict = Depends(require_user)):
    """Save a message to a conversation."""
    role = req.get("role", "user")
    content = req.get("content", "")
    meta = req.get("metadata", {})
    msg = save_message(conv_id, role, content, meta)
    return {"message": msg}

# ==================== Project Workspace API ====================
@app.get("/api/projects")
async def api_list_projects(user: dict = Depends(require_user)):
    """List project workspaces for the current user."""
    return {"projects": list_projects(user["id"])}

@app.post("/api/projects")
async def api_create_project(req: dict, user: dict = Depends(require_user)):
    """Create a project workspace."""
    project = create_project(
        user["id"],
        req.get("name", ""),
        req.get("customer_name", ""),
        req.get("description", ""),
    )
    return {"project": project}

@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: int, user: dict = Depends(require_user)):
    """Get a project with saved artifacts."""
    project = get_project(project_id, user["id"])
    if not project:
        raise HTTPException(404, "项目不存在")
    return {"project": project}

@app.put("/api/projects/{project_id}")
async def api_update_project(project_id: int, req: dict, user: dict = Depends(require_user)):
    """Update project metadata."""
    project = update_project(
        user["id"],
        project_id,
        req.get("name") if "name" in req else None,
        req.get("customer_name") if "customer_name" in req else None,
        req.get("description") if "description" in req else None,
        req.get("status") if "status" in req else None,
    )
    if not project:
        raise HTTPException(404, "项目不存在")
    return {"project": project}

@app.post("/api/projects/{project_id}/artifacts")
async def api_save_project_artifact(project_id: int, req: dict, user: dict = Depends(require_user)):
    """Save an answer or workflow output into a project."""
    artifact = save_project_artifact(
        user["id"],
        project_id,
        req.get("type", "qa"),
        req.get("title", ""),
        req.get("content", ""),
        req.get("structured_data", {}),
        req.get("citations", []),
        req.get("metadata", {}),
    )
    return {"artifact": artifact}

if __name__ == "__main__":
    print(f"[Orchestrator] Starting on {HOST}:{PORT}")
    print(f"[Orchestrator] SSE: direct from agent.py (no proxy)")
    print(f"[Orchestrator] RAG Agent (search/chat POST): {RAG_URL}")
    uvicorn.run(app, host=HOST, port=PORT)
