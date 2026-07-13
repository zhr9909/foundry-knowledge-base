#!/usr/bin/env python3
"""Orchestrator Gateway (port 8000)"""

import os, sys, json, asyncio, logging, mimetypes, mimetypes, re, html, base64, io, zipfile
from pathlib import Path
import hashlib
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import quote
import httpx
from auth_handler import (
    init_auth_db, create_user, authenticate_user, create_session_token,
    get_current_user, require_user, create_verification_code,
    verify_code, send_verification_code,
    get_google_auth_url, google_login, validate_email,
    create_conversation, list_conversations, get_conv_messages,
    save_message, delete_conversation, update_conv_title,
    create_project, list_projects, get_project, update_project, save_project_artifact,
    list_evidence_cards, create_evidence_card, update_evidence_card, delete_evidence_card,
    list_engineering_documents, create_engineering_document, attach_artifact_to_engineering_document
)
from auth_handler import decode_token as _decode_jwt
from pydantic import BaseModel

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from storage import build_object_key, get_object_store, object_hash, safe_name
from document_parser import build_document_chunks, parse_document

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, Response
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

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 15432,
    "dbname": "foundry_kb",
    "user": "findmyjob",
    "password": "findmyjob_dev_password",
}

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

PROJECT_BRIEF_PROMPT = """你是材料铸造行业的解决方案工程师，正在为一个客户项目生成内部评审/客户沟通用的项目简报。

请基于输入的项目上下文生成一份中文 Markdown 简报。要求：
1. 不要编造没有依据的具体数值；没有信息时写“待确认”。
2. 保留关键引用线索，例如 pg.399、pg.3204 等。
3. 语言要像工程方案文档，不要像聊天回复。
4. 结构必须包含以下标题：
   # 项目简报
   ## 1. 项目背景
   ## 2. 客户需求与约束
   ## 3. 已确认工况
   ## 4. 候选材料 / 工艺路线
   ## 5. 选型对比结论
   ## 6. 主要风险与待确认项
   ## 7. 推荐方案
   ## 8. 验证计划
   ## 9. 引用依据
"""

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

_STREAM_DONE = object()

def _next_stream_event(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return _STREAM_DONE

def _brief_text(value, limit=900):
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
    text = " ".join(text.split())
    return text[:limit]

def _report_evidence_cards(project):
    cards = project.get("evidence_cards") or []
    return [card for card in cards if card.get("usable_in_report")]

def _evidence_card_line(card, idx=None):
    prefix = f"证据 {idx}：" if idx is not None else ""
    page = card.get("page") or "?"
    title = card.get("title") or "未命名证据"
    reliability = card.get("reliability") or "medium"
    quote_text = _brief_text(card.get("quote"), 520)
    note = _brief_text(card.get("note"), 260)
    tags = "、".join(str(tag) for tag in (card.get("tags") or [])[:5])
    parts = [
        f"{prefix}{title}",
        f"- 页码：pg.{page}",
        f"- 类型：{card.get('evidence_type') or 'general'}",
        f"- 可靠性：{reliability}",
    ]
    if tags:
        parts.append(f"- 标签：{tags}")
    if quote_text:
        parts.append(f"- 原文片段：{quote_text}")
    if note:
        parts.append(f"- 工程师备注：{note}")
    return "\n".join(parts)

def _collect_project_brief_context(project):
    artifacts = project.get("artifacts") or []
    conversations = project.get("conversations") or []
    report_evidence = _report_evidence_cards(project)
    chunks = [
        f"项目名称：{project.get('name') or '未命名项目'}",
        f"客户名称：{project.get('customer_name') or '待确认'}",
        f"项目描述：{project.get('description') or '待补充'}",
        f"项目状态：{project.get('status') or 'active'}",
        "",
        "【项目内对话】",
    ]
    for conv in conversations[:8]:
        chunks.append(f"- {conv.get('title') or '新对话'}（更新时间：{conv.get('updated_at') or ''}）")
    chunks.append("")
    chunks.append("【已保存项目产物】")
    for idx, artifact in enumerate(artifacts[:18], 1):
        citations = artifact.get("citations") or []
        pages = []
        for c in citations[:6]:
            page = c.get("page") or "?"
            section = c.get("section") or ""
            pages.append(f"pg.{page} {section}".strip())
        chunks.extend([
            f"\n产物 {idx}：{artifact.get('title') or '未命名产物'}",
            f"- 类型：{artifact.get('type') or 'qa'}",
            f"- 正文摘要：{_brief_text(artifact.get('content'), 1100)}",
            f"- 结构化数据：{_brief_text(artifact.get('structured_data'), 1100)}",
            f"- 引用线索：{'；'.join(pages) if pages else '无'}",
        ])
    chunks.append("")
    chunks.append("【已选择报告证据】")
    if report_evidence:
        chunks.append("以下证据由工程师标记为可用于报告，生成简报时必须优先使用。")
        for idx, card in enumerate(report_evidence[:18], 1):
            chunks.append(_evidence_card_line(card, idx))
    else:
        chunks.append("暂无工程师确认的报告证据。可参考项目产物中的引用线索，但需要在简报中标注为待确认。")
    return "\n".join(chunks)[:18000]

def _fallback_project_brief(project):
    artifacts = project.get("artifacts") or []
    conversations = project.get("conversations") or []
    report_evidence = _report_evidence_cards(project)
    types = {a.get("type") for a in artifacts}
    stage = "项目初始化"
    if "defect_diagnosis" in types:
        stage = "现场诊断 / 风险闭环"
    elif "selection_matrix" in types:
        stage = "选型决策"
    elif "solution_draft" in types:
        stage = "方案形成"
    elif "requirement_clarification" in types:
        stage = "需求澄清"
    elif "qa" in types or conversations:
        stage = "资料检索"
    citation_pages = []
    if report_evidence:
        for card in report_evidence[:12]:
            citation_pages.append(
                f"pg.{card.get('page') or '?'} {card.get('title') or card.get('section') or '已确认证据'}"
                + (f"：{_brief_text(card.get('summary') or card.get('quote'), 140)}" if (card.get('summary') or card.get('quote')) else "")
            )
    else:
        for artifact in artifacts:
            for c in (artifact.get("citations") or [])[:3]:
                citation_pages.append(f"pg.{c.get('page') or '?'} {c.get('section') or ''}".strip())
    citation_pages = list(dict.fromkeys(citation_pages))[:12]
    artifact_lines = [f"- {a.get('title') or '未命名产物'}（{a.get('type') or 'qa'}）" for a in artifacts[:8]]
    return "\n".join([
        "# 项目简报",
        "",
        "## 1. 项目背景",
        f"- 项目名称：{project.get('name') or '未命名项目'}",
        f"- 客户名称：{project.get('customer_name') or '待确认'}",
        f"- 当前阶段：{stage}",
        "",
        "## 2. 客户需求与约束",
        f"- {project.get('description') or '待从后续需求澄清中补充。'}",
        "",
        "## 3. 已确认工况",
        "- 待从项目对话和需求澄清结果中进一步确认。",
        "",
        "## 4. 候选材料 / 工艺路线",
        "\n".join(artifact_lines) if artifact_lines else "- 暂无已保存方案产物。",
        "",
        "## 5. 选型对比结论",
        "- 待生成或保存选型矩阵后补充。",
        "",
        "## 6. 主要风险与待确认项",
        "- 待从方案草案、选型矩阵和缺陷诊断中补充。",
        "",
        "## 7. 推荐方案",
        "- 当前信息不足，建议继续补充需求澄清、知识依据和选型矩阵。",
        "",
        "## 8. 验证计划",
        "- 建议补充关键性能指标、工况边界、样件验证和引用依据后形成验证计划。",
        "",
        "## 9. 引用依据",
        "\n".join([f"- {item}" for item in citation_pages]) if citation_pages else "- 暂无引用依据。",
    ])

def _project_brief_citations(project):
    seen = set()
    result = []
    report_evidence = _report_evidence_cards(project)
    for card in report_evidence:
        metadata = card.get("metadata") or {}
        citation = {
            "source_id": card.get("document_id") or metadata.get("source_id") or 2,
            "page": card.get("page"),
            "section": card.get("section") or card.get("title") or "已确认证据",
            "text": card.get("quote") or card.get("summary") or "",
            "source_type": metadata.get("source_type") or "standard_manual",
            "evidence_level": metadata.get("evidence_level") or "confirmed",
            "evidence_card_id": card.get("id"),
        }
        key = (citation.get("source_id"), citation.get("page"), citation.get("text"))
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
        if len(result) >= 20:
            return result
    if result:
        return result
    for artifact in project.get("artifacts") or []:
        for c in artifact.get("citations") or []:
            key = (c.get("source_id"), c.get("page"), c.get("text"))
            if key in seen:
                continue
            seen.add(key)
            result.append(c)
            if len(result) >= 20:
                return result
    return result

def _safe_report_filename(value):
    name = re.sub(r'[\\/:*?"<>|]+', "_", str(value or "project-artifact")).strip(" ._")
    return (name or "project-artifact")[:80]

def _render_inline_markdown(text):
    code_parts = []

    def stash_code(match):
        code_parts.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00CODE{len(code_parts) - 1}\x00"

    result = re.sub(r"`([^`]+)`", stash_code, html.escape(str(text or "")))
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    result = result.replace("\n", "<br>")

    def restore_code(match):
        idx = int(match.group(1))
        return code_parts[idx] if idx < len(code_parts) else ""

    return re.sub(r"\x00CODE(\d+)\x00", restore_code, result)

def _is_markdown_table_start(lines, index):
    if index + 1 >= len(lines):
        return False
    current = lines[index].strip()
    sep = lines[index + 1].strip()
    return (
        current.startswith("|") and current.endswith("|")
        and re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", sep)
    )

def _render_markdown_table(table_lines):
    rows = []
    for i, line in enumerate(table_lines):
        if i == 1:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return ""
    head = "".join(f"<th>{_render_inline_markdown(cell)}</th>" for cell in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{_render_inline_markdown(cell)}</td>" for cell in row) + "</tr>"
        for row in rows[1:]
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

def _render_markdown_html(markdown):
    lines = str(markdown or "").replace("\r\n", "\n").split("\n")
    blocks = []
    paragraph = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{_render_inline_markdown(chr(10).join(paragraph))}</p>")
            paragraph = []

    i = 0
    while i < len(lines):
        line = lines[i]
        trimmed = line.strip()
        if not trimmed:
            flush_paragraph()
            i += 1
            continue
        if trimmed.startswith("```"):
            flush_paragraph()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            i += 1
            continue
        if _is_markdown_table_start(lines, i):
            flush_paragraph()
            table_lines = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i])
                i += 1
            blocks.append(_render_markdown_table(table_lines))
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", trimmed)
        if heading:
            flush_paragraph()
            level = min(len(heading.group(1)) + 1, 5)
            blocks.append(f"<h{level}>{_render_inline_markdown(heading.group(2))}</h{level}>")
            i += 1
            continue
        if re.match(r"^[-*]\s+", trimmed):
            flush_paragraph()
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            blocks.append("<ul>" + "".join(f"<li>{_render_inline_markdown(item)}</li>" for item in items) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", trimmed):
            flush_paragraph()
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            blocks.append("<ol>" + "".join(f"<li>{_render_inline_markdown(item)}</li>" for item in items) + "</ol>")
            continue
        paragraph.append(line)
        i += 1

    flush_paragraph()
    return "\n".join(blocks)

def _artifact_report_html(project, artifact):
    citations = artifact.get("citations") or []
    citation_html = "".join(
        "<li>"
        f"<strong>pg.{html.escape(str(c.get('page') or '?'))}</strong>"
        f"<span>{html.escape(str(c.get('section') or '引用依据'))}</span>"
        f"<p>{html.escape(str(c.get('text') or ''))}</p>"
        "</li>"
        for c in citations
    ) or "<li>暂无引用来源。</li>"
    structured = artifact.get("structured_data") or {}
    structured_html = ""
    if isinstance(structured, dict) and structured:
        structured_html = (
            "<section><h2>结构化数据</h2><pre><code>"
            + html.escape(json.dumps(structured, ensure_ascii=False, indent=2))
            + "</code></pre></section>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(str(artifact.get("title") or "项目产物"))}</title>
  <style>
    @page {{ size: A4; margin: 18mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #0f172a;
      background: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
      line-height: 1.72;
      font-size: 14px;
    }}
    header {{ border-bottom: 2px solid #0f766e; padding-bottom: 14px; margin-bottom: 22px; }}
    .kicker {{ color: #0f766e; font-size: 11px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }}
    h1 {{ margin: 6px 0 8px; font-size: 26px; line-height: 1.28; }}
    h2 {{ margin: 22px 0 8px; font-size: 18px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
    h3 {{ margin: 18px 0 8px; font-size: 16px; }}
    h4, h5 {{ margin: 14px 0 6px; font-size: 14px; }}
    h2, h3, h4, h5 {{ break-after: avoid; color: #0f172a; line-height: 1.35; }}
    p {{ margin: 0 0 10px; word-break: break-word; }}
    strong {{ color: #0f172a; font-weight: 760; }}
    .meta {{ color: #64748b; display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; }}
    code {{ border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; color: #0f766e; padding: 1px 4px; font-family: "Cascadia Mono", Consolas, monospace; font-size: .9em; }}
    pre {{ margin: 10px 0 12px; border: 1px solid #cbd5e1; border-radius: 8px; background: #f8fafc; padding: 10px 12px; white-space: pre-wrap; word-break: break-word; }}
    pre code {{ border: 0; background: transparent; color: inherit; padding: 0; font-size: 12px; line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 16px; break-inside: avoid; font-size: 12px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; color: #0f172a; font-weight: 760; }}
    ul, ol {{ margin: 0 0 12px; padding-left: 22px; }}
    li {{ break-inside: avoid; margin: 0 0 6px; }}
    .citations li {{ margin-bottom: 10px; }}
    .citations strong {{ color: #0f766e; margin-right: 8px; }}
    .citations span {{ color: #475569; font-weight: 650; }}
    .citations p {{ margin: 4px 0 0; color: #334155; }}
  </style>
</head>
<body>
  <header>
    <div class="kicker">Foundry Knowledge Base · Project Artifact</div>
    <h1>{html.escape(str(artifact.get("title") or "未命名产物"))}</h1>
    <div class="meta">
      <span>项目：{html.escape(str(project.get("name") or "未命名项目"))}</span>
      <span>类型：{html.escape(str(artifact.get("type") or "项目产物"))}</span>
      <span>创建时间：{html.escape(str(artifact.get("created_at") or "未知"))}</span>
    </div>
  </header>
  <section>
    <h2>正文</h2>
    {_render_markdown_html(artifact.get("content") or "暂无正文内容。")}
  </section>
  {structured_html}
  <section class="citations">
    <h2>引用来源</h2>
    <ul>{citation_html}</ul>
  </section>
</body>
</html>"""

async def _artifact_pdf_bytes(project, artifact):
    from playwright.async_api import async_playwright

    report_html = _artifact_report_html(project, artifact)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(report_html, wait_until="load")
            return await page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "18mm", "right": "18mm", "bottom": "18mm", "left": "18mm"},
            )
        finally:
            await browser.close()

def _extract_docx_text(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as docx:
            document_xml = docx.read("word/document.xml")
    except Exception:
        return ""
    try:
        root = ET.fromstring(document_xml)
    except Exception:
        return ""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for para in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in para.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)

def _decode_text_bytes(data):
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")

def _extract_text_from_upload(filename, data, mime_type=""):
    lower = str(filename or "").lower()
    if lower.endswith(".docx") or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(data)
    if lower.endswith((".txt", ".md", ".markdown", ".csv")) or str(mime_type or "").startswith("text/"):
        return _decode_text_bytes(data)
    return ""

def _parse_uploaded_document(filename, data, mime_type=""):
    parsed = parse_document(filename, data, mime_type)
    if not isinstance(parsed, dict):
        return {
            "parser": "unknown",
            "parse_status": "stored",
            "text": _extract_text_from_upload(filename, data, mime_type),
            "markdown": "",
            "blocks": [],
            "tables": [],
            "images": [],
            "outline": [],
            "statistics": {},
        }
    if not parsed.get("text"):
        parsed["text"] = _extract_text_from_upload(filename, data, mime_type)
    return parsed

def _clean_lines(text):
    return [line.strip() for line in str(text or "").replace("\r\n", "\n").split("\n") if line.strip()]

def _pick_lines(lines, patterns, limit=12):
    result = []
    for line in lines:
        if any(re.search(pattern, line, re.I) for pattern in patterns):
            result.append(line)
        if len(result) >= limit:
            break
    return result

def _safe_title_from_filename(filename):
    name = Path(str(filename or "工程文档")).stem
    return safe_name(name, "工程文档")

def _parse_engineering_case(extracted_text, filename, document_kind="engineering_case", parsed_document=None):
    parsed_document = parsed_document or {}
    lines = _clean_lines(extracted_text)
    for table in parsed_document.get("tables") or []:
        for row in table.get("row_text") or []:
            line = " | ".join(str(cell).strip() for cell in row if str(cell).strip())
            if line:
                lines.append(line)
    title = lines[0][:120] if lines else _safe_title_from_filename(filename)
    outline = parsed_document.get("outline") or []
    if outline:
        title = (outline[0].get("text") or title)[:120]
    condition_patterns = [
        r"条件", r"参数", r"温度", r"压力", r"时间", r"比例", r"树脂", r"砂芯", r"浇注", r"孕育",
        r"temperature", r"pressure", r"time", r"ratio", r"condition", r"parameter",
    ]
    observation_patterns = [
        r"现象", r"结果", r"固化", r"强度", r"硬度", r"颜色", r"对比", r"差异", r"优于", r"不如",
        r"result", r"observation", r"compare", r"strength", r"hardness",
    ]
    conclusion_patterns = [
        r"结论", r"总结", r"汇总", r"建议", r"原因", r"风险", r"下一步", r"实际", r"说明",
        r"conclusion", r"summary", r"recommend", r"risk",
    ]
    variables = []
    variable_regexes = [
        r"\d+(?:\.\d+)?\s*(?:s|sec|秒|℃|°C|bar|MPa|%|ml|mL|kg|Kg)",
        r"[A-Za-z]?\d{2,4}/\d{2,4}",
        r"\d{3,4}[/\-]\d{3,4}",
    ]
    for line in lines:
        for pattern in variable_regexes:
            variables.extend(re.findall(pattern, line, re.I))
    variables = list(dict.fromkeys(variables))[:24]
    return {
        "type": "engineering_case",
        "document_kind": document_kind or "engineering_case",
        "title": title,
        "problem_summary": "\n".join(lines[1:5]) if len(lines) > 1 else "",
        "experiment_conditions": _pick_lines(lines, condition_patterns),
        "observations": _pick_lines(lines, observation_patterns),
        "conclusions": _pick_lines(lines, conclusion_patterns),
        "variables": variables,
        "line_count": len(lines),
        "source_title": _safe_title_from_filename(filename),
        "raw_blocks": (parsed_document.get("blocks") or [])[:500],
        "tables": (parsed_document.get("tables") or [])[:80],
        "images": parsed_document.get("images") or [],
        "outline": outline,
        "parser": parsed_document.get("parser") or "",
        "statistics": parsed_document.get("statistics") or {},
    }

def _md_list(items, fallback="待进一步整理"):
    if not items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in items[:18])

def _engineering_case_markdown(structured, extracted_text, filename, parsed_document=None):
    parsed_document = parsed_document or {}
    source_title = structured.get("source_title") or _safe_title_from_filename(filename)
    parsed_markdown = parsed_document.get("markdown") or ""
    preview = parsed_markdown.strip() or "\n".join(_clean_lines(extracted_text)[:18])
    if len(preview) > 5000:
        preview = preview[:5000].rstrip() + "\n..."
    return "\n".join([
        f"# {structured.get('title') or source_title}",
        "",
        "## 1. 文档来源",
        f"- 原始文件：{filename}",
        f"- 文档类型：{structured.get('document_kind') or 'engineering_case'}",
        "",
        "## 2. 问题与背景",
        structured.get("problem_summary") or "- 待从现场记录中进一步归纳。",
        "",
        "## 3. 工程条件 / 实验参数",
        _md_list(structured.get("experiment_conditions") or [], "暂未识别到明确条件参数"),
        "",
        "## 4. 观察结果",
        _md_list(structured.get("observations") or [], "暂未识别到明确观察结果"),
        "",
        "## 5. 初步结论 / 后续动作",
        _md_list(structured.get("conclusions") or [], "待工程师补充结论或下一步验证计划"),
        "",
        "## 6. 识别到的关键变量",
        _md_list(structured.get("variables") or [], "暂未识别到数值变量"),
        "",
        "## 7. 文档结构统计",
        _md_list([
            f"块数量：{(structured.get('statistics') or {}).get('block_count', 0)}",
            f"表格数量：{(structured.get('statistics') or {}).get('table_count', 0)}",
            f"图片数量：{(structured.get('statistics') or {}).get('image_count', 0)}",
            f"标题数量：{(structured.get('statistics') or {}).get('heading_count', 0)}",
        ], "暂未识别到结构信息"),
        "",
        "## 8. 原始结构化摘录",
        "```markdown",
        preview or "图片或附件暂未进行 OCR，已保存原始文件。",
        "```",
    ])

def _parse_upload_payload(req):
    filename = str(req.get("filename") or "upload.bin").strip() or "upload.bin"
    encoded = str(req.get("content_base64") or "").strip()
    if not encoded:
        raise HTTPException(400, "缺少文件内容")
    if "," in encoded and encoded.split(",", 1)[0].lower().startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception:
        raise HTTPException(400, "文件内容不是有效的 base64")
    if not data:
        raise HTTPException(400, "文件为空")
    max_size = 25 * 1024 * 1024
    if len(data) > max_size:
        raise HTTPException(413, "文件超过 25MB，简单版导入暂不支持")
    return filename, data

def _get_embedding_model_for_ingest():
    from search import get_embedding_model
    return get_embedding_model()

def _json_default(value, fallback):
    try:
        return json.dumps(value if value is not None else fallback, ensure_ascii=False)
    except Exception:
        return json.dumps(fallback, ensure_ascii=False)

def _index_engineering_document_chunks(user_id, project_id, document, parsed_document, filename, document_kind):
    chunks = build_document_chunks(parsed_document, filename=filename, document_kind=document_kind)
    indexable_chunks = [chunk for chunk in chunks if chunk.get("type") != "image_note"]
    if not indexable_chunks:
        return {"status": "skipped", "chunk_count": 0, "reason": "no parsed chunks"}

    import psycopg2

    doc_id = int(document.get("id"))
    source_title = document.get("title") or filename
    object_key = (document.get("metadata") or {}).get("object_key", "")
    model = _get_embedding_model_for_ingest()
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        source_metadata = {
            "source": "engineering_document",
            "project_id": project_id,
            "engineering_document_id": doc_id,
            "document_kind": document_kind,
            "object_key": object_key,
        }
        cur.execute(
            """INSERT INTO document_sources
               (source_type, title, file_name, visibility, owner_user_id, confidentiality, metadata)
               VALUES ('project_document', %s, %s, 'private', %s, 'internal', %s)
               RETURNING id""",
            (
                source_title,
                filename,
                user_id,
                _json_default(source_metadata, {}),
            ),
        )
        source_id = cur.fetchone()[0]

        cur.execute(
            "DELETE FROM chunks WHERE source_type = 'project_document' AND document_id = %s",
            (doc_id,),
        )

        batch_size = 16
        inserted = 0
        for start in range(0, len(indexable_chunks), batch_size):
            batch = indexable_chunks[start:start + batch_size]
            embeddings = model.encode([c["content"] for c in batch], show_progress_bar=False)
            for chunk, embedding in zip(batch, embeddings):
                page = int((chunk.get("pages") or [1])[0] or 1)
                chunk_meta = dict(chunk.get("metadata") or {})
                chunk_meta.update({
                    "source": "engineering_document",
                    "project_id": project_id,
                    "engineering_document_id": doc_id,
                    "document_source_id": source_id,
                    "section_path": chunk.get("section_path", ""),
                    "page_range": chunk.get("pages") or [page],
                    "tokens": chunk.get("tokens", 0),
                })
                cur.execute(
                    """INSERT INTO chunks
                       (source_id, document_id, source_type, visibility, owner_user_id, project_id,
                        confidentiality, evidence_level, chunk_id, page, chunk_type, content_text,
                        table_shape, table_header, embedding, metadata)
                       VALUES (%s, %s, 'project_document', 'private', %s, %s,
                               'internal', 'project', %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (chunk_id) DO UPDATE SET
                         content_text = EXCLUDED.content_text,
                         embedding = EXCLUDED.embedding,
                         metadata = EXCLUDED.metadata,
                         table_shape = EXCLUDED.table_shape,
                         table_header = EXCLUDED.table_header""",
                    (
                        source_id,
                        doc_id,
                        user_id,
                        project_id,
                        f"engdoc-{doc_id}-{chunk['chunk_id']}",
                        page,
                        chunk.get("type") or "paragraph",
                        chunk.get("content") or "",
                        chunk.get("table_shape"),
                        _json_default(chunk.get("table_header") or [], []),
                        embedding.tolist(),
                        _json_default(chunk_meta, {}),
                    ),
                )
                inserted += 1
        conn.commit()
        chunk_types = {}
        for chunk in chunks:
            kind = chunk.get("type") or "unknown"
            chunk_types[kind] = chunk_types.get(kind, 0) + 1
        return {
            "status": "indexed",
            "chunk_count": inserted,
            "parsed_chunk_count": len(chunks),
            "skipped_image_notes": len(chunks) - len(indexable_chunks),
            "document_source_id": source_id,
            "chunk_types": chunk_types,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _update_engineering_document_chunk_index(user_id, project_id, document_id, chunk_index):
    import psycopg2
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE engineering_documents
               SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                   updated_at = NOW()
               WHERE id = %s AND user_id = %s AND project_id = %s""",
            (_json_default({"chunk_index": chunk_index}, {}), document_id, user_id, project_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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
async def chat_stream(query: str, section: str = None, conv_id: str = None, token: str = None, history: str = None, mode: str = "qa", project_id: str = None, correction_entity: str = None, correction_original_query: str = None, display_query: str = None):
    """Direct SSE from agent.py - no proxy, no buffering.
    Supports: token (JWT) for auth, conv_id for conversation tracking.
    """
    project_id_int = None
    if project_id not in (None, "", "null", "undefined"):
        try:
            project_id_int = int(project_id)
        except Exception:
            project_id_int = None

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
            title_source = display_query or query
            title = title_source[:60] if len(title_source) > 60 else title_source
            c = create_conversation(auth_user["id"], title, project_id_int)
            conversation_id = c["id"]
            conv_id = str(conversation_id)
        
        # Save user message
        try:
            save_message(conversation_id, "user", display_query or query, {
                "mode": mode or "qa",
                "project_id": project_id_int,
                "raw_query": query,
                "correction_entity": correction_entity or "",
            })
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
                        if hist_from_conv and hist_from_conv[-1].get("role") == "user" and hist_from_conv[-1].get("content") in {query, display_query}:
                            hist_from_conv.pop()
                except Exception:
                    pass
            effective_history = request_history or hist_from_conv
            stream_iter = _agent.stream_chat(query, section, history=effective_history if effective_history else None, mode=full_mode, project_id=project_id_int, correction_entity=correction_entity)
            while True:
                event = await asyncio.to_thread(_next_stream_event, stream_iter)
                if event is _STREAM_DONE:
                    break
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
                    save_message(conversation_id, "assistant", full_answer, {"citations": full_citations, "graph": full_graph, "retrieval": full_retrieval, "mode": full_mode, "structured_output": full_structured_output, "project_id": project_id_int})
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

@app.get("/api/projects/{project_id}/evidence")
async def api_list_project_evidence(project_id: int, user: dict = Depends(require_user)):
    """List confirmed evidence cards for a project."""
    project = get_project(project_id, user["id"])
    if not project:
        raise HTTPException(404, "项目不存在")
    return {"evidence_cards": list_evidence_cards(user["id"], project_id)}

@app.post("/api/projects/{project_id}/evidence")
async def api_create_project_evidence(project_id: int, req: dict, user: dict = Depends(require_user)):
    """Save an automatic citation as a project evidence card."""
    card = create_evidence_card(user["id"], project_id, req)
    return {"evidence_card": card}

@app.put("/api/projects/{project_id}/evidence/{evidence_id}")
async def api_update_project_evidence(project_id: int, evidence_id: int, req: dict, user: dict = Depends(require_user)):
    """Update a project evidence card."""
    card = update_evidence_card(user["id"], project_id, evidence_id, req)
    if not card:
        raise HTTPException(404, "证据卡不存在")
    return {"evidence_card": card}

@app.delete("/api/projects/{project_id}/evidence/{evidence_id}")
async def api_delete_project_evidence(project_id: int, evidence_id: int, user: dict = Depends(require_user)):
    """Delete a project evidence card."""
    ok = delete_evidence_card(user["id"], project_id, evidence_id)
    if not ok:
        raise HTTPException(404, "证据卡不存在")
    return {"message": "deleted"}

@app.get("/api/projects/{project_id}/engineering-documents")
async def api_list_engineering_documents(project_id: int, user: dict = Depends(require_user)):
    """List engineering documents imported into a project."""
    project = get_project(project_id, user["id"])
    if not project:
        raise HTTPException(404, "项目不存在")
    return {"engineering_documents": list_engineering_documents(user["id"], project_id)}

@app.post("/api/projects/{project_id}/engineering-documents")
async def api_upload_engineering_document(project_id: int, req: dict, user: dict = Depends(require_user)):
    """Import a field note, experiment record, or process mind-map into a project."""
    project = get_project(project_id, user["id"])
    if not project:
        raise HTTPException(404, "项目不存在")

    filename, data = _parse_upload_payload(req)
    mime_type = str(req.get("mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream")
    document_kind = str(req.get("document_kind") or "engineering_case").strip()[:50] or "engineering_case"
    source_type = str(req.get("source_type") or "current_project").strip()[:50] or "current_project"
    digest = object_hash(data)
    object_key = build_object_key(project_id, filename, digest)
    storage_info = get_object_store().put_bytes(object_key, data)

    parsed_document = _parse_uploaded_document(filename, data, mime_type)
    extracted_text = parsed_document.get("text") or ""
    structured = _parse_engineering_case(extracted_text, filename, document_kind, parsed_document)
    parse_status = parsed_document.get("parse_status") or ("parsed" if extracted_text else "stored")
    title = structured.get("title") or _safe_title_from_filename(filename)
    document = create_engineering_document(
        user["id"],
        project_id,
        title,
        filename,
        document_kind,
        source_type,
        storage_info,
        digest,
        mime_type,
        len(data),
        parse_status,
        extracted_text,
        structured,
        {
            "original_filename": filename,
            "object_key": object_key,
            "content_hash": digest,
            "parser": parsed_document.get("parser") or ("simple_text_v1" if extracted_text else "stored_without_ocr_v1"),
            "statistics": parsed_document.get("statistics") or {},
        },
    )
    chunk_index = {"status": "not_started", "chunk_count": 0}
    try:
        chunk_index = _index_engineering_document_chunks(
            user["id"],
            project_id,
            document,
            parsed_document,
            filename,
            document_kind,
        )
    except Exception as exc:
        _log.warning(f"Engineering document chunk indexing failed: {exc}")
        chunk_index = {"status": "failed", "chunk_count": 0, "error": str(exc)[:240]}
    try:
        _update_engineering_document_chunk_index(user["id"], project_id, document["id"], chunk_index)
    except Exception as exc:
        _log.warning(f"Engineering document chunk metadata update failed: {exc}")
    document.setdefault("metadata", {})
    document["metadata"]["chunk_index"] = chunk_index
    document["chunk_index"] = chunk_index
    artifact = save_project_artifact(
        user["id"],
        project_id,
        "engineering_case",
        title,
        _engineering_case_markdown(structured, extracted_text, filename, parsed_document),
        structured,
        [],
        {
            "source": "engineering_document_import",
            "engineering_document_id": document.get("id"),
            "storage_backend": storage_info.get("storage_backend"),
            "bucket": storage_info.get("bucket"),
            "object_key": object_key,
            "parse_status": parse_status,
            "mime_type": mime_type,
            "chunk_index": chunk_index,
        },
    )
    document = attach_artifact_to_engineering_document(user["id"], project_id, document["id"], artifact["id"]) or document
    document.setdefault("metadata", {})
    document["metadata"]["chunk_index"] = chunk_index
    document["chunk_index"] = chunk_index
    return {"document": document, "artifact": artifact, "project": get_project(project_id, user["id"])}

@app.get("/api/projects/{project_id}/artifacts/{artifact_id}/pdf")
async def api_download_project_artifact_pdf(project_id: int, artifact_id: int, user: dict = Depends(require_user)):
    """Render a saved project artifact as a Markdown-formatted PDF download."""
    project = get_project(project_id, user["id"])
    if not project:
        raise HTTPException(404, "项目不存在")
    artifact = next((item for item in project.get("artifacts") or [] if int(item.get("id") or 0) == artifact_id), None)
    if not artifact:
        raise HTTPException(404, "项目产物不存在")
    try:
        pdf = await _artifact_pdf_bytes(project, artifact)
    except Exception as e:
        raise HTTPException(500, f"PDF 生成失败: {e}")
    filename = _safe_report_filename(artifact.get("title") or "project-artifact") + ".pdf"
    disposition = f"attachment; filename=\"project-artifact.pdf\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )

@app.post("/api/projects/{project_id}/brief")
async def api_generate_project_brief(project_id: int, user: dict = Depends(require_user)):
    """Generate and save a project brief from conversations and artifacts."""
    project = get_project(project_id, user["id"])
    if not project:
        raise HTTPException(404, "项目不存在")

    context = _collect_project_brief_context(project)
    messages = [
        {"role": "system", "content": PROJECT_BRIEF_PROMPT},
        {"role": "user", "content": context},
    ]
    brief = _agent._call_llm(messages, max_tokens=2600, timeout=75)
    generated_by = "llm"
    if not brief.strip():
        brief = _fallback_project_brief(project)
        generated_by = "fallback"

    title = f"{project.get('name') or '项目'} - 项目简报"
    citations = _project_brief_citations(project)
    report_evidence = _report_evidence_cards(project)
    artifact = save_project_artifact(
        user["id"],
        project_id,
        "project_brief",
        title[:120],
        brief,
        {
            "type": "project_brief",
            "format": "markdown",
            "generated_by": generated_by,
            "report_evidence_count": len(report_evidence),
        },
        citations,
        {
            "source": "project_brief_generator",
            "generated_by": generated_by,
            "citation_source": "evidence_cards" if report_evidence else "artifact_citations",
            "report_evidence_count": len(report_evidence),
            "report_evidence_ids": [card.get("id") for card in report_evidence[:30]],
            "conversation_count": len(project.get("conversations") or []),
            "artifact_count": len(project.get("artifacts") or []),
        },
    )
    return {"artifact": artifact, "project": get_project(project_id, user["id"])}

if __name__ == "__main__":
    print(f"[Orchestrator] Starting on {HOST}:{PORT}")
    print(f"[Orchestrator] SSE: direct from agent.py (no proxy)")
    print(f"[Orchestrator] RAG Agent (search/chat POST): {RAG_URL}")
    uvicorn.run(app, host=HOST, port=PORT)
