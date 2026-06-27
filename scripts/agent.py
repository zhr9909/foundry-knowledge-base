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

FALLBACK_SYSTEM_PROMPT = """你是铸造、金属材料专业知识库AI助手。当前知识库检索未能找到与用户问题匹配的有效信息。
请基于你自身的知识来回答用户问题。

【规则】
1. 回答开头必须加免责声明：「知识库中未检索到相关内容，以下回答基于模型自身知识，请核实关键数据」
2. 尽可能提供准确、具体的数值数据，附带单位
3. 如果也不确定答案，诚实说明不确定性
4. 使用中文回答
"""


FALLBACK_SYSTEM_PROMPT = """你是铸造、金属材料专业知识库AI助手。
当前知识库检索未能找到与用户问题匹配的有效信息，请基于你自身的知识来回答用户问题。

【规则】
1. 回答开头必须加免责声明：「知识库中未检索到相关内容，以下回答基于模型自身知识，请核实关键数据」
2. 尽可能提供准确、具体的数值数据，附带单位
3. 如果也不确定答案，诚实说明不确定性
4. 使用中文回答"""

FALLBACK_SYSTEM_PROMPT = """你是铸造、金属材料专业知识库AI助手。当前知识库检索未能找到与用户问题匹配的有效信息，请基于你自身的知识来回答用户问题。

[规则]
1. 回答开头必须加免责声明
2. 提供具体数值数据，附带单位
3. 不确定时诚实说明
4. 使用中文回答"""
FALLBACK_SYSTEM_PROMPT = """你是铸造、金属材料专业知识库AI助手。当前知识库检索未能找到与用户问题匹配的有效信息，请基于你自身的知识来回答用户问题。

[规则]
1. 回答开头必须加免责声明
2. 提供具体数值数据，附带单位
3. 不确定时诚实说明
4. 使用中文回答"""

IMPROVED_SYSTEM_PROMPT = """你是铸造、金属材料专业知识库专属AI助手，知识库数据源仅为《ASM Handbook Vol.2》，所有回答严格依据本次传入的「检索结果」内容生成。

# 一、硬性核心约束（违反即判定回答失效）
1. 信息唯一来源：仅能使用本次提供的检索结果文本，绝对禁止调用模型内置知识、编造材料参数、脑补推导手册以外内容；若全部检索块无对应有效信息，统一回复：「知识库中没有找到相关信息」。
2. 引用规范：每一处材料数据、结论、描述都必须标注对应检索结果序号引用标记[数字]，序号与传入results数组顺序一一对应，禁止编造、跳号、不存在的编号。
3. 信息过滤：自动识别检索结果中无关内容（硅青铜、锰黄铜、铜镍合金、铝镍钴永磁等非铝合金材料），回答时完全剔除无关铜材、永磁材料数据，仅保留和用户提问金属牌号匹配的有效内容。
4. 数据真实性：表格型chunk、文本chunk同等采信，表格参数必须完整转述，不得篡改、四舍五入删减关键数值。

# 二、数值与单位强制规则（材料专业统一标准）
1. 所有力学、热学、温度、成分数值必须附带完整单位：强度统一标注MPa/ksi、温度标注℃(℉)、循环次数标注10⁶、成分标注质量百分比%；
2. 同时存在英制+公制单位时，优先展示公制(MPa/℃)，英制数值作为补充附带；
3. 合金牌号完整保留热处理状态，如6061-T6、6061-T651，不可简写丢失T6/T651标识。

# 三、标准回答结构（严格按场景匹配）
## 场景1：单一材料参数问答（如：6061铝合金力学性能）
1. 第一段：一句话直接给出核心结论；
2. 第二段：分维度罗列全部细分数据（拉伸强度、屈服强度、疲劳强度、断裂韧性、低温性能、合金成分），每条参数附带数值+单位+引用标记；
3. 第三段：补充工况、测试条件、适用说明（如有）。

## 场景2：多材料对比提问（如6061与7075疲劳性能对比）
强制使用Markdown对比表格，表格固定列：合金牌号&热处理态、性能指标、常温24℃参数、低温-196℃参数、数据来源；
表格内每个单元格数值附带单位，表格下方统一标注对应引用来源。

## 场景3：成分/牌号查询（如6061合金元素组成）
分点列出合金各元素质量占比，标注合金体系（Al-Mg1SiCu）。

## 场景4：无有效匹配信息
固定单句输出：「知识库中没有找到相关信息」，不额外拓展内容。

# 四、冲突/多chunk整合规则
1. 同一参数在多条检索块出现重复数据：合并去重，统一标注全部来源引用；
2. 多条检索块同一指标数值存在冲突：分别列出两组数据，标注各自对应的来源编号，不自行取舍判定对错；
3. 多条分散chunk同一材料数据：按「成分→常温力学→低温疲劳→断裂韧性」分类整合，不零散罗列。

# 五、语言要求
# 六、检索失败兜底规则
当系统确认多次检索均无法从知识库中找到与问题匹配的有效信息时，会切换为本规则：
1. 先用[知识库中未找到相关信息]明确告知用户；
2. 然后基于模型自身知识给出尽可能准确的回答；
3. 在这种模式下，回答前必须加一句免责声明。
全程使用通顺专业中文，符合金属铸造行业书面表达，禁止口语化、网络用语；专业材料名词统一遵循ASM手册
# 六、检索失败兜底规则
当系统确认多次检索均无法从知识库中找到与问题匹配的有效信息时，会切换为本规则：
1. 先用[知识库中未找到相关信息]明确告知用户；
2. 然后基于模型自身知识给出尽可能准确的回答；
3. 在这种模式下，回答前必须加一句免责声明。
"""






"""

你是材料工程专业知识库的检索语句优化专家。
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

def generate_answer(query: str, context: list, history: list = None, system_prompt: str = None) -> dict:

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
        {"role": "system", "content": system_prompt or IMPROVED_SYSTEM_PROMPT},
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
    if not answer or len(answer) < 30:
        return {"score": 3, "reason": "too short", "missing": "specific data"}
    prompt = f"""You are a strict, professional answer quality evaluator for metal material knowledge base based on ASM Handbook.
Evaluate the answer strictly against the 3 criteria, calculate total score by summing sub-scores, final total range: 1~10.

# Grading Sub-Criteria
1. Direct and specific data response (0-4 points)
    4: Fully answer, complete data with unit, no irrelevant content.
    2: Partially answer, missing key data.
    0: No valid data, only general text.
2. Source citation with [N] marker (0-3 points)
    3: Every data point correctly cited, no missing or fake citations.
    1: Partial missing citations.
    0: No citations at all.
3. Logical structure and factual correctness (0-3 points)
    3: Clear structure, no fabricated data.
    1: Messy structure, conflicting data.
    0: Disorganized, fabricated data.

# Input
Question: {query}
Generated Answer: {answer}

Output ONLY a JSON: {{"score": N, "reason": "one sentence", "missing": "what specific info is missing"}}"""
    try:
        result = _call_llm([{"role": "system", "content": "You are a strict evaluator. Output only JSON."}, {"role": "user", "content": prompt}], max_tokens=128, timeout=15)
        import re
        nums = re.findall(r"\\d+", result)
        score = int(nums[0]) if nums else 7
        return {"score": min(max(score, 1), 10), "reason": "", "missing": ""}
    except:
        return {"score": 8, "reason": "eval failed", "missing": ""}

def agent_chat(query: str, section: str = None, history: list = None, progress_callback: callable = None) -> dict:
    _log.info('=' * 50)
    _log.info(f'Query: {query}')
    start = time.time()
    max_retries = 1
    current_query = query
    if progress_callback: progress_callback({'type': 'log', 'message': '开始处理查询...'})
    if progress_callback: progress_callback({'type': 'log', 'message': f'原始查询：{query}'})
    for attempt in range(max_retries + 1):
        _log.info(f'Attempt {attempt + 1}/{max_retries + 1}')
        if attempt > 0:
            if progress_callback: progress_callback({'type': 'log', 'message': f'开始第{attempt+1}轮尝试...', 'level': 'retry'})
        if progress_callback: progress_callback({'type': 'log', 'message': '正在进行查询语义拆解...'})
        sub_queries = rewrite_query(current_query)
        _log.info(f'Rewritten: {sub_queries}')
        if progress_callback: progress_callback({'step': 'rewritten', 'queries': sub_queries})
        if progress_callback: progress_callback({'type': 'log', 'message': f'查询拆解完成：{sub_queries}'})
        if progress_callback: progress_callback({'type': 'log', 'message': '正在检索知识库...'})
        results = search_parallel(sub_queries, section, top_k=12)
        _log.info(f'Candidates: {len(results)}')
        if progress_callback: progress_callback({'step': 'searched', 'count': len(results)})
        if progress_callback: progress_callback({'type': 'log', 'message': f'检索完成，共{len(results)}条候选'})
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
        if progress_callback: progress_callback({'type': 'log', 'message': '正在精选相关上下文...'})
        context = select_context(results, top_k=dynamic_k, original_query=' '.join(sub_queries), search_query=sub_queries[0] if sub_queries else current_query)
        _log.info(f'Context: {len(context)} chunks')
        if progress_callback: progress_callback({'step': 'context_ready', 'count': len(context)})
        if progress_callback: progress_callback({'type': 'log', 'message': f'精选{len(context)}条上下文'})
        if progress_callback: progress_callback({'type': 'log', 'message': '正在构建提示词并生成回答...'})
        ad = generate_answer(current_query, context, history)
        answer = ad.get('answer', '')
        if attempt < max_retries and len(answer) > 30:
            if progress_callback: progress_callback({'type': 'log', 'message': '正在进行质量检查和评估...'})
            qc = quality_check(current_query, answer)
            _log.info(f'Quality: {qc["score"]}/10')
            if progress_callback: progress_callback({'step': 'checked', 'score': qc['score']})
            if qc['score'] >= 7:
                if progress_callback: progress_callback({'type': 'log', 'message': f'质量评分{qc["score"]}/10，通过！'})
                elapsed = int((time.time()-start)*1000)
                _log.info(f'Done: {elapsed}ms')
                return {'answer': answer, 'citations': ad.get('citations', context[:5]), 'model': ad.get('model', ''), 'sub_queries': sub_queries, 'attempts': attempt+1, 'latency_ms': elapsed}
            if progress_callback: progress_callback({'type': 'log', 'message': f'质量评分{qc["score"]}/10，偏低，进行新一轮检索...', 'level': 'retry'})
            current_query = query + ' data'
        else:
            if len(answer) < 50 or '没有找到' in answer or '未找到' in answer:
                if progress_callback: progress_callback({'type': 'log', 'message': '知识库中未找到相关信息，切换到大模型知识兜底...', 'level': 'fallback'})
                ad = generate_answer(current_query, context, history, system_prompt=FALLBACK_SYSTEM_PROMPT)
                answer = ad.get('answer', answer)
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


def stream_chat(query: str, section: str = None, history: list = None):
    """Generator that yields progress events during agent_chat execution."""
    import queue as _q
    import threading as _t
    q = _q.Queue()

    def progress(event):
        q.put(event)

    def worker():
        try:
            result = agent_chat(query, section, history, progress_callback=progress)
            q.put({"type": "result", "data": result})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
        finally:
            q.put(None)

    _t.Thread(target=worker, daemon=True).start()

    while True:
        event = q.get()
        if event is None:
            break
        yield event
