#!/usr/bin/env python3
"""agent.py - Intelligent RAG Orchestrator
===========================================
Multi-step agent that rewrites queries, parallel searches, selects context,
and generates answers with improved prompting.

Usage: from agent import agent_chat
       result = agent_chat("铝合金6061的力学性能")
"""

import os, sys, json, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, str(Path(__file__).parent))
from search import search, list_sections

import httpx
import logging
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent.log')
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [AGENT] %(message)s',
    datefmt='%H:%M:%S',
    force=True
)
_log = logging.getLogger('agent')

LLM_API = "http://127.0.0.1:15721/v1"
LLM_MODEL = "deepseek-v4-flash"
LLM_KEY = "PROXY_MANAGED"

IMPROVED_SYSTEM_PROMPT = """你是一位铸造和金属材料领域的知识库AI助手，基于 ASM Handbook Vol.2 的内容回答用户提问。

【核心原则】
- 只使用"检索结果"中提供的信息来回答。如果信息不足，直接说"知识库中没有找到相关信息"。
- 引用来源时用 [1]、[2] 等编号标注，对应检索结果列表中的序号。
- 使用中文回答，要具体有数据支撑，给出数值时附带单位。

【回答结构】
1. 如果问题有明确答案，先直接回答，再补充详细数据。
2. 如果涉及数值（如强度、温度），必须给出具体数字和单位。
3. 如果是对比类问题，用表格或对比结构呈现。

【引用格式】
- 每个数据点后面标注来源，如"抗拉强度 310 MPa [1]"
- 表格数据转述为文字描述
- 不编造不存在的引用编号"""

QUERY_REWRITE_PROMPT = """你是材料工程专业知识库的检索语句优化专家。
你的任务：将用户中文材料问题，优化生成1~3条适配混合检索的英文专业检索语句，严格遵循以下全部规则：

## 一、检索语句专业改写规则
1. 必须保留全部核心关键实体：材料牌号(6061/7075等)、热处理状态(T6/T651)、性能类型、测试温度、测试工况；
2. 区分检索维度拆分复合问题，单条query只聚焦一类性能（力学/疲劳/断裂韧性/化学成分/热学性能分开写）；
3. 使用材料行业标准专业术语，禁止口语化描述；
4. 主动过滤无关材料关键词，规避搜索结果混入其他材料类型的数据；
5. 每条query关键词前置，便于全文检索命中表格标题和页面标题；

## 二、输出强制格式
仅输出纯JSON数组，无任何多余解释、前言、换行说明，数组内1~3条英文字符串

## 三、边界兜底
1. 用户简单单条件问题：生成1条精准query；
2. 用户多性能复合问题：拆分为2~3条分维度query；
3. 包含温度、循环次数等测试参数，必须完整写入检索语句；
4. 不允许超长单句query，每条控制在30个英文单词以内。"""

def generate_answer(query: str, context: list, history: list = None) -> dict:

    # Build context block
    context_parts = []
    for c in context:
        source = f"[{c['index']}] pg.{c['page']}"
        if c.get("section"):
            source += f" ({c['section']})"
        context_parts.append(f"{source}\n{c['text']}")
    context_text = "\n\n---\n\n".join(context_parts)
    
    # Build messages
    messages = [
        {"role": "system", "content": IMPROVED_SYSTEM_PROMPT},
    ]
    
    # Add history
    if history:
        for msg in history[-4:]:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current query + context
    messages.append({
        "role": "user",
        "content": f"检索结果：\n\n{context_text}\n\n---\n\n用户问题：{query}\n\n请基于以上检索结果回答。"
    })
    
    # Call LLM
    start = time.time()
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{LLM_API}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
                json={"model": LLM_MODEL, "messages": messages, "max_tokens": 2048},
            )
            
            if resp.status_code != 200:
                return {"answer": f"❌ AI 调用失败 (HTTP {resp.status_code})", "citations": context[:5]}
            
            data = resp.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            answer = (msg.get("content", "") or "").strip()
            thinking = (msg.get("reasoning_content", "") or "")
            
            elapsed = int((time.time() - start) * 1000)
            
            return {
                "answer": answer,
                "citations": context[:5],
                "thinking": thinking,
                "model": data.get("model", ""),
                "latency_ms": elapsed,
            }
    except httpx.TimeoutException:
        return {"answer": "❌ AI 响应超时（超过60秒）", "citations": context[:5]}
    except Exception as e:
        return {"answer": f"❌ AI 异常: {str(e)}", "citations": context[:5]}



def quality_check(query: str, answer: str) -> dict:
    """Evaluate answer quality. Returns {score, reason, missing}."""
    if not answer or len(answer) < 20:
        return {"score": 1, "reason": "Answer too short", "missing": "Need specific data"}
    
    prompt = f"""You are a strict answer quality evaluator. Rate from 1-10.

Criteria:
1. Does it DIRECTLY answer the question with specific data? (0-4)
2. Does it cite sources properly with [N] markers? (0-3)  
3. Is the answer well-structured and factual? (0-3)

Question: {query}
Answer: {answer}

Output ONLY a JSON: {{"score": N, "reason": "one line", "missing": "what specific info is missing"}}"""
    
    try:
        result = _call_llm([
            {"role": "system", "content": "You are a strict evaluator. Output only JSON."},
            {"role": "user", "content": prompt}
        ], max_tokens=128, timeout=15)
        
        import re, json as _json
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            data = _json.loads(match.group())
            return {
                "score": int(data.get("score", 5)),
                "reason": data.get("reason", ""),
                "missing": data.get("missing", ""),
            }
    except Exception as e:
        _log.warning(f"Quality check failed: {e}")
    
    return {"score": 5, "reason": "Evaluation failed", "missing": ""}

def agent_chat(query: str, section: str = None, history: list = None) -> dict:
    _log.info('=' * 50)
    _log.info(f'Query: {query}')
    start = time.time()
    max_retries = 1
    current_query = query
    for attempt in range(max_retries + 1):
        _log.info(f'Attempt {attempt + 1}/{max_retries + 1}')
        sub_queries = rewrite_query(current_query)
        _log.info(f'Rewritten: {sub_queries}')
        results = search_parallel(sub_queries, section, top_k=12)
        _log.info(f'Candidates: {len(results)}')
        if results:
            top_score = results[0].get("score", 0)
            if top_score >= 0.75:
                dynamic_k = 4
            elif top_score >= 0.6:
                dynamic_k = 6
            elif top_score >= 0.4:
                dynamic_k = 8
            else:
                dynamic_k = 8
            _log.info(f'Dynamic k: {dynamic_k} (top_score={top_score:.3f})')
        else:
            dynamic_k = 6
        if not results:
            if attempt < max_retries:
                current_query = query + ' properties data'
                continue
            return {'answer': 'No relevant information.', 'citations': [], 'latency_ms': int((time.time()-start)*1000), 'attempts': attempt+1}
        context = select_context(results, top_k=dynamic_k, original_query=' '.join(sub_queries), search_query=sub_queries[0] if sub_queries else current_query)
        _log.info(f'Context: {len(context)} chunks')
        ad = generate_answer(current_query, context, history)
        answer = ad.get('answer', '')
        if attempt < max_retries and len(answer) > 30:
            qc = quality_check(current_query, answer)
            _log.info(f'Quality: {qc["score"]}/10')
            if qc['score'] >= 7:
                elapsed = int((time.time()-start)*1000)
                _log.info(f'Done: {elapsed}ms')
                return {'answer': answer, 'citations': ad.get('citations', context[:5]), 'model': ad.get('model', ''), 'sub_queries': sub_queries, 'attempts': attempt+1, 'latency_ms': elapsed}
            current_query = query + ' data'
        else:
            elapsed = int((time.time()-start)*1000)
            _log.info(f'Done: {elapsed}ms')
            return {'answer': answer, 'citations': ad.get('citations', context[:5]), 'model': ad.get('model', ''), 'sub_queries': sub_queries, 'attempts': attempt+1, 'latency_ms': elapsed}
    elapsed = int((time.time()-start)*1000)
    return {'answer': 'Failed after retries.', 'latency_ms': elapsed, 'attempts': max_retries+1}
def _call_llm(messages, max_tokens=512, timeout=30):
    last_input = (messages[-1]["content"][:200] if messages else "") + "..."
    func = messages[0]["content"][:60] if messages and messages[0]["role"] == "system" else "no system"
    _log.info(f"LLM -> {max_tokens}tok [{func}] timeout={timeout}s")
    _log.info(f"  Input: {last_input}")
    start = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{LLM_API}/chat/completions", headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}, json={"model": LLM_MODEL, "messages": messages, "max_tokens": max_tokens})
            elapsed = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                result = data["choices"][0]["message"].get("content", "")
                _log.info(f"  Resp ({elapsed}ms): {result[:250]}")
                return result
            _log.warning(f"  HTTP {resp.status_code} ({elapsed}ms)")
    except Exception as e:
        _log.warning(f"  Error: {e}")
    return ""

def rewrite_query(query: str) -> list:
    if re.match(r'^[a-zA-Z0-9\s\-\.]+$', query) and len(query.split()) <= 10:
        return [query.strip()]
    try:
        result = _call_llm([
            {"role": "system", "content": QUERY_REWRITE_PROMPT},
            {"role": "user", "content": query}
        ], max_tokens=256, timeout=15)
        if result:
            import json as _json
            match = re.search(r'\[.*?\]', result, re.DOTALL)
            if match:
                parsed = _json.loads(match.group())
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed[:3]
    except:
        pass
    return [query.strip()]

def search_single(query: str, section: str = None, top_k: int = 8) -> list:
    from search import search
    result = search(query, top_k=top_k, hybrid=True, section=section)
    return result.get("results", [])

def search_parallel(sub_queries, section=None, top_k=8):
    per_query = []
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(sub_queries), 3)) as executor:
        futures = {executor.submit(search_single, q, section, 12): q for q in sub_queries}
        for future in as_completed(futures):
            q = futures[future]
            results = future.result()
            per_query.append(results)
            all_results.extend(results)
            _log.info(f"  Query [{q[:60]}]: {len(results)} results")
            if results:
                _log.info(f"    Top: pg.{results[0]['page']} score={results[0]['score']:.4f}")
    seen = {}
    interleaved = []
    for i in range(8):
        for q_results in per_query:
            if i < len(q_results):
                r = q_results[i]
                cid = r.get("chunk_id", "")
                if cid not in seen:
                    seen[cid] = r
                    interleaved.append(r)
    for r in sorted(all_results, key=lambda x: x.get("score", 0), reverse=True):
        cid = r.get("chunk_id", "")
        if cid not in seen:
            seen[cid] = r
            interleaved.append(r)
    _log.info(f"  Merged: {len(interleaved)} candidates -> returning top {top_k}")
    return interleaved[:top_k]

def get_reranker():
    if not hasattr(get_reranker, "_model"):
        from sentence_transformers import CrossEncoder
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _log.info(f"  Loading reranker ({device})...")
        get_reranker._model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=device)
    return get_reranker._model

def rerank(query, candidates, top_k=6):
    if not candidates or len(candidates) < 2:
        return candidates[:top_k]
    model = get_reranker()
    pairs = [(query, c.get("text_full", c.get("text", ""))) for c in candidates]
    scores = model.predict(pairs, show_progress_bar=False)
    min_s, max_s = min(scores), max(scores)
    if max_s > min_s:
        norm_scores = [(s - min_s) / (max_s - min_s) for s in scores]
    else:
        norm_scores = [0.5 for _ in scores]
    for i, c in enumerate(candidates):
        c["rerank_score"] = round(norm_scores[i], 4)
    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return candidates[:top_k]

def select_context(results, top_k=6, original_query="", search_query=""):
    boost_keywords = []
    if original_query:
        import re as re2
        codes = re2.findall(r"[A-Za-z]+\d+|\d+[A-Za-z]+|\d+", original_query)
        boost_keywords.extend([c.lower() for c in codes])
    if boost_keywords:
        _log.info(f"  Boost keywords: {boost_keywords}")
    scored = []
    for r in results:
        original_score = r.get("score", 0)
        score = original_score
        text = (r.get("text_full", r.get("text", "")) or "").lower()
        boosted = False
        for kw in boost_keywords:
            if kw.lower() in text:
                score += 0.08
                boosted = True
                break
        if boosted:
            _log.info(f"    pg.{r['page']}: {original_score:.4f} -> {score:.4f} [+0.08]")
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    candidates_pool = [r for _, r in scored[:max(top_k * 2, 12)]]
    selected = candidates_pool[:top_k]
    formatted = []
    for i, r in enumerate(selected):
        formatted.append({
            "index": i + 1,
            "chunk_id": r.get("chunk_id", ""),
            "page": r.get("page", 0),
            "type": r.get("type", ""),
            "text": r.get("text_full", r.get("text", "")),
            "score": round(r.get("score", 0), 4),
            "section": r.get("section", ""),
        })
    return formatted
