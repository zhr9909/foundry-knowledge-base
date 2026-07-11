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
from typing import TypedDict, Optional, List, Any
from langgraph.graph import StateGraph, START, END

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, str(Path(__file__).parent))
from search import search, list_sections

import httpx
import logging

_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent.log')
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [AGENT] %(message)s',
    datefmt='%H:%M:%S',
    force=True
)
_log = logging.getLogger('agent')

LLM_API = os.environ.get("LLM_API", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
LLM_KEY = os.environ.get("LLM_KEY", "")

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
3. 信息过滤：自动识别检索结果中与当前问题材料实体不匹配的内容，回答时仅保留和用户提问金属材料、牌号、工艺或性能指标匹配的有效内容。
4. 数据真实性：表格型chunk、文本chunk同等采信，表格参数必须完整转述，不得篡改、四舍五入删减关键数值。

# 二、数值与单位强制规则（材料专业统一标准）
1. 所有力学、热学、温度、成分数值必须附带完整单位：强度统一标注MPa/ksi、温度标注℃(℉)、循环次数标注10⁶、成分标注质量百分比%；
2. 同时存在英制+公制单位时，优先展示公制(MPa/℃)，英制数值作为补充附带；
3. 合金牌号、钢种、热处理状态必须完整保留，不可简写或替换为其他材料。

# 三、标准回答结构（严格按场景匹配）
## 场景1：单一材料参数问答（如：<当前材料>的<当前性能/工艺参数>）
1. 第一段：一句话直接给出核心结论；
2. 第二段：分维度罗列全部细分数据（拉伸强度、屈服强度、疲劳强度、断裂韧性、低温性能、合金成分），每条参数附带数值+单位+引用标记；
3. 第三段：补充工况、测试条件、适用说明（如有）。

## 场景2：多材料对比提问（如<材料A>与<材料B>的<性能/工艺>对比）
强制使用Markdown对比表格，表格固定列：合金牌号&热处理态、性能指标、常温24℃参数、低温-196℃参数、数据来源；
表格内每个单元格数值附带单位，表格下方统一标注对应引用来源。

## 场景3：成分/牌号查询（如<当前牌号>元素组成）
分点列出合金各元素质量占比，标注合金体系或材料类别。

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






QUERY_REWRITE_PROMPT = """
# 角色定位
你是深耕铸造、金属材料工程的检索策略专家，精通材料手册检索逻辑，专为工业私有材料知识库设计检索方案。
知识库内容：各类变形铝合金、铜合金、永磁材料、铸造工艺、力学/热学性能、高低温测试参数、牌号标准、加工规范；检索底层为FTS全文检索(BM25) + 稠密向量检索 + RRF排名融合混合架构。

# 核心任务
接收用户铸造/金属材料类提问，输出一套可直接交付检索引擎执行的标准化检索策略。

# 强制拆解&生成规则
## 1. 核心实体提取
完整拆分问题内全部检索关键要素，分为四类：
1) 材料实体：合金牌号、热处理状态、合金体系（必须来自当前问题或已解析上下文，不得从示例继承）
2) 性能实体：抗拉强度、屈服强度、疲劳强度、断裂韧性、热膨胀系数等
3) 工况实体：测试温度(-196℃/常温24℃)、循环次数、焊接/锻造工艺
4) 查询意图：单参数查询、多牌号对比、高低温性能、成分查询、表格参数查询

## 2. 检索Query生成规范（适配混合检索）
1. 输出1~4条英文专业检索语句；
2. 每条Query必须携带核心牌号、热处理态、测试温度、性能指标；
3. 复合类问题拆分维度：力学疲劳单独一条、低温韧性单独一条、合金成分单独一条；
4. 使用标准专业术语，禁止口语化描述，每条控制在30词以内。

## 3. 输出硬性约束
仅输出标准单行JSON，禁止额外说明、换行、注释，字段不可缺失：
1. core_entity：数组，存放提取到的全部关键实体；
2. filter_rule：字符串，明确检索时的文档过滤逻辑（如"仅铝合金"、"排除铜合金"、"全部"）；
3. search_queries：数组，1~4条英文检索语句；
4. search_priority：字符串，"关键词优先"或"语义均衡"，材料牌号类固定"关键词优先"
5. 严禁从示例中复制材料实体；只能使用当前问题或已解析上下文中的材料。

# 输出示例（抽象模板，尖括号内容必须替换为当前问题/上下文中的真实实体，禁止原样输出）
{"core_entity": ["<当前材料实体>","<当前性能或工艺意图>"], "filter_rule": "仅<当前材料类别或牌号>", "search_queries": ["<current material/entity> <current property/process intent>"], "search_priority": "语义均衡"}
"""

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
        for msg in history[-8:]:
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
        with httpx.Client(timeout=60, trust_env=False) as client:
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


def _answer_indicates_no_knowledge(answer: str) -> bool:
    text = (answer or "").strip()
    if not text or text.startswith("❌"):
        return False
    phrases = [
        "知识库中没有找到相关信息",
        "知识库中未找到相关信息",
        "没有找到相关信息",
        "未找到相关信息",
        "未能找到与",
        "未检索到",
    ]
    return any(p in text for p in phrases)


def _should_repair_retrieval(state: dict) -> bool:
    if int(state.get("repair_attempts", 0) or 0) >= int(state.get("max_repair_attempts", 0) or 0):
        return False
    answer = state.get("answer", "") or ""
    if answer.strip().startswith("❌"):
        return False
    if not state.get("search_results") or not state.get("context"):
        return True
    if _answer_indicates_no_knowledge(answer):
        return True
    if answer and len(answer.strip()) < 50:
        return True
    return False


def _repair_fallback_queries(query: str, state: dict) -> list:
    entities = state.get("core_entity") or _explicit_entities_for_text(query)
    intents = _intent_terms(query)
    queries = []
    if len(entities) > 1:
        for entity in entities[:4]:
            term = _entity_search_term(entity)
            if intents:
                queries.append(f"{term} {' '.join(intents)}")
            queries.append(f"{term} properties and selection")
            if term == "iron alloy":
                queries.append("high alloy iron castings properties")
    else:
        rule = _entity_rule_for_text(query)
        term = _entity_search_term(rule["label"]) if rule else query
        if intents:
            queries.append(f"{term} {' '.join(intents)}")
        queries.extend([
            f"{term} properties and selection",
            f"{term} mechanical properties strength density corrosion resistance",
            f"{term} processing heat treatment applications",
        ])
    return _dedupe_keep_order([q.replace("harness", "hardness").strip() for q in queries if q.strip()])[:6]


def _repair_queries_with_llm(state: dict) -> tuple:
    retrieval = state.get("retrieval") or {}
    top_hits = retrieval.get("top_hits") or []
    context = state.get("context") or []
    hit_lines = [
        f"- pg.{h.get('page')} score={h.get('score')} section={h.get('section', '')}"
        for h in top_hits[:8]
    ]
    ctx_lines = [
        f"[{c.get('index')}] pg.{c.get('page')} {c.get('section', '')}: {(c.get('text') or '')[:280]}"
        for c in context[:6]
    ]
    prompt = f"""You are a retrieval repair planner for an ASM Handbook metal-material RAG system.
Analyze why the previous retrieval or answer failed, then propose better English search queries.

User question:
{state.get('current_query') or state.get('query')}

Previous search queries:
{state.get('sub_queries')}

Top hits:
{chr(10).join(hit_lines) if hit_lines else '(none)'}

Selected context snippets:
{chr(10).join(ctx_lines) if ctx_lines else '(none)'}

Failed/weak answer:
{(state.get('answer') or '')[:800]}

Rules:
- Output only JSON.
- Keep search_queries in English.
- Prefer ASM section phrasing such as "properties and selection", "applications", "heat treatment", "forging", "corrosion resistance".
- For multi-material comparison, include one query per explicit material so no entity is dropped.
- Do not include Chinese in search_queries.

JSON schema:
{{"reason":"short diagnosis in Chinese","search_queries":["query 1","query 2"],"strategy":"short strategy in Chinese"}}"""
    try:
        raw = _call_llm([
            {"role": "system", "content": "Output only valid JSON for retrieval repair."},
            {"role": "user", "content": prompt},
        ], max_tokens=512, timeout=25)
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if not match:
            return "", []
        data = json.loads(match.group())
        queries = []
        for item in data.get("search_queries", []):
            q = str(item).replace("harness", "hardness").strip()
            if q and not re.search(r"[\u4e00-\u9fff]", q):
                queries.append(q)
        return str(data.get("reason", "") or data.get("strategy", "")), _dedupe_keep_order(queries)[:6]
    except Exception as exc:
        _log.warning("retrieval repair planner failed: %s", exc)
        return "", []


def _plan_repair_queries(state: dict) -> tuple:
    reason, llm_queries = _repair_queries_with_llm(state)
    fallback = _repair_fallback_queries(state.get("current_query") or state.get("query", ""), state)
    merged = _dedupe_keep_order((llm_queries or []) + fallback)
    if not reason:
        if not state.get("search_results"):
            reason = "上一轮没有召回候选，改用更宽的材料族和性能章节检索。"
        elif not state.get("context"):
            reason = "上一轮候选未能精选为有效上下文，改用手册章节式检索词。"
        else:
            reason = "上一轮回答判断信息不足，改用更贴近ASM章节标题和材料族的检索词。"
    return reason, merged[:6]


# ===== LangGraph State & Node Definitions =====
class AgentState(TypedDict):
    query: str
    section: Optional[str]
    history: Optional[list]
    current_query: str
    sub_queries: list
    core_entity: list
    filter_rule: str
    search_priority: str
    search_results: list
    context: list
    answer: str
    citations: list
    graph: dict
    mode: str
    structured_output: dict
    score: float
    attempts: int
    max_retries: int
    repair_attempts: int
    max_repair_attempts: int
    start_time: float
    progress_callback: Optional[callable]
    retrieval: dict

def _rewrite_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在进行查询语义拆解..."})
    resolved_query = resolve_contextual_query(state["current_query"], state.get("history"))
    if resolved_query != state["current_query"] and state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"上下文解析：{state['current_query']} → {resolved_query}"})
    mode = state.get("mode", "qa")
    rw = rewrite_query_for_mode(resolved_query, state.get("history"), mode)
    retrieval = {
        "original_query": state.get("query", state["current_query"]),
        "resolved_query": resolved_query,
        "mode": mode,
        "context_scope": f"mode:{mode}",
        "core_entity": rw["core_entity"],
        "filter_rule": rw["filter_rule"],
        "search_queries": rw["search_queries"],
        "search_priority": rw["search_priority"],
        "task_intent": rw.get("task_intent", ""),
        "used_history": resolved_query != state["current_query"],
    }
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "rewritten", "queries": rw["search_queries"], "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"查询拆解完成：{rw['search_queries']}"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _rewrite_node elapsed=%dms" % _elapsed)
    return {"current_query": resolved_query, "sub_queries": rw["search_queries"], "core_entity": rw["core_entity"], "filter_rule": rw["filter_rule"], "search_priority": rw["search_priority"], "retrieval": retrieval}

def _search_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在检索知识库..."})
    rs = search_parallel(state["sub_queries"], state.get("section"), top_k=20)
    retrieval = dict(state.get("retrieval") or {})
    retrieval["candidate_count"] = len(rs)
    retrieval["top_hits"] = [
        {
            "page": r.get("page"),
            "score": round(float(r.get("score", 0) or 0), 4),
            "section": r.get("section", ""),
            "reason": "语义/关键词混合命中",
        }
        for r in rs[:3]
    ]
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "searched", "count": len(rs), "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"检索完成，共{len(rs)}条候选"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _search_node elapsed=%dms" % _elapsed)
    return {"search_results": rs, "retrieval": retrieval}

def _select_context_node(state: AgentState) -> dict:
    _step_start = time.time()
    rs = state["search_results"]
    if not rs:
        return {"context": []}
    top_score = rs[0].get("score", 0)
    if top_score >= 0.75: dk = 8
    elif top_score >= 0.6: dk = 10
    else: dk = 12
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在精选相关上下文..."})
    is_multi_entity = len(state.get("core_entity") or []) > 1
    ctx = select_context(
        rs,
        top_k=dk,
        original_query=" ".join(state["sub_queries"]),
        search_query=" ".join(state["sub_queries"]) if is_multi_entity else (state["sub_queries"][0] if state["sub_queries"] else state["current_query"]),
        preserve_order=is_multi_entity,
    )
    retrieval = dict(state.get("retrieval") or {})
    retrieval["selected_count"] = len(ctx)
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "context_ready", "count": len(ctx), "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"精选{len(ctx)}条上下文"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _select_context_node elapsed=%dms" % _elapsed)
    return {"context": ctx, "retrieval": retrieval}

def _generate_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在构建提示词并生成回答..."})
    ad = generate_mode_answer(state["current_query"], state["context"], state.get("history"), state.get("mode", "qa"))
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _generate_node elapsed=%dms" % _elapsed)
    return {"answer": ad.get("answer", ""), "citations": ad.get("citations", state["context"][:5]), "structured_output": ad.get("structured_output", {})}

def _check_node(state: AgentState) -> dict:
    _step_start = time.time()
    ans = state["answer"]
    if state["attempts"] < state["max_retries"] and len(ans) > 30:
        if state.get("progress_callback"):
            state["progress_callback"]({"type": "log", "message": "正在进行质量检查和评估..."})
        qc = quality_check(state["current_query"], ans)
        sc = qc["score"]
        if state.get("progress_callback"):
            state["progress_callback"]({"step": "checked", "score": sc})
        return {"score": sc}
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _check_node elapsed=%dms" % _elapsed)
    return {"score": 10}

def _decide_next(state: AgentState) -> str:
    ans, sc = state["answer"], state["score"]
    if _should_repair_retrieval(state):
        return "repair"
    if state["attempts"] < state["max_retries"] and len(ans) > 30 and sc < 7:
        return "repair"
    if len(ans) < 50 or "没有找到" in ans or "未找到" in ans:
        return "fallback"
    return "output"

def _repair_node(state: AgentState) -> dict:
    _step_start = time.time()
    next_attempt = int(state.get("repair_attempts", 0) or 0) + 1
    reason, queries = _plan_repair_queries(state)
    retrieval = dict(state.get("retrieval") or {})
    history = list(retrieval.get("repair_history") or [])
    history.append({
        "attempt": next_attempt,
        "reason": reason,
        "previous_queries": list(state.get("sub_queries") or []),
        "search_queries": queries,
        "candidate_count": len(state.get("search_results") or []),
        "selected_count": len(state.get("context") or []),
    })
    retrieval["repair_history"] = history
    retrieval["repair_reason"] = reason
    retrieval["search_queries"] = queries
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"检索修复分析：{reason}", "level": "retry"})
        state["progress_callback"]({"step": "repair_planned", "queries": queries, "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"重新规划查询：{queries}", "level": "retry"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _repair_node elapsed=%dms" % _elapsed)
    return {
        "sub_queries": queries,
        "search_results": [],
        "context": [],
        "answer": "",
        "citations": [],
        "score": 0,
        "repair_attempts": next_attempt,
        "retrieval": retrieval,
    }

def _retry_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"质量评分{state['score']}/10，偏低，进行新一轮检索...", "level": "retry"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _retry_node elapsed=%dms" % _elapsed)
    return {"current_query": state["query"] + " data", "attempts": state["attempts"] + 1}

def _fallback_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "知识库中未找到相关信息，切换到大模型知识兜底...", "level": "fallback"})
    ad = generate_answer(state["current_query"], state["context"], state.get("history"), system_prompt=FALLBACK_SYSTEM_PROMPT)
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _fallback_node elapsed=%dms" % _elapsed)
    return {"answer": ad.get("answer", state["answer"])}

def _output_node(state: AgentState) -> dict:
    elapsed = int((time.time() - state["start_time"]) * 1000)
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"回答生成完成 (耗时 {elapsed}ms)", "level": "done"})
    citations = state.get("citations", state.get("context", [])[:5])
    graph = extract_knowledge_graph(state.get("query") or state.get("current_query", ""), state["answer"], citations)
    retrieval = dict(state.get("retrieval") or {})
    retrieval.setdefault("candidate_count", len(state.get("search_results", []) or []))
    retrieval.setdefault("selected_count", len(state.get("context", []) or []))
    return {"answer": state["answer"], "citations": citations, "graph": graph, "retrieval": retrieval,
            "mode": state.get("mode", "qa"), "structured_output": state.get("structured_output", {}),
            "model": "", "sub_queries": state["sub_queries"], "attempts": state["attempts"], "latency_ms": elapsed}

_agent_graph = None
def _get_graph():
    global _agent_graph
    if _agent_graph is not None:
        return _agent_graph
    wf = StateGraph(AgentState)
    wf.add_node("rewrite", _rewrite_node)
    wf.add_node("search", _search_node)
    wf.add_node("select_ctx", _select_context_node)
    wf.add_node("generate", _generate_node)
    wf.add_node("check", _check_node)
    wf.add_node("repair", _repair_node)
    wf.add_node("retry", _retry_node)
    wf.add_node("fallback", _fallback_node)
    wf.add_node("output", _output_node)
    wf.add_edge(START, "rewrite")
    wf.add_edge("rewrite", "search")
    wf.add_edge("search", "select_ctx")
    wf.add_edge("select_ctx", "generate")
    wf.add_edge("generate", "check")
    wf.add_conditional_edges("check", _decide_next, {"repair": "repair", "retry": "retry", "fallback": "fallback", "output": "output"})
    wf.add_edge("repair", "search")
    wf.add_edge("retry", "rewrite")
    wf.add_edge("fallback", "output")
    wf.add_edge("output", END)
    _agent_graph = wf.compile()
    return _agent_graph

# Manual message store (avoids MemorySaver serialization issues)
_message_store = {}

def _save_msgs(tid, msgs):
    _message_store[tid] = msgs

def _load_msgs(tid):
    return _message_store.get(tid, [])

def _sanitize_history(query: str, history: list = None, limit: int = 8) -> list:
    if not history:
        return []
    cleaned = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if role == "user" and content == query:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned[-limit:]

def agent_chat(query: str, section: str = None, history: list = None, progress_callback: callable = None, mode: str = "qa") -> dict:

    _log.info('=' * 50)
    _log.info(f'Query: {query}')
    app = _get_graph()
    initial = {
        "query": query, "section": section, "history": history,
        "current_query": query, "sub_queries": [], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡", "search_results": [],
        "context": [], "answer": "", "citations": [], "graph": {}, "mode": normalize_mode(mode), "structured_output": {}, "score": 0, "retrieval": {},
        "attempts": 1, "max_retries": 1, "repair_attempts": 0, "max_repair_attempts": 2, "start_time": time.time(),
        "progress_callback": progress_callback,
    }
    # Use only the conversation-scoped history supplied by the gateway.
    # A previous process-wide "default" memory polluted unrelated chats
    # and caused pronoun follow-ups to resolve to stale entities such as 6061.
    initial["history"] = _sanitize_history(query, history)
    result = app.invoke(initial)
    
    # Log to qa_log
    try:
        import psycopg2 as _pg
        _conn = _pg.connect(**{
            "host": "127.0.0.1", "port": 15432,
            "dbname": "foundry_kb", "user": "findmyjob",
            "password": "findmyjob_dev_password",
        })
        _cur = _conn.cursor()
        _cur.execute(
            "INSERT INTO qa_log (query, answer, retrieved_chunks, model) VALUES (%s, %s, %s, %s)",
            (query, result.get("answer", ""), json.dumps(result.get("citations", []), default=str),
             result.get("model", "")),
        )
        _conn.commit()
        _conn.close()
    except Exception as _e:
        _log.warning(f"qa_log insert failed: {_e}")
    
    return {
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "model": result.get("model", ""),
        "sub_queries": result.get("sub_queries", []),
        "attempts": result.get("attempts", 1),
        "latency_ms": result.get("latency_ms", 0),
        "thinking": "",
        "graph": result.get("graph", {}),
        "retrieval": result.get("retrieval", {}),
        "mode": result.get("mode", normalize_mode(mode)),
        "structured_output": result.get("structured_output", {}),
    }


def _call_llm(messages, max_tokens=512, timeout=30):
    last_input = (messages[-1]["content"][:200] if messages else "") + "..."
    func = messages[0]["content"][:60] if messages and messages[0]["role"] == "system" else "no system"
    _log.info(f"LLM -> {max_tokens}tok [{func}] timeout={timeout}s")
    _log.info(f"  Input: {last_input}")
    start = time.time()
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(f"{LLM_API}/chat/completions", headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}, json={"model": LLM_MODEL, "messages": messages, "max_tokens": max_tokens})
            elapsed = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                result = data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get("reasoning_content") or ""
                _log.info(f"  Resp ({elapsed}ms): {result[:250]}")
                return result
            _log.warning(f"  HTTP {resp.status_code} ({elapsed}ms)")
    except Exception as e:
        _log.warning(f"  Error: {e}")
    return ""


def _safe_json_loads(text: str):
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def _normalize_graph(raw, citations):
    if not isinstance(raw, dict):
        return {}
    nodes_in = raw.get("nodes") or []
    edges_in = raw.get("edges") or []
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        return {}

    allowed_types = {"material", "material_state", "property", "property_value", "process", "condition", "application", "source", "risk"}
    nodes = []
    seen = set()
    for idx, node in enumerate(nodes_in[:16]):
        if not isinstance(node, dict):
            continue
        label = str(node.get("label", "")).strip()
        if not label:
            continue
        node_id = str(node.get("id") or f"node_{idx + 1}").strip()
        node_id = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fa5]+", "_", node_id)[:48] or f"node_{idx + 1}"
        if node_id in seen:
            continue
        seen.add(node_id)
        node_type = str(node.get("type") or "property").strip()
        if node_type not in allowed_types:
            node_type = "property"
        if node_type == "source":
            label = re.sub(r"^(来源|Source)\s*[:：]?\s*", "", label, flags=re.I)
        nodes.append({
            "id": node_id,
            "label": label[:36],
            "type": node_type,
            "meta": str(node.get("meta") or node.get("evidence") or "")[:80],
            "page": node.get("page"),
        })

    if not nodes:
        return {}
    if not any(n["id"] == "root" for n in nodes):
        nodes[0]["id"] = "root"
        nodes[0]["type"] = nodes[0].get("type") or "material"

    node_ids = {n["id"] for n in nodes}
    edges = []
    for edge in edges_in[:24]:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", "")).strip()
        target = str(edge.get("target", "")).strip()
        if source not in node_ids or target not in node_ids or source == target:
            continue
        edges.append({
            "source": source,
            "target": target,
            "label": str(edge.get("label") or edge.get("relation") or "关联")[:16],
        })

    if not edges and len(nodes) > 1:
        edges = [{"source": "root", "target": n["id"], "label": "关联"} for n in nodes if n["id"] != "root"]

    return {
        "title": str(raw.get("title") or f"{nodes[0]['label']} 思维图谱")[:48],
        "summary": str(raw.get("summary") or f"{len(nodes)}个知识节点 / {len(edges)}条关系")[:60],
        "nodes": nodes,
        "edges": edges,
    }


def extract_knowledge_graph(query: str, answer: str, citations: list) -> dict:
    if not answer or answer.startswith("❌"):
        return {}
    citation_lines = []
    for i, c in enumerate((citations or [])[:5], 1):
        citation_lines.append(
            f"[{i}] pg.{c.get('page', '?')} {c.get('section', '')}: {(c.get('text', '') or '')[:420]}"
        )
    prompt = f"""请从下面这轮工业材料知识库问答中抽取有工程价值的知识图谱，只输出 JSON，不要解释。

要求：
1. 优先抽取材料状态、具体性能数值、温度/工艺条件、应用/风险、来源证据。
2. 不要只生成 pg.xxx 这种来源节点；来源节点只能作为证据，并连接到它支持的具体结论。
3. 属性节点尽量带数值和单位，例如“抗拉强度 310 MPa”“T6 24℃ 屈服强度 276 MPa”。
4. 边要有语义，例如“具有”“测试条件”“来源支持”“提升”“适用于”“风险”。
5. 节点数量 6-14 个，边数量 6-18 条。

JSON schema:
{{
  "title": "string",
  "summary": "string",
  "nodes": [
    {{"id": "root", "label": "主题", "type": "material", "meta": "中心主题"}},
    {{"id": "uts_310", "label": "抗拉强度 310 MPa", "type": "property_value", "meta": "T6/T651 常温典型值"}}
  ],
  "edges": [
    {{"source": "root", "target": "uts_310", "label": "具有"}}
  ]
}}

可用 type: material, material_state, property, property_value, process, condition, application, source, risk

用户问题：
{query}

最终答案：
{answer[:3500]}

引用来源：
{chr(10).join(citation_lines)}
"""
    raw = _call_llm([
        {"role": "system", "content": "You extract compact engineering knowledge graphs. Output valid JSON only."},
        {"role": "user", "content": prompt},
    ], max_tokens=1200, timeout=30)
    graph = _normalize_graph(_safe_json_loads(raw), citations)
    if graph:
        _log.info(f"  Graph extracted: {len(graph.get('nodes', []))} nodes, {len(graph.get('edges', []))} edges")
    else:
        _log.warning("  Graph extraction returned empty graph")
    return graph


def _explicit_entity_label(query: str):
    text = (query or "").strip()
    if not text:
        return None
    prop = r"硬度|颜色|色泽|外观|性能|力学性能|机械性能|热处理|热处理温度|铸造|铸造工艺|抗拉|拉伸|屈服|密度|用途|应用|成分|耐腐蚀|腐蚀"
    match = re.search(rf"(?:关于|请问|查询|分析)?\s*([\u4e00-\u9fa5A-Za-z0-9][\u4e00-\u9fa5A-Za-z0-9\-\s]{{0,24}}?)(?:的|在)?(?:{prop})", text, re.I)
    if not match:
        return None
    candidate = re.sub(r"^(关于|请问|查询|分析)\s*", "", match.group(1).strip())
    if candidate in {"它", "他", "他的", "它的", "这个", "这种", "该", "上面", "上述", "刚才", "前面"}:
        return None
    return candidate[:24] if candidate else None


def _dedupe_keep_order(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _clean_entity_label(value: str) -> str:
    item = str(value or "").strip()
    item = re.sub(r"^(那|那么|请问|查询|分析|关于)\s*", "", item)
    item = re.sub(r"(之间|之间的|之间比较|之间对比|互相比较|相互比较)$", "", item)
    item = re.sub(r"(一连串.*|一句话.*|呢|吗|吧|如何|怎么样|怎么比|比较起来)$", "", item)
    item = re.sub(r"(的|在)$", "", item).strip()
    return item[:24] if item else ""


def _entity_search_term(label: str) -> str:
    value = _clean_entity_label(label)
    lower = value.lower()
    english_map = {
        "不锈钢": "stainless steel",
        "铜合金": "copper alloy",
        "钛合金": "titanium alloy",
        "铝合金": "aluminum alloy",
        "铝合金 6061": "6061 aluminum alloy",
        "6061": "6061 aluminum alloy",
        "铁合金": "iron alloy",
        "铁基合金": "iron alloy",
        "铸铁": "cast iron",
        "钢铁": "steel",
        "碳钢": "carbon steel",
        "合金钢": "alloy steel",
        "镁合金": "magnesium alloy",
        "钻石": "diamond",
    }
    if value in english_map:
        return english_map[value]
    for rule in _ENTITY_RULES:
        if rule["label"] == value or re.fullmatch(rule["pattern"], value, re.I):
            return rule["terms"][0]
    if re.search(r"[\u4e00-\u9fff]", value):
        return value
    return lower


_SEARCH_TERM_MAP = [
    ("铝合金6061", "6061 aluminum alloy"),
    ("6061铝合金", "6061 aluminum alloy"),
    ("不锈钢", "stainless steel"),
    ("铜合金", "copper alloy"),
    ("钛合金", "titanium alloy"),
    ("铝合金", "aluminum alloy"),
    ("铁基合金", "iron alloy"),
    ("铁合金", "iron alloy"),
    ("铸铁", "cast iron"),
    ("碳钢", "carbon steel"),
    ("合金钢", "alloy steel"),
    ("钢铁", "steel"),
    ("镁合金", "magnesium alloy"),
    ("钻石", "diamond"),
    ("热处理温度", "heat treatment temperature"),
    ("热处理", "heat treatment"),
    ("铸造工艺", "casting process"),
    ("铸造", "casting"),
    ("力学性能", "mechanical properties"),
    ("机械性能", "mechanical properties"),
    ("抗拉强度", "tensile strength"),
    ("抗拉", "tensile strength"),
    ("拉伸", "tensile"),
    ("屈服强度", "yield strength"),
    ("屈服", "yield strength"),
    ("剪切强度", "shear strength"),
    ("剪切", "shear strength"),
    ("硬度", "hardness"),
    ("颜色", "color appearance"),
    ("色泽", "color appearance"),
    ("外观", "appearance"),
    ("耐腐蚀", "corrosion resistance"),
    ("腐蚀", "corrosion"),
    ("耐磨", "wear resistance"),
    ("磨损", "wear"),
    ("密度", "density"),
    ("导热", "thermal conductivity"),
    ("气孔", "casting porosity"),
    ("针孔", "pinholes porosity"),
    ("缩孔", "shrinkage cavity"),
    ("缩松", "shrinkage porosity"),
    ("热裂", "hot tearing"),
    ("冷裂", "cold cracking"),
    ("裂纹", "cracking"),
    ("夹杂", "inclusions"),
    ("砂眼", "sand inclusion"),
    ("冷隔", "cold shut"),
    ("浇不足", "misrun"),
    ("偏析", "segregation"),
    ("变形", "distortion"),
    ("硬度不够", "insufficient hardness"),
    ("硬度不足", "insufficient hardness"),
    ("失效", "failure analysis"),
    ("疲劳", "fatigue failure"),
    ("排查", "troubleshooting"),
    ("纠正", "corrective action"),
    ("高温", "high temperature"),
    ("低温", "low temperature"),
    ("海水", "seawater"),
    ("泵体", "pump body"),
    ("阀体", "valve body"),
    ("壳体", "housing"),
    ("轻量化", "lightweight"),
    ("工况", "service conditions"),
]


def _normalize_search_query_english(query: str, source_query: str = "") -> str:
    text = str(query or "").replace("harness", "hardness").strip()
    for zh, en in _SEARCH_TERM_MAP:
        text = re.sub(re.escape(zh), f" {en} ", text, flags=re.I)
    text = re.sub(r"[\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"[^0-9A-Za-z+\-./\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\b(and|or|with|between|compare|comparison)\b(?:\s+\b(and|or|with)\b)+", " ", text)
    tokens = text.split()
    if len(tokens) % 2 == 0 and tokens[: len(tokens) // 2] == tokens[len(tokens) // 2 :]:
        text = " ".join(tokens[: len(tokens) // 2])
    for _ in range(2):
        text = re.sub(r"\b([a-z]+(?:\s+[a-z]+){0,2})\s+\1\b", r"\1", text)
    if text:
        return text

    source = source_query or query
    terms = []
    rule = _entity_rule_for_text(source)
    if rule:
        terms.append(_entity_search_term(rule["label"]))
    terms.extend(_intent_terms(source))
    for zh, en in _SEARCH_TERM_MAP:
        if zh in str(source or ""):
            terms.append(en)
    normalized = " ".join(_dedupe_keep_order([t for t in terms if t])).strip().lower()
    return normalized or "casting alloy properties"


def _normalize_search_queries_english(queries: list, source_query: str = "") -> list:
    normalized = [_normalize_search_query_english(q, source_query) for q in (queries or [])]
    return _dedupe_keep_order([q for q in normalized if q])[:4]


def _explicit_entities_for_text(text: str) -> list:
    text = text or ""
    entities = []
    for rule in _ENTITY_RULES:
        if re.search(rule["pattern"], text, re.I):
            entities.append(rule["label"])

    # Generic comparison parsing: 铜合金和铝合金和铁合金和钻石相比较
    # Known material rules cover the common metals; this keeps non-metal entities
    # such as 钻石 from being swallowed by the first matched rule.
    marker = r"相比较|比较|对比|相比|差异|区别|哪个|哪种|孰|更|怎么选|选型|性能|硬度|颜色|用途|应用"
    head = re.split(marker, text, maxsplit=1)[0]
    if re.search(r"和|与|以及|及|跟|同|、|vs\.?|versus", head, re.I):
        head = re.sub(r"^(那|那么|请问|查询|分析|关于)\s*", "", head.strip())
        parts = re.split(r"\s*(?:和|与|以及|及|跟|同|、|vs\.?|versus)\s*", head, flags=re.I)
        stop = {"它", "他", "他的", "它的", "这个", "这种", "该", "上面", "上述", "刚才", "前面", "那", "那么"}
        for part in parts:
            item = _clean_entity_label(re.sub(r"(之间|哪个|哪种|怎么选|如何选|选型).*$", "", part).strip())
            if item and item not in stop and len(item) <= 24:
                entities.append(item)

    label = _explicit_entity_label(text)
    if label:
        entities.append(_clean_entity_label(label))
    return _dedupe_keep_order(entities)


def _is_multi_entity_query(text: str) -> bool:
    return len(_explicit_entities_for_text(text)) > 1


def _query_has_explicit_entity(query: str) -> bool:
    text = query or ""
    patterns = [
        r"\b\d{3,5}(?:[-\s]?[A-Za-z0-9]+)?\b",
        r"不锈钢|铝合金|铜合金|钛合金|镁合金|钢铁|碳钢|合金钢|马氏体|奥氏体|铁素体",
        r"stainless\s+steel|aluminum\s+alloy|aluminium\s+alloy|titanium\s+alloy|copper\s+alloy|carbon\s+steel",
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns) or bool(_explicit_entities_for_text(text))


def _query_needs_history(query: str) -> bool:
    text = query or ""
    if _is_multi_entity_query(text):
        return False
    if _query_has_explicit_entity(text) and not re.search(r"它|他|他的|它的|这个|这种|该|上面|上述|刚才|前面|it|this|that|above|previous", text, re.I):
        return False
    contextual_markers = [
        "它", "他", "他的", "它的", "这个", "这种", "该", "上面", "上述", "刚才", "前面", "上一轮",
        "继续", "再说", "对比一下", "相比", "哪个", "这些", "那它",
        "it", "this", "that", "above", "previous", "continue", "compare",
    ]
    if any(marker in text.lower() for marker in contextual_markers):
        return True
    return not _query_has_explicit_entity(text)

_ENTITY_RULES = [
    {
        "label": "不锈钢",
        "pattern": r"不锈钢|stainless\s+steel",
        "terms": ["stainless steel", "stainless", "不锈钢"],
        "banned": ["6061", "aluminum", "aluminium", "铝合金", "铜合金", "copper alloy"],
        "filter": "仅不锈钢",
    },
    {
        "label": "铜合金",
        "pattern": r"铜合金|copper\s+alloy|brass|bronze",
        "terms": ["copper alloy", "copper", "brass", "bronze", "铜合金"],
        "banned": ["6061", "aluminum", "aluminium", "铝合金", "stainless steel", "不锈钢"],
        "filter": "仅铜合金",
    },
    {
        "label": "钛合金",
        "pattern": r"钛合金|titanium\s+alloy",
        "terms": ["titanium alloy", "titanium", "钛合金"],
        "banned": ["6061", "aluminum", "aluminium", "铝合金", "stainless steel", "不锈钢"],
        "filter": "仅钛合金",
    },
    {
        "label": "铝合金 6061",
        "pattern": r"6061|铝合金\s*6061|6061\s*al(?:uminum|uminium)",
        "terms": ["6061", "aluminum alloy", "aluminium alloy", "铝合金"],
        "banned": ["stainless steel", "不锈钢", "copper alloy", "铜合金"],
        "filter": "仅铝合金",
    },
    {
        "label": "铝合金",
        "pattern": r"铝合金|al(?:uminum|uminium)\s+alloy",
        "terms": ["aluminum alloy", "aluminium alloy", "铝合金"],
        "banned": ["stainless steel", "不锈钢", "copper alloy", "铜合金"],
        "filter": "仅铝合金",
    },
]


def _entity_rule_for_text(text: str):
    text = text or ""
    if _is_multi_entity_query(text):
        return None
    for rule in _ENTITY_RULES:
        if re.search(rule["pattern"], text, re.I):
            return rule
    label = _explicit_entity_label(text)
    if label:
        return {
            "label": label,
            "pattern": re.escape(label),
            "terms": [label],
            "banned": ["6061", "aluminum", "aluminium", "铝合金", "stainless steel", "不锈钢", "copper alloy", "铜合金"],
            "filter": f"仅{label}",
        }
    return None


def _latest_entity_from_history(history: list = None):
    if not history:
        return None
    # Prefer explicit entities in user turns; assistant answers often mention
    # comparison materials and can pollute pronoun resolution.
    for role in ("user", "assistant"):
        for msg in reversed(history):
            if msg.get("role") != role:
                continue
            rule = _entity_rule_for_text(msg.get("content", ""))
            if rule:
                return rule
    return None


def _intent_terms(query: str):
    text = query or ""
    checks = [
        (r"硬度|hardness|harness", "hardness"),
        (r"颜色|色泽|外观|color|colour", "color appearance"),
        (r"热处理温度|热处理|固溶|退火|时效|淬火|回火|heat treatment", "heat treatment temperature"),
        (r"铸造工艺|铸造|casting", "casting process"),
        (r"力学性能|机械性能|mechanical", "mechanical properties"),
        (r"抗拉|拉伸|tensile", "tensile strength"),
        (r"屈服|yield", "yield strength"),
        (r"耐腐蚀|腐蚀|corrosion", "corrosion resistance"),
        (r"密度|density", "density"),
    ]
    return [term for pattern, term in checks if re.search(pattern, text, re.I)]


def resolve_contextual_query(query: str, history: list = None) -> str:
    if _query_has_explicit_entity(query) or not _query_needs_history(query):
        return query
    rule = _latest_entity_from_history(history)
    if not rule:
        return query
    entity = rule["label"]
    rewritten = re.sub(r"(它的|他的|它|他|这个|这种|该)", entity, query)
    if rewritten == query:
        intents = _intent_terms(query)
        if intents:
            zh_intent = {
                "hardness": "硬度",
                "color appearance": "颜色",
                "heat treatment temperature": "热处理温度",
                "casting process": "铸造工艺",
                "mechanical properties": "力学性能",
                "tensile strength": "抗拉强度",
                "yield strength": "屈服强度",
                "corrosion resistance": "耐腐蚀性能",
                "density": "密度",
            }.get(intents[0], intents[0])
            rewritten = f"{entity}的{zh_intent}"
        else:
            rewritten = f"{entity} {query}"
    return rewritten


def _deterministic_search_query(query: str) -> str:
    rule = _entity_rule_for_text(query)
    intents = _intent_terms(query)
    if not rule:
        return _normalize_search_query_english(query, query)
    entity = _entity_search_term(rule["label"])
    intent = " ".join(intents) if intents else query
    return _normalize_search_query_english(f"{entity} {intent}", query)


def _deterministic_multi_search_queries(query: str) -> list:
    entities = _explicit_entities_for_text(query)
    intents = _intent_terms(query)
    intent = " ".join(intents) if intents else "properties"
    if len(entities) <= 1:
        return [_deterministic_search_query(query)]
    search_terms = [_entity_search_term(entity) for entity in entities[:4]]
    queries = [f"{term} {intent}".strip().replace("harness", "hardness") for term in search_terms]
    return _normalize_search_queries_english(queries, query)


def _guard_multi_search_queries(query: str, search_queries: list) -> list:
    entities = _explicit_entities_for_text(query)
    if len(entities) > 1:
        return _deterministic_multi_search_queries(query)
    cleaned = _normalize_search_queries_english(search_queries, query)
    if any(re.search(r"[\u4e00-\u9fff]", q) for q in cleaned):
        return _deterministic_multi_search_queries(query)
    joined = " ".join(cleaned).lower()
    terms = [_entity_search_term(entity).lower() for entity in entities]
    missing = [term for term in terms if term and term not in joined]
    if not cleaned or len(missing) >= max(1, len(entities) // 2):
        return _deterministic_multi_search_queries(query)
    fallback = _deterministic_multi_search_queries(query)
    return _normalize_search_queries_english(_dedupe_keep_order(cleaned + fallback), query)


def _guard_search_queries(query: str, search_queries: list) -> list:
    cleaned = _normalize_search_queries_english(search_queries, query)
    if _is_multi_entity_query(query):
        return _guard_multi_search_queries(query, cleaned)
    rule = _entity_rule_for_text(query)
    if not rule:
        if _query_needs_history(query):
            leaked_terms = ["6061", "aluminum", "aluminium", "铝合金"]
            joined = " ".join(cleaned).lower()
            if any(term.lower() in joined for term in leaked_terms):
                return [_deterministic_search_query(query)]
        return cleaned or [_deterministic_search_query(query)]
    joined = " ".join(cleaned).lower()
    has_required = any(term.lower() in joined for term in rule["terms"])
    has_banned = any(term.lower() in joined for term in rule["banned"])
    if has_banned or not has_required:
        return [_deterministic_search_query(query)]
    return _normalize_search_queries_english(cleaned, query)


def rewrite_query(query: str, history: list = None) -> dict:
    multi_entities = _explicit_entities_for_text(query)
    if len(multi_entities) > 1:
        return {"search_queries": _deterministic_multi_search_queries(query), "core_entity": multi_entities, "filter_rule": f"对比实体：{'、'.join(multi_entities)}", "search_priority": "语义均衡"}
    if False and re.match(r'^[a-zA-Z0-9\s\-\.]+$', query) and len(query.split()) <= 10:
        return {"search_queries": _normalize_search_queries_english([query], query), "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡"}
    if history and _query_needs_history(query):
        users = [m.get("content", "") for m in history if m.get("role") == "user" and m.get("content")]
        if users:
            if len(users) > 10:
                old_text = "\n".join("User: " + u[:100] for u in users[:-8])
                _alloys = set(re.findall(r"\b\d{3,5}[-A-Za-z0-9]*\b", old_text))
                _props = set(re.findall(r"(strength|tensile|fatigue|hardness|corrosion|thermal|\u70ed\u5904\u7406|\u6297\u62c9|\u5c48\u670d|\u786c\u5ea6|\u529b\u5b66)", old_text, re.I))
                _parts = []
                if _alloys: _parts.append("previous alloys: " + ", ".join(sorted(_alloys)[:8]))
                if _props: _parts.append("topics: " + ", ".join(sorted(_props)[:4]))
                summary = " | ".join(_parts) if _parts else old_text[:200]
                recent = "\n".join("User: " + u[:200] for u in users[-8:])
                ctx = "[Early History Summary]\n" + summary + "\n\n[Recent History]\n" + recent
            else:
                ctx = "\n".join("User: " + u[:200] for u in users)
            user_content = ("[Conversation History]\n" + ctx
                + "\n\n[Current]\n" + query
                + "\n\nOnly use history to resolve pronouns or omitted entities. If the current query contains an explicit material, alloy, steel type, or grade, do not inject older identifiers from history.")
    else:
        user_content = query
    for attempt in range(3):
        try:
            result = _call_llm([
                {"role": "system", "content": QUERY_REWRITE_PROMPT},
                {"role": "user", "content": user_content}
            ], max_tokens=1024, timeout=60)
            if result:
                import json as _json
                match = re.search(r'\{.*?\}', result, re.DOTALL)
                if match:
                    parsed = _json.loads(match.group())
                    if isinstance(parsed, dict):
                        multi_entities = _explicit_entities_for_text(query)
                        sq = _guard_search_queries(query, parsed.get("search_queries", [query]))
                        rule = _entity_rule_for_text(query)
                        core = parsed.get("core_entity", [])
                        if len(multi_entities) > 1:
                            core = multi_entities
                        elif rule:
                            core = [rule["label"]]
                        elif _query_needs_history(query) and any(re.search(r"6061|aluminum|aluminium|铝合金", str(item), re.I) for item in (core or [])):
                            core = []
                        filter_rule = f"对比实体：{'、'.join(multi_entities)}" if len(multi_entities) > 1 else (rule["filter"] if rule else parsed.get("filter_rule", "全部"))
                        if not rule and _query_needs_history(query) and re.search(r"铝合金|aluminum|aluminium|6061", str(filter_rule), re.I):
                            filter_rule = "全部"
                        return {"search_queries": _normalize_search_queries_english(sq[:4], query), "core_entity": core, "filter_rule": filter_rule, "search_priority": parsed.get("search_priority", "语义均衡")}
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} failed, retrying...")
                time.sleep(0.5)
        except:
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} exception, retrying...")
                time.sleep(0.5)
    rule = _entity_rule_for_text(query)
    multi_entities = _explicit_entities_for_text(query)
    if len(multi_entities) > 1:
        return {"search_queries": _deterministic_multi_search_queries(query), "core_entity": multi_entities, "filter_rule": f"对比实体：{'、'.join(multi_entities)}", "search_priority": "语义均衡"}
    return {"search_queries": _normalize_search_queries_english([_deterministic_search_query(query)], query), "core_entity": [rule["label"]] if rule else [], "filter_rule": rule["filter"] if rule else "全部", "search_priority": "语义均衡"}

def search_single(query: str, section: str = None, top_k: int = 8) -> list:
    from search import search
    result = search(query, top_k=top_k, hybrid=True, section=section)
    return result.get("results", [])

def search_parallel(sub_queries, section=None, top_k=20):
    per_query = []
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(sub_queries), 3)) as executor:
        futures = {executor.submit(search_single, q, section, top_k): q for q in sub_queries}
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
    for i in range(top_k):
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
        get_reranker._model = CrossEncoder(r"E:/AgentProjects/ai-solution-architect-lab/projects/foundry-knowledge-base/processed/models/ms-marco-MiniLM-L-6-v2", device=device)
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

def select_context(results, top_k=6, original_query="", search_query="", preserve_order=False):
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
    if preserve_order:
        # Multi-entity comparison already arrives interleaved by sub-query.
        # Re-ranking with one merged query tends to collapse coverage onto the
        # first entity, so keep the balanced retrieval order.
        candidates_pool = [r for _, r in scored[:max(top_k * 3, 12)]]
        _log.info("  Rerank skipped: preserving multi-entity coverage")
    else:
        scored.sort(key=lambda x: x[0], reverse=True)
        candidates_pool = [r for _, r in scored[:max(top_k * 3, 12)]]
        # Apply cross-encoder reranker
        try:
            rq = search_query or original_query
            candidates_pool = rerank(rq, candidates_pool, top_k=max(top_k * 3, 12))
            _log.info("  Reranked: %d candidates" % len(candidates_pool))
        except Exception as re_err:
            _log.warning("  Reranker failed: %s" % re_err)
    selected = candidates_pool[:top_k]
    formatted = []
    for i, r in enumerate(selected):
        cid = r.get("chunk_id", "")
        # Determine source_id from chunk_id prefix
        src = 5 if cid.startswith("ci_page-") else 2
        formatted.append({
            "index": i + 1,
            "chunk_id": cid,
            "source_id": src,
            "page": r.get("page", 0),
            "type": r.get("type", ""),
            "text": r.get("text_full", r.get("text", "")),
            "score": round(r.get("score", 0), 4),
            "section": r.get("section", ""),
        })
    return formatted


def stream_chat(query: str, section: str = None, history: list = None, mode: str = "qa"):
    """Generator that yields progress events during agent_chat execution."""
    import queue as _q
    import threading as _t
    q = _q.Queue()

    def progress(event):
        q.put(event)

    def worker():
        try:
            result = agent_chat(query, section, history, progress_callback=progress, mode=mode)
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
from typing import TypedDict, Optional, List, Any
from langgraph.graph import StateGraph, START, END

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

LLM_API = os.environ.get("LLM_API", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
LLM_KEY = os.environ.get("LLM_KEY", "")

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
3. 信息过滤：自动识别检索结果中与当前问题材料实体不匹配的内容，回答时仅保留和用户提问金属材料、牌号、工艺或性能指标匹配的有效内容。
4. 数据真实性：表格型chunk、文本chunk同等采信，表格参数必须完整转述，不得篡改、四舍五入删减关键数值。

# 二、数值与单位强制规则（材料专业统一标准）
1. 所有力学、热学、温度、成分数值必须附带完整单位：强度统一标注MPa/ksi、温度标注℃(℉)、循环次数标注10⁶、成分标注质量百分比%；
2. 同时存在英制+公制单位时，优先展示公制(MPa/℃)，英制数值作为补充附带；
3. 合金牌号、钢种、热处理状态必须完整保留，不可简写或替换为其他材料。

# 三、标准回答结构（严格按场景匹配）
## 场景1：单一材料参数问答（如：<当前材料>的<当前性能/工艺参数>）
1. 第一段：一句话直接给出核心结论；
2. 第二段：分维度罗列全部细分数据（拉伸强度、屈服强度、疲劳强度、断裂韧性、低温性能、合金成分），每条参数附带数值+单位+引用标记；
3. 第三段：补充工况、测试条件、适用说明（如有）。

## 场景2：多材料对比提问（如<材料A>与<材料B>的<性能/工艺>对比）
强制使用Markdown对比表格，表格固定列：合金牌号&热处理态、性能指标、常温24℃参数、低温-196℃参数、数据来源；
表格内每个单元格数值附带单位，表格下方统一标注对应引用来源。

## 场景3：成分/牌号查询（如<当前牌号>元素组成）
分点列出合金各元素质量占比，标注合金体系或材料类别。

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






QUERY_REWRITE_PROMPT = """
# 角色定位
你是深耕铸造、金属材料工程的检索策略专家，精通材料手册检索逻辑，专为工业私有材料知识库设计检索方案。
知识库内容：各类变形铝合金、铜合金、永磁材料、铸造工艺、力学/热学性能、高低温测试参数、牌号标准、加工规范；检索底层为FTS全文检索(BM25) + 稠密向量检索 + RRF排名融合混合架构。

# 核心任务
接收用户铸造/金属材料类提问，输出一套可直接交付检索引擎执行的标准化检索策略。

# 强制拆解&生成规则
## 1. 核心实体提取
完整拆分问题内全部检索关键要素，分为四类：
1) 材料实体：合金牌号、热处理状态、合金体系（必须来自当前问题或已解析上下文，不得从示例继承）
2) 性能实体：抗拉强度、屈服强度、疲劳强度、断裂韧性、热膨胀系数等
3) 工况实体：测试温度(-196℃/常温24℃)、循环次数、焊接/锻造工艺
4) 查询意图：单参数查询、多牌号对比、高低温性能、成分查询、表格参数查询

## 2. 检索Query生成规范（适配混合检索）
1. 输出1~4条英文专业检索语句；
2. 每条Query必须携带核心牌号、热处理态、测试温度、性能指标；
3. 复合类问题拆分维度：力学疲劳单独一条、低温韧性单独一条、合金成分单独一条；
4. 使用标准专业术语，禁止口语化描述，每条控制在30词以内。

## 3. 输出硬性约束
仅输出标准单行JSON，禁止额外说明、换行、注释，字段不可缺失：
1. core_entity：数组，存放提取到的全部关键实体；
2. filter_rule：字符串，明确检索时的文档过滤逻辑（如"仅铝合金"、"排除铜合金"、"全部"）；
3. search_queries：数组，1~4条英文检索语句；
4. search_priority：字符串，"关键词优先"或"语义均衡"，材料牌号类固定"关键词优先"
5. 严禁从示例中复制材料实体；只能使用当前问题或已解析上下文中的材料。

# 输出示例（抽象模板，尖括号内容必须替换为当前问题/上下文中的真实实体，禁止原样输出）
{"core_entity": ["<当前材料实体>","<当前性能或工艺意图>"], "filter_rule": "仅<当前材料类别或牌号>", "search_queries": ["<current material/entity> <current property/process intent>"], "search_priority": "语义均衡"}
"""

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
    if history and _query_needs_history(query):
        for msg in history[-8:]:
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
        with httpx.Client(timeout=60, trust_env=False) as client:
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


# ===== LangGraph State & Node Definitions =====
class AgentState(TypedDict):
    query: str
    section: Optional[str]
    history: Optional[list]
    current_query: str
    sub_queries: list
    core_entity: list
    filter_rule: str
    search_priority: str
    search_results: list
    context: list
    answer: str
    citations: list
    graph: dict
    mode: str
    structured_output: dict
    score: float
    attempts: int
    max_retries: int
    repair_attempts: int
    max_repair_attempts: int
    start_time: float
    progress_callback: Optional[callable]
    retrieval: dict

def _rewrite_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在进行查询语义拆解..."})
    resolved_query = resolve_contextual_query(state["current_query"], state.get("history"))
    if resolved_query != state["current_query"] and state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"上下文解析：{state['current_query']} → {resolved_query}"})
    mode = state.get("mode", "qa")
    rw = rewrite_query_for_mode(resolved_query, state.get("history"), mode)
    retrieval = {
        "original_query": state.get("query", state["current_query"]),
        "resolved_query": resolved_query,
        "mode": mode,
        "context_scope": f"mode:{mode}",
        "core_entity": rw["core_entity"],
        "filter_rule": rw["filter_rule"],
        "search_queries": rw["search_queries"],
        "search_priority": rw["search_priority"],
        "task_intent": rw.get("task_intent", ""),
        "used_history": resolved_query != state["current_query"],
    }
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "rewritten", "queries": rw["search_queries"], "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"查询拆解完成：{rw['search_queries']}"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _rewrite_node elapsed=%dms" % _elapsed)
    return {"current_query": resolved_query, "sub_queries": rw["search_queries"], "core_entity": rw["core_entity"], "filter_rule": rw["filter_rule"], "search_priority": rw["search_priority"], "retrieval": retrieval}

def _search_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在检索知识库..."})
    rs = search_parallel(state["sub_queries"], state.get("section"), top_k=20)
    retrieval = dict(state.get("retrieval") or {})
    retrieval["candidate_count"] = len(rs)
    retrieval["top_hits"] = [
        {
            "page": r.get("page"),
            "score": round(float(r.get("score", 0) or 0), 4),
            "section": r.get("section", ""),
            "reason": "语义/关键词混合命中",
        }
        for r in rs[:3]
    ]
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "searched", "count": len(rs), "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"检索完成，共{len(rs)}条候选"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _search_node elapsed=%dms" % _elapsed)
    return {"search_results": rs, "retrieval": retrieval}

def _select_context_node(state: AgentState) -> dict:
    _step_start = time.time()
    rs = state["search_results"]
    if not rs:
        return {"context": []}
    top_score = rs[0].get("score", 0)
    if top_score >= 0.75: dk = 8
    elif top_score >= 0.6: dk = 10
    else: dk = 12
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在精选相关上下文..."})
    is_multi_entity = len(state.get("core_entity") or []) > 1
    merged_query = " ".join(state["sub_queries"])
    ctx = select_context(
        rs,
        top_k=dk,
        original_query=merged_query,
        search_query=merged_query if is_multi_entity else (state["sub_queries"][0] if state["sub_queries"] else state["current_query"]),
        preserve_order=is_multi_entity,
    )
    retrieval = dict(state.get("retrieval") or {})
    retrieval["selected_count"] = len(ctx)
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "context_ready", "count": len(ctx), "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"精选{len(ctx)}条上下文"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _select_context_node elapsed=%dms" % _elapsed)
    return {"context": ctx, "retrieval": retrieval}

def _generate_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在构建提示词并生成回答..."})
    ad = generate_mode_answer(state["current_query"], state["context"], state.get("history"), state.get("mode", "qa"))
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _generate_node elapsed=%dms" % _elapsed)
    return {"answer": ad.get("answer", ""), "citations": ad.get("citations", state["context"][:5]), "structured_output": ad.get("structured_output", {})}

def _check_node(state: AgentState) -> dict:
    _step_start = time.time()
    ans = state["answer"]
    if state["attempts"] < state["max_retries"] and len(ans) > 30:
        if state.get("progress_callback"):
            state["progress_callback"]({"type": "log", "message": "正在进行质量检查和评估..."})
        qc = quality_check(state["current_query"], ans)
        sc = qc["score"]
        if state.get("progress_callback"):
            state["progress_callback"]({"step": "checked", "score": sc})
        return {"score": sc}
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _check_node elapsed=%dms" % _elapsed)
    return {"score": 10}

def _decide_next(state: AgentState) -> str:
    ans, sc = state["answer"], state["score"]
    if _should_repair_retrieval(state):
        return "repair"
    if state["attempts"] < state["max_retries"] and len(ans) > 30 and sc < 7:
        return "repair"
    if len(ans) < 50 or "没有找到" in ans or "未找到" in ans:
        return "fallback"
    return "output"

def _repair_node(state: AgentState) -> dict:
    _step_start = time.time()
    next_attempt = int(state.get("repair_attempts", 0) or 0) + 1
    reason, queries = _plan_repair_queries(state)
    retrieval = dict(state.get("retrieval") or {})
    history = list(retrieval.get("repair_history") or [])
    history.append({
        "attempt": next_attempt,
        "reason": reason,
        "previous_queries": list(state.get("sub_queries") or []),
        "search_queries": queries,
        "candidate_count": len(state.get("search_results") or []),
        "selected_count": len(state.get("context") or []),
    })
    retrieval["repair_history"] = history
    retrieval["repair_reason"] = reason
    retrieval["search_queries"] = queries
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"检索修复分析：{reason}", "level": "retry"})
        state["progress_callback"]({"step": "repair_planned", "queries": queries, "retrieval": retrieval})
        state["progress_callback"]({"type": "log", "message": f"重新规划查询：{queries}", "level": "retry"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _repair_node elapsed=%dms" % _elapsed)
    return {
        "sub_queries": queries,
        "search_results": [],
        "context": [],
        "answer": "",
        "citations": [],
        "score": 0,
        "repair_attempts": next_attempt,
        "retrieval": retrieval,
    }

def _retry_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"质量评分{state['score']}/10，偏低，进行新一轮检索...", "level": "retry"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _retry_node elapsed=%dms" % _elapsed)
    return {"current_query": state["query"] + " data", "attempts": state["attempts"] + 1}

def _fallback_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "知识库中未找到相关信息，切换到大模型知识兜底...", "level": "fallback"})
    ad = generate_answer(state["current_query"], state["context"], state.get("history"), system_prompt=FALLBACK_SYSTEM_PROMPT)
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _fallback_node elapsed=%dms" % _elapsed)
    return {"answer": ad.get("answer", state["answer"])}

def _output_node(state: AgentState) -> dict:
    elapsed = int((time.time() - state["start_time"]) * 1000)
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": f"回答生成完成 (耗时 {elapsed}ms)", "level": "done"})
    citations = state.get("citations", state.get("context", [])[:5])
    graph = extract_knowledge_graph(state.get("query") or state.get("current_query", ""), state["answer"], citations)
    retrieval = dict(state.get("retrieval") or {})
    retrieval.setdefault("candidate_count", len(state.get("search_results", []) or []))
    retrieval.setdefault("selected_count", len(state.get("context", []) or []))
    return {"answer": state["answer"], "citations": citations, "graph": graph, "retrieval": retrieval,
            "mode": state.get("mode", "qa"), "structured_output": state.get("structured_output", {}),
            "model": "", "sub_queries": state["sub_queries"], "attempts": state["attempts"], "latency_ms": elapsed}

_agent_graph = None
def _get_graph():
    global _agent_graph
    if _agent_graph is not None:
        return _agent_graph
    wf = StateGraph(AgentState)
    wf.add_node("rewrite", _rewrite_node)
    wf.add_node("search", _search_node)
    wf.add_node("select_ctx", _select_context_node)
    wf.add_node("generate", _generate_node)
    wf.add_node("check", _check_node)
    wf.add_node("repair", _repair_node)
    wf.add_node("retry", _retry_node)
    wf.add_node("fallback", _fallback_node)
    wf.add_node("output", _output_node)
    wf.add_edge(START, "rewrite")
    wf.add_edge("rewrite", "search")
    wf.add_edge("search", "select_ctx")
    wf.add_edge("select_ctx", "generate")
    wf.add_edge("generate", "check")
    wf.add_conditional_edges("check", _decide_next, {"repair": "repair", "retry": "retry", "fallback": "fallback", "output": "output"})
    wf.add_edge("repair", "search")
    wf.add_edge("retry", "rewrite")
    wf.add_edge("fallback", "output")
    wf.add_edge("output", END)
    _agent_graph = wf.compile()
    return _agent_graph

# Manual message store (avoids MemorySaver serialization issues)
_message_store = {}

def _save_msgs(tid, msgs):
    _message_store[tid] = msgs

def _load_msgs(tid):
    return _message_store.get(tid, [])

def agent_chat(query: str, section: str = None, history: list = None, progress_callback: callable = None, mode: str = "qa") -> dict:

    _log.info('=' * 50)
    _log.info(f'Query: {query}')
    app = _get_graph()
    initial = {
        "query": query, "section": section, "history": history,
        "current_query": query, "sub_queries": [], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡", "search_results": [],
        "context": [], "answer": "", "citations": [], "graph": {}, "mode": normalize_mode(mode), "structured_output": {}, "score": 0, "retrieval": {},
        "attempts": 1, "max_retries": 1, "repair_attempts": 0, "max_repair_attempts": 2, "start_time": time.time(),
        "progress_callback": progress_callback,
    }
    # Use only the conversation-scoped history supplied by the gateway.
    # Never merge process-wide "default" memory; it mixes unrelated chats.
    initial["history"] = _sanitize_history(query, history)
    result = app.invoke(initial)
    
    # Log to qa_log
    try:
        import psycopg2 as _pg
        _conn = _pg.connect(**{
            "host": "127.0.0.1", "port": 15432,
            "dbname": "foundry_kb", "user": "findmyjob",
            "password": "findmyjob_dev_password",
        })
        _cur = _conn.cursor()
        _cur.execute(
            "INSERT INTO qa_log (query, answer, retrieved_chunks, model) VALUES (%s, %s, %s, %s)",
            (query, result.get("answer", ""), json.dumps(result.get("citations", []), default=str),
             result.get("model", "")),
        )
        _conn.commit()
        _conn.close()
    except Exception as _e:
        _log.warning(f"qa_log insert failed: {_e}")
    
    return {
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "model": result.get("model", ""),
        "sub_queries": result.get("sub_queries", []),
        "attempts": result.get("attempts", 1),
        "latency_ms": result.get("latency_ms", 0),
        "thinking": "",
        "graph": result.get("graph", {}),
        "retrieval": result.get("retrieval", {}),
        "mode": result.get("mode", normalize_mode(mode)),
        "structured_output": result.get("structured_output", {}),
    }


def _call_llm(messages, max_tokens=512, timeout=30):
    last_input = (messages[-1]["content"][:200] if messages else "") + "..."
    func = messages[0]["content"][:60] if messages and messages[0]["role"] == "system" else "no system"
    _log.info(f"LLM -> {max_tokens}tok [{func}] timeout={timeout}s")
    _log.info(f"  Input: {last_input}")
    start = time.time()
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(f"{LLM_API}/chat/completions", headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}, json={"model": LLM_MODEL, "messages": messages, "max_tokens": max_tokens})
            elapsed = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                result = data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get("reasoning_content") or ""
                _log.info(f"  Resp ({elapsed}ms): {result[:250]}")
                return result
            _log.warning(f"  HTTP {resp.status_code} ({elapsed}ms)")
    except Exception as e:
        _log.warning(f"  Error: {e}")
    return ""


SUPPORTED_MODES = {"qa", "requirement_clarification", "solution_draft", "selection_matrix", "defect_diagnosis"}


def normalize_mode(mode: str = "qa") -> str:
    mode = (mode or "qa").strip()
    return mode if mode in SUPPORTED_MODES else "qa"


def _context_to_text(context: list) -> str:
    parts = []
    for c in context or []:
        source = f"[{c.get('index', len(parts) + 1)}] pg.{c.get('page', '?')}"
        if c.get("section"):
            source += f" ({c.get('section')})"
        parts.append(f"{source}\n{c.get('text', '')}")
    return "\n\n---\n\n".join(parts)


def _extract_json_object(text: str) -> dict:
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _mode_prompt(mode: str) -> str:
    if mode == "requirement_clarification":
        return """你是材料铸造行业的解决方案需求澄清专家。请严格基于检索结果和用户问题输出。

输出必须是一个 JSON 对象，禁止 Markdown 包裹，字段如下：
{
  "answer": "面向工程师的中文摘要，说明已识别需求、关键缺口和下一步",
  "structured_output": {
    "type": "requirement_clarification",
    "known_conditions": ["已明确的材料/工况/性能/工艺条件"],
    "missing_conditions": ["还缺少的约束条件"],
    "risks": ["需求不清导致的工程风险"],
    "questions_to_ask": ["需要继续追问客户的问题"],
    "preliminary_direction": ["可先行判断的方案方向"],
    "next_steps": ["建议下一步动作"]
  }
}

要求：所有可验证的数据和结论必须来自检索结果；无法确认的内容放入 missing_conditions 或 questions_to_ask。"""
    if mode == "solution_draft":
        return """你是材料铸造行业的解决方案工程师。请严格基于检索结果和用户问题输出方案草案。

输出必须是一个 JSON 对象，禁止 Markdown 包裹，字段如下：
{
  "answer": "面向工程师的中文方案摘要，包含推荐方向、依据和风险",
  "structured_output": {
    "type": "solution_draft",
    "requirement_summary": ["需求归纳"],
    "operating_conditions": ["工况与约束"],
    "candidate_materials": ["候选材料或牌号"],
    "recommended_processes": ["推荐工艺/热处理/铸造路线"],
    "risks": ["技术风险和验证风险"],
    "alternatives": ["备选路线"],
    "evidence": ["来自检索结果的依据，保留引用编号"],
    "open_questions": ["仍需确认的问题"],
    "next_steps": ["建议验证或交付步骤"]
  }
}

要求：不要编造手册外参数；对比类问题优先输出候选材料、性能维度、风险和验证步骤。"""
    if mode == "selection_matrix":
        return """你是材料铸造行业的选型矩阵分析师。请严格基于检索结果和用户问题，输出候选材料/工艺路线的工程决策矩阵。

输出必须是一个 JSON 对象，禁止 Markdown 包裹，字段如下：
{
  "answer": "面向解决方案工程师的中文决策摘要，说明推荐候选、关键取舍和证据不足处",
  "structured_output": {
    "type": "selection_matrix",
    "requirement_summary": ["从用户问题提炼出的工况、性能目标、预算、制造约束"],
    "criteria": ["评价维度，例如耐腐蚀、强度、铸造/加工适配、成本、证据充分度"],
    "rows": [
      {
        "candidate": "候选材料、牌号或工艺路线",
        "category": "material",
        "fit_score": 0,
        "criteria_scores": {"评价维度": "high|medium|low|unknown"},
        "advantages": ["基于检索结果的优势"],
        "risks": ["基于检索结果的风险或证据不足"],
        "process_fit": "铸造、热处理或加工适配说明",
        "cost_level": "low|medium|high|unknown",
        "evidence": ["检索依据，保留引用编号"],
        "citations": [1]
      }
    ],
    "recommendation": "推荐路线和理由",
    "decision_notes": ["关键取舍说明"],
    "open_questions": ["仍需客户或工程侧确认的问题"]
  }
}

要求：
1. rows 每个候选项必须独立判断，不能把一个候选的证据套到另一个候选。
2. fit_score 只能在证据足够时给出 0-100；证据不足可省略或写 null。
3. 每个关键优势、风险和证据必须来自检索结果；不确定时写入 risks 或 open_questions。
4. 输出中文，但 citation 编号必须保留。"""
    if mode == "defect_diagnosis":
        return """你是材料铸造行业的缺陷与失效诊断工程师。请严格基于检索结果和用户问题，输出可执行的现场排查报告。

输出必须是一个 JSON 对象，禁止 Markdown 包裹，字段如下：
{
  "answer": "面向工程师的中文诊断摘要，说明最可能原因、排查优先级和证据不足处",
  "structured_output": {
    "type": "defect_diagnosis",
    "symptom_summary": ["从用户问题提取的缺陷现象、材料、工艺阶段、环境"],
    "possible_causes": [
      {
        "cause": "可能原因",
        "likelihood": "high|medium|low",
        "evidence": "来自检索结果的依据，保留引用编号",
        "inspection_method": "现场验证或检测方法",
        "corrective_action": "对应纠正措施",
        "citations": [1]
      }
    ],
    "inspection_steps": ["建议现场排查顺序"],
    "process_checks": ["熔炼、浇注、模具/砂型、热处理、环境等过程检查点"],
    "corrective_actions": ["纠正或预防措施"],
    "missing_field_info": ["仍需用户补充的现场信息"],
    "severity": "high|medium|low|unknown"
  }
}

要求：
1. 不要只解释缺陷定义，必须输出排查动作。
2. 可能原因必须按 likelihood 排序。
3. 证据不足时必须写入 missing_field_info，不能编造现场事实。
4. 关键判断必须来自检索结果；没有证据时明确标注待确认。"""
    return IMPROVED_SYSTEM_PROMPT


def _fallback_structured_output(mode: str, answer: str) -> dict:
    if mode == "requirement_clarification":
        return {
            "type": mode,
            "known_conditions": [],
            "missing_conditions": ["结构化解析失败，请根据文本回答继续补充需求条件"],
            "risks": [],
            "questions_to_ask": [],
            "preliminary_direction": [],
            "next_steps": [],
            "raw_answer": answer,
        }
    if mode == "solution_draft":
        return {
            "type": mode,
            "requirement_summary": [],
            "operating_conditions": [],
            "candidate_materials": [],
            "recommended_processes": [],
            "risks": [],
            "alternatives": [],
            "evidence": [],
            "open_questions": [],
            "next_steps": [],
            "raw_answer": answer,
        }
    if mode == "selection_matrix":
        return {
            "type": mode,
            "requirement_summary": [],
            "criteria": ["耐腐蚀", "强度", "工艺适配", "成本", "证据充分度"],
            "rows": [],
            "recommendation": "结构化解析失败，请根据文本回答重新评估候选项。",
            "decision_notes": [],
            "open_questions": [],
            "raw_answer": answer,
        }
    if mode == "defect_diagnosis":
        return {
            "type": mode,
            "symptom_summary": [],
            "possible_causes": [],
            "inspection_steps": [],
            "process_checks": [],
            "corrective_actions": [],
            "missing_field_info": ["结构化解析失败，请补充材料、工艺阶段、缺陷位置和发生频率。"],
            "severity": "unknown",
            "raw_answer": answer,
        }
    return {}


def generate_mode_answer(query: str, context: list, history: list = None, mode: str = "qa") -> dict:
    mode = normalize_mode(mode)
    if mode == "qa":
        data = generate_answer(query, context, history)
        data["structured_output"] = {}
        return data

    context_text = _context_to_text(context)
    messages = [{"role": "system", "content": _mode_prompt(mode)}]
    if history and _query_needs_history(query):
        for msg in history[-8:]:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({
        "role": "user",
        "content": f"检索结果：\n\n{context_text}\n\n---\n\n用户问题：{query}\n\n请输出符合要求的 JSON。",
    })
    raw = _call_llm(messages, max_tokens=2400, timeout=60)
    parsed = _extract_json_object(raw)
    answer = (parsed.get("answer") if isinstance(parsed, dict) else "") or raw.strip()
    structured = parsed.get("structured_output") if isinstance(parsed, dict) else {}
    if not isinstance(structured, dict):
        structured = {}
    structured.setdefault("type", mode)
    if not parsed:
        structured = _fallback_structured_output(mode, answer)
    return {
        "answer": answer,
        "citations": (context or [])[:5],
        "thinking": "",
        "structured_output": structured,
    }


MODE_REWRITE_PROMPTS = {
    "requirement_clarification": """You are a retrieval planner for a casting/materials requirement clarification workflow.

The user is not only asking for a factual answer. Your goal is to identify what engineering facts should be retrieved to clarify a customer requirement.

Rules:
1. Output ONLY one JSON object.
2. search_queries must be English because the handbook corpus is English.
3. Do not copy examples or inject old entities from history unless the current query has pronouns or omitted entities.
4. Prefer broad engineering dimensions: material class, service environment, casting process, heat treatment, corrosion, mechanical properties, temperature, hardness, manufacturability.
5. If the requirement lacks a material, search by application/environment/process instead of guessing a material.
6. Keep 2-4 concise queries, each under 12 English words.

JSON schema:
{"core_entity":[],"filter_rule":"需求澄清：按当前需求限定","search_queries":[],"search_priority":"语义均衡","task_intent":"clarify customer requirement"}""",
    "solution_draft": """You are a retrieval planner for a casting/materials solution drafting workflow.

The user needs an engineering solution draft, not a single factual answer. Your retrieval should gather candidate materials, process routes, operating constraints, risks, and comparable properties.

Rules:
1. Output ONLY one JSON object.
2. search_queries must be English because the handbook corpus is English.
3. Do not copy examples or inject old entities from history unless the current query has pronouns or omitted entities.
4. For explicit multi-material comparison, query each material separately; avoid one long mixed query.
5. For vague solution requests, retrieve by application, service environment, casting process, corrosion resistance, strength, heat treatment, and manufacturability.
6. Keep 2-4 concise queries, each under 12 English words.

JSON schema:
{"core_entity":[],"filter_rule":"方案草案：按候选材料和工况限定","search_queries":[],"search_priority":"语义均衡","task_intent":"draft engineering solution"}""",
    "selection_matrix": """You are a retrieval planner for a materials and casting selection matrix workflow.

The user needs an engineering decision matrix, not a single factual answer. Retrieval must support candidate-by-candidate comparison and evidence-backed criteria.

Rules:
1. Output ONLY one JSON object.
2. search_queries must be English because the handbook corpus is English.
3. If the user lists multiple candidates, produce one concise query per candidate.
4. If the user gives an application or service condition, retrieve application, environment, material selection, corrosion, strength, process fit, and cost/manufacturability evidence.
5. Avoid mixed long queries such as "candidate A candidate B candidate C comparison"; split candidates instead.
6. Keep 2-4 concise queries, each under 12 English words.

JSON schema:
{"core_entity":[],"filter_rule":"选型矩阵：按候选项和评价维度限定","search_queries":[],"search_priority":"语义均衡","task_intent":"build selection matrix"}""",
    "defect_diagnosis": """You are a retrieval planner for a casting defects and failure diagnosis workflow.

The user needs troubleshooting, not a factual definition. Retrieval must support defect symptoms, likely causes, inspection steps, process checks, and corrective actions.

Rules:
1. Output ONLY one JSON object.
2. search_queries must be English because the handbook corpus is English.
3. Preserve explicit material/process context when present, for example "aluminum alloy casting porosity".
4. Prefer defect and failure terminology: porosity, shrinkage cavity, shrinkage porosity, hot tearing, cracking, inclusions, cold shut, misrun, hardness failure, fatigue failure, corrosion failure.
5. Include one query for causes/troubleshooting and one query for corrective actions when possible.
6. Keep 2-4 concise queries, each under 12 English words.

JSON schema:
{"core_entity":[],"filter_rule":"缺陷诊断：按缺陷症状和工艺阶段限定","search_queries":[],"search_priority":"语义均衡","task_intent":"diagnose casting defect"}""",
}


def _fallback_mode_search_queries(query: str, mode: str) -> list:
    entities = _explicit_entities_for_text(query)
    if entities:
        base = _deterministic_multi_search_queries(query) if len(entities) > 1 else [_deterministic_search_query(query)]
    else:
        base = [_deterministic_search_query(query)]
    if mode == "requirement_clarification":
        extras = [
            "casting alloy service environment requirements",
            "material selection corrosion temperature strength",
        ]
    elif mode == "solution_draft":
        extras = [
            "casting alloy material selection properties",
            "casting process heat treatment mechanical properties",
        ]
    elif mode == "selection_matrix":
        extras = [
            "material selection corrosion strength cost",
            "casting process manufacturability properties",
            "alloy service environment selection",
        ]
    elif mode == "defect_diagnosis":
        extras = [
            "casting defects causes troubleshooting",
            "casting defects corrective actions",
            "foundry process defects inspection",
        ]
    else:
        extras = []
    queries = []
    for item in base + extras:
        if item and item not in queries:
            queries.append(item)
    return queries[:4]


def rewrite_query_for_mode(query: str, history: list = None, mode: str = "qa") -> dict:
    mode = normalize_mode(mode)
    if mode == "qa":
        data = rewrite_query(query, history)
        data["search_queries"] = _normalize_search_queries_english(data.get("search_queries", []), query)
        data["task_intent"] = "knowledge question answering"
        return data

    multi_entities = _explicit_entities_for_text(query)
    if len(multi_entities) > 1:
        return {
            "search_queries": _normalize_search_queries_english(_deterministic_multi_search_queries(query), query),
            "core_entity": multi_entities,
            "filter_rule": f"{'缺陷诊断' if mode == 'defect_diagnosis' else ('选型矩阵' if mode == 'selection_matrix' else ('方案草案' if mode == 'solution_draft' else '需求澄清'))}：对比实体：{'、'.join(multi_entities)}",
            "search_priority": "语义均衡",
            "task_intent": "diagnose casting defect" if mode == "defect_diagnosis" else ("build selection matrix" if mode == "selection_matrix" else ("compare candidates for solution" if mode == "solution_draft" else "clarify multi-entity requirement")),
        }

    if history and _query_needs_history(query):
        users = [m.get("content", "") for m in history if m.get("role") == "user" and m.get("content")]
        history_text = "\n".join("User: " + u[:220] for u in users[-6:])
        user_content = (
            "[Same-mode Conversation History]\n"
            + history_text
            + "\n\n[Current]\n"
            + query
            + "\n\nOnly use this history to resolve pronouns or omitted entities in the same task mode."
        )
    else:
        user_content = query

    try:
        result = _call_llm([
            {"role": "system", "content": MODE_REWRITE_PROMPTS[mode]},
            {"role": "user", "content": user_content},
        ], max_tokens=700, timeout=45)
        parsed = _extract_json_object(result)
        if parsed:
            rule = _entity_rule_for_text(query)
            if mode == "defect_diagnosis" and rule and rule["label"] not in {item["label"] for item in _ENTITY_RULES}:
                rule = None
            search_queries = parsed.get("search_queries") or _fallback_mode_search_queries(query, mode)
            guarded = _guard_search_queries(query, search_queries)
            if not guarded:
                guarded = _fallback_mode_search_queries(query, mode)
            core = parsed.get("core_entity") or []
            if rule:
                core = [rule["label"]]
            return {
                "search_queries": _normalize_search_queries_english(guarded[:4], query),
                "core_entity": core if isinstance(core, list) else [],
                "filter_rule": parsed.get("filter_rule") or (rule["filter"] if rule else "全部"),
                "search_priority": parsed.get("search_priority", "语义均衡"),
                "task_intent": parsed.get("task_intent") or ("diagnose casting defect" if mode == "defect_diagnosis" else ("draft engineering solution" if mode == "solution_draft" else "clarify customer requirement")),
            }
    except Exception as e:
        _log.warning(f"mode rewrite failed: {e}")

    rule = _entity_rule_for_text(query)
    if mode == "defect_diagnosis" and rule and rule["label"] not in {item["label"] for item in _ENTITY_RULES}:
        rule = None
    return {
        "search_queries": _normalize_search_queries_english(_fallback_mode_search_queries(query, mode), query),
        "core_entity": [rule["label"]] if rule else [],
        "filter_rule": rule["filter"] if rule else ("缺陷诊断：按缺陷症状和工艺阶段检索" if mode == "defect_diagnosis" else ("选型矩阵：按候选项和评价维度检索" if mode == "selection_matrix" else ("方案草案：按工况和候选路线检索" if mode == "solution_draft" else "需求澄清：按工况和缺失条件检索"))),
        "search_priority": "语义均衡",
        "task_intent": "diagnose casting defect" if mode == "defect_diagnosis" else ("build selection matrix" if mode == "selection_matrix" else ("draft engineering solution" if mode == "solution_draft" else "clarify customer requirement")),
    }


def rewrite_query(query: str, history: list = None) -> dict:
    multi_entities = _explicit_entities_for_text(query)
    if len(multi_entities) > 1:
        return {"search_queries": _normalize_search_queries_english(_deterministic_multi_search_queries(query), query), "core_entity": multi_entities, "filter_rule": f"对比实体：{'、'.join(multi_entities)}", "search_priority": "语义均衡"}
    if False and re.match(r'^[a-zA-Z0-9\s\-\.]+$', query) and len(query.split()) <= 10:
        return {"search_queries": _normalize_search_queries_english([query], query), "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡"}
    if history and _query_needs_history(query):
        users = [m.get("content", "") for m in history if m.get("role") == "user" and m.get("content")]
        if users:
            if len(users) > 10:
                old_text = "\n".join("User: " + u[:100] for u in users[:-8])
                _alloys = set(re.findall(r"\b\d{3,5}[-A-Za-z0-9]*\b", old_text))
                _props = set(re.findall(r"(strength|tensile|fatigue|hardness|corrosion|thermal|\u70ed\u5904\u7406|\u6297\u62c9|\u5c48\u670d|\u786c\u5ea6|\u529b\u5b66)", old_text, re.I))
                _parts = []
                if _alloys: _parts.append("previous alloys: " + ", ".join(sorted(_alloys)[:8]))
                if _props: _parts.append("topics: " + ", ".join(sorted(_props)[:4]))
                summary = " | ".join(_parts) if _parts else old_text[:200]
                recent = "\n".join("User: " + u[:200] for u in users[-8:])
                ctx = "[Early History Summary]\n" + summary + "\n\n[Recent History]\n" + recent
            else:
                ctx = "\n".join("User: " + u[:200] for u in users)
            user_content = ("[Conversation History]\n" + ctx
                + "\n\n[Current]\n" + query
                + "\n\nOnly use history to resolve pronouns or omitted entities. If the current query contains an explicit material, alloy, steel type, or grade, do not inject older identifiers from history.")
    else:
        user_content = query
    for attempt in range(3):
        try:
            result = _call_llm([
                {"role": "system", "content": QUERY_REWRITE_PROMPT},
                {"role": "user", "content": user_content}
            ], max_tokens=1024, timeout=60)
            if result:
                import json as _json
                match = re.search(r'\{.*?\}', result, re.DOTALL)
                if match:
                    parsed = _json.loads(match.group())
                    if isinstance(parsed, dict):
                        multi_entities = _explicit_entities_for_text(query)
                        sq = _guard_search_queries(query, parsed.get("search_queries", [query]))
                        rule = _entity_rule_for_text(query)
                        core = parsed.get("core_entity", [])
                        if len(multi_entities) > 1:
                            core = multi_entities
                        elif rule:
                            core = [rule["label"]]
                        elif _query_needs_history(query) and any(re.search(r"6061|aluminum|aluminium|铝合金", str(item), re.I) for item in (core or [])):
                            core = []
                        filter_rule = f"对比实体：{'、'.join(multi_entities)}" if len(multi_entities) > 1 else (rule["filter"] if rule else parsed.get("filter_rule", "全部"))
                        if not rule and _query_needs_history(query) and re.search(r"铝合金|aluminum|aluminium|6061", str(filter_rule), re.I):
                            filter_rule = "全部"
                        return {"search_queries": _normalize_search_queries_english(sq[:4], query), "core_entity": core, "filter_rule": filter_rule, "search_priority": parsed.get("search_priority", "语义均衡")}
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} failed, retrying...")
                time.sleep(0.5)
        except:
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} exception, retrying...")
                time.sleep(0.5)
    rule = _entity_rule_for_text(query)
    multi_entities = _explicit_entities_for_text(query)
    if len(multi_entities) > 1:
        return {"search_queries": _normalize_search_queries_english(_deterministic_multi_search_queries(query), query), "core_entity": multi_entities, "filter_rule": f"对比实体：{'、'.join(multi_entities)}", "search_priority": "语义均衡"}
    return {"search_queries": _normalize_search_queries_english([_deterministic_search_query(query)], query), "core_entity": [rule["label"]] if rule else [], "filter_rule": rule["filter"] if rule else "全部", "search_priority": "语义均衡"}

def search_single(query: str, section: str = None, top_k: int = 8) -> list:
    from search import search
    result = search(query, top_k=top_k, hybrid=True, section=section)
    return result.get("results", [])

def search_parallel(sub_queries, section=None, top_k=20):
    per_query = []
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(sub_queries), 3)) as executor:
        futures = {executor.submit(search_single, q, section, top_k): q for q in sub_queries}
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
    for i in range(top_k):
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
        get_reranker._model = CrossEncoder(r"E:/AgentProjects/ai-solution-architect-lab/projects/foundry-knowledge-base/processed/models/ms-marco-MiniLM-L-6-v2", device=device)
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

def select_context(results, top_k=6, original_query="", search_query="", preserve_order=False):
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
    if preserve_order:
        # Multi-entity comparisons are already interleaved by sub-query in
        # search_parallel. A single rerank query tends to collapse coverage
        # onto one entity, so keep the balanced retrieval order.
        candidates_pool = [r for _, r in scored[:max(top_k * 3, 12)]]
        _log.info("  Rerank skipped: preserving multi-entity coverage")
    else:
        scored.sort(key=lambda x: x[0], reverse=True)
        candidates_pool = [r for _, r in scored[:max(top_k * 3, 12)]]
        try:
            rq = search_query or original_query
            candidates_pool = rerank(rq, candidates_pool, top_k=max(top_k * 3, 12))
            _log.info("  Reranked: %d candidates" % len(candidates_pool))
        except Exception as re_err:
            _log.warning("  Reranker failed: %s" % re_err)
    selected = candidates_pool[:top_k]
    formatted = []
    for i, r in enumerate(selected):
        cid = r.get("chunk_id", "")
        # Determine source_id from chunk_id prefix
        src = 5 if cid.startswith("ci_page-") else 2
        formatted.append({
            "index": i + 1,
            "chunk_id": cid,
            "source_id": src,
            "page": r.get("page", 0),
            "type": r.get("type", ""),
            "text": r.get("text_full", r.get("text", "")),
            "score": round(r.get("score", 0), 4),
            "section": r.get("section", ""),
        })
    return formatted
