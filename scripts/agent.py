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






QUERY_REWRITE_PROMPT = """
# 角色定位
你是深耕铸造、金属材料工程的检索策略专家，精通材料手册检索逻辑，专为工业私有材料知识库设计检索方案。
知识库内容：各类变形铝合金、铜合金、永磁材料、铸造工艺、力学/热学性能、高低温测试参数、牌号标准、加工规范；检索底层为FTS全文检索(BM25) + 稠密向量检索 + RRF排名融合混合架构。

# 核心任务
接收用户铸造/金属材料类提问，输出一套可直接交付检索引擎执行的标准化检索策略。

# 强制拆解&生成规则
## 1. 核心实体提取
完整拆分问题内全部检索关键要素，分为四类：
1) 材料实体：合金牌号、热处理状态、合金体系（如6061 Al-Mg1SiCu、7075-T6）
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

# 输出示例
{"core_entity": ["6061-T6","6061-T651","-196℃","断裂韧性","疲劳强度"], "filter_rule": "仅铝合金", "search_queries": ["6061-T651 cryogenic fracture toughness at -196℃","6061-T6 low temperature fatigue","Al-Mg-Si-Cu 6061 alloy yield strength"], "search_priority": "关键词优先"}
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
    score: float
    attempts: int
    max_retries: int
    start_time: float
    progress_callback: Optional[callable]

def _rewrite_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在进行查询语义拆解..."})
    rw = rewrite_query(state["current_query"], state.get("history"))
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "rewritten", "queries": rw["search_queries"]})
        state["progress_callback"]({"type": "log", "message": f"查询拆解完成：{rw['search_queries']}"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _rewrite_node elapsed=%dms" % _elapsed)
    return {"sub_queries": rw["search_queries"], "core_entity": rw["core_entity"], "filter_rule": rw["filter_rule"], "search_priority": rw["search_priority"]}

def _search_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在检索知识库..."})
    rs = search_parallel(state["sub_queries"], state.get("section"), top_k=20)
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "searched", "count": len(rs)})
        state["progress_callback"]({"type": "log", "message": f"检索完成，共{len(rs)}条候选"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _search_node elapsed=%dms" % _elapsed)
    return {"search_results": rs}

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
    ctx = select_context(rs, top_k=dk, original_query=" ".join(state["sub_queries"]),
                         search_query=state["sub_queries"][0] if state["sub_queries"] else state["current_query"])
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "context_ready", "count": len(ctx)})
        state["progress_callback"]({"type": "log", "message": f"精选{len(ctx)}条上下文"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _select_context_node elapsed=%dms" % _elapsed)
    return {"context": ctx}

def _generate_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在构建提示词并生成回答..."})
    ad = generate_answer(state["current_query"], state["context"], state.get("history"))
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _generate_node elapsed=%dms" % _elapsed)
    return {"answer": ad.get("answer", ""), "citations": ad.get("citations", state["context"][:5])}

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
    if state["attempts"] < state["max_retries"] and len(ans) > 30 and sc < 7:
        return "retry"
    if len(ans) < 50 or "没有找到" in ans or "未找到" in ans:
        return "fallback"
    return "output"

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
    return {"answer": state["answer"], "citations": state.get("citations", state.get("context", [])[:5]),
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
    wf.add_node("retry", _retry_node)
    wf.add_node("fallback", _fallback_node)
    wf.add_node("output", _output_node)
    wf.add_edge(START, "rewrite")
    wf.add_edge("rewrite", "search")
    wf.add_edge("search", "select_ctx")
    wf.add_edge("select_ctx", "generate")
    wf.add_edge("generate", "check")
    wf.add_conditional_edges("check", _decide_next, {"retry": "retry", "fallback": "fallback", "output": "output"})
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

def agent_chat(query: str, section: str = None, history: list = None, progress_callback: callable = None) -> dict:

    _log.info('=' * 50)
    _log.info(f'Query: {query}')
    app = _get_graph()
    initial = {
        "query": query, "section": section, "history": history,
        "current_query": query, "sub_queries": [], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡", "search_results": [],
        "context": [], "answer": "", "citations": [], "score": 0,
        "attempts": 1, "max_retries": 1, "start_time": time.time(),
        "progress_callback": progress_callback,
    }
    # Merge saved messages with request history
    saved = _load_msgs("default")
    if saved and not history:
        initial["history"] = list(saved)
    elif saved and history:
        initial["history"] = list(saved) + list(history)
    result = app.invoke(initial)
    # Save messages after execution
    if result.get("answer"):
        msgs = list(initial.get("history") or [])
        msgs.append({"role": "user", "content": query})
        msgs.append({"role": "assistant", "content": result.get("answer", "")})
        _save_msgs("default", msgs)
    
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
    }


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
                result = data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get("reasoning_content") or ""
                _log.info(f"  Resp ({elapsed}ms): {result[:250]}")
                return result
            _log.warning(f"  HTTP {resp.status_code} ({elapsed}ms)")
    except Exception as e:
        _log.warning(f"  Error: {e}")
    return ""


def rewrite_query(query: str, history: list = None) -> dict:
    if False and re.match(r'^[a-zA-Z0-9\s\-\.]+$', query) and len(query.split()) <= 10:
        return {"search_queries": [query], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡"}
    if history:
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
                + "\n\nResolve pronouns via history. Include identifiers from history.")
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
                        sq = parsed.get("search_queries", [query])
                        if not sq:
                            sq = [query]
                        return {"search_queries": sq[:4], "core_entity": parsed.get("core_entity", []), "filter_rule": parsed.get("filter_rule", "全部"), "search_priority": parsed.get("search_priority", "语义均衡")}
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} failed, retrying...")
                time.sleep(0.5)
        except:
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} exception, retrying...")
                time.sleep(0.5)
    return {"search_queries": [query], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡"}

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






QUERY_REWRITE_PROMPT = """
# 角色定位
你是深耕铸造、金属材料工程的检索策略专家，精通材料手册检索逻辑，专为工业私有材料知识库设计检索方案。
知识库内容：各类变形铝合金、铜合金、永磁材料、铸造工艺、力学/热学性能、高低温测试参数、牌号标准、加工规范；检索底层为FTS全文检索(BM25) + 稠密向量检索 + RRF排名融合混合架构。

# 核心任务
接收用户铸造/金属材料类提问，输出一套可直接交付检索引擎执行的标准化检索策略。

# 强制拆解&生成规则
## 1. 核心实体提取
完整拆分问题内全部检索关键要素，分为四类：
1) 材料实体：合金牌号、热处理状态、合金体系（如6061 Al-Mg1SiCu、7075-T6）
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

# 输出示例
{"core_entity": ["6061-T6","6061-T651","-196℃","断裂韧性","疲劳强度"], "filter_rule": "仅铝合金", "search_queries": ["6061-T651 cryogenic fracture toughness at -196℃","6061-T6 low temperature fatigue","Al-Mg-Si-Cu 6061 alloy yield strength"], "search_priority": "关键词优先"}
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
    score: float
    attempts: int
    max_retries: int
    start_time: float
    progress_callback: Optional[callable]

def _rewrite_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在进行查询语义拆解..."})
    rw = rewrite_query(state["current_query"], state.get("history"))
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "rewritten", "queries": rw["search_queries"]})
        state["progress_callback"]({"type": "log", "message": f"查询拆解完成：{rw['search_queries']}"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _rewrite_node elapsed=%dms" % _elapsed)
    return {"sub_queries": rw["search_queries"], "core_entity": rw["core_entity"], "filter_rule": rw["filter_rule"], "search_priority": rw["search_priority"]}

def _search_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在检索知识库..."})
    rs = search_parallel(state["sub_queries"], state.get("section"), top_k=20)
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "searched", "count": len(rs)})
        state["progress_callback"]({"type": "log", "message": f"检索完成，共{len(rs)}条候选"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _search_node elapsed=%dms" % _elapsed)
    return {"search_results": rs}

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
    ctx = select_context(rs, top_k=dk, original_query=" ".join(state["sub_queries"]),
                         search_query=state["sub_queries"][0] if state["sub_queries"] else state["current_query"])
    if state.get("progress_callback"):
        state["progress_callback"]({"step": "context_ready", "count": len(ctx)})
        state["progress_callback"]({"type": "log", "message": f"精选{len(ctx)}条上下文"})
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _select_context_node elapsed=%dms" % _elapsed)
    return {"context": ctx}

def _generate_node(state: AgentState) -> dict:
    _step_start = time.time()
    if state.get("progress_callback"):
        state["progress_callback"]({"type": "log", "message": "正在构建提示词并生成回答..."})
    ad = generate_answer(state["current_query"], state["context"], state.get("history"))
    _elapsed = int((time.time() - _step_start) * 1000)
    _log.info("  [timing] _generate_node elapsed=%dms" % _elapsed)
    return {"answer": ad.get("answer", ""), "citations": ad.get("citations", state["context"][:5])}

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
    if state["attempts"] < state["max_retries"] and len(ans) > 30 and sc < 7:
        return "retry"
    if len(ans) < 50 or "没有找到" in ans or "未找到" in ans:
        return "fallback"
    return "output"

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
    return {"answer": state["answer"], "citations": state.get("citations", state.get("context", [])[:5]),
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
    wf.add_node("retry", _retry_node)
    wf.add_node("fallback", _fallback_node)
    wf.add_node("output", _output_node)
    wf.add_edge(START, "rewrite")
    wf.add_edge("rewrite", "search")
    wf.add_edge("search", "select_ctx")
    wf.add_edge("select_ctx", "generate")
    wf.add_edge("generate", "check")
    wf.add_conditional_edges("check", _decide_next, {"retry": "retry", "fallback": "fallback", "output": "output"})
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

def agent_chat(query: str, section: str = None, history: list = None, progress_callback: callable = None) -> dict:

    _log.info('=' * 50)
    _log.info(f'Query: {query}')
    app = _get_graph()
    initial = {
        "query": query, "section": section, "history": history,
        "current_query": query, "sub_queries": [], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡", "search_results": [],
        "context": [], "answer": "", "citations": [], "score": 0,
        "attempts": 1, "max_retries": 1, "start_time": time.time(),
        "progress_callback": progress_callback,
    }
    # Merge saved messages with request history
    saved = _load_msgs("default")
    if saved and not history:
        initial["history"] = list(saved)
    elif saved and history:
        initial["history"] = list(saved) + list(history)
    result = app.invoke(initial)
    # Save messages after execution
    if result.get("answer"):
        msgs = list(initial.get("history") or [])
        msgs.append({"role": "user", "content": query})
        msgs.append({"role": "assistant", "content": result.get("answer", "")})
        _save_msgs("default", msgs)
    
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
    }


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
                result = data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get("reasoning_content") or ""
                _log.info(f"  Resp ({elapsed}ms): {result[:250]}")
                return result
            _log.warning(f"  HTTP {resp.status_code} ({elapsed}ms)")
    except Exception as e:
        _log.warning(f"  Error: {e}")
    return ""


def rewrite_query(query: str, history: list = None) -> dict:
    if False and re.match(r'^[a-zA-Z0-9\s\-\.]+$', query) and len(query.split()) <= 10:
        return {"search_queries": [query], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡"}
    if history:
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
                + "\n\nResolve pronouns via history. Include identifiers from history.")
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
                        sq = parsed.get("search_queries", [query])
                        if not sq:
                            sq = [query]
                        return {"search_queries": sq[:4], "core_entity": parsed.get("core_entity", []), "filter_rule": parsed.get("filter_rule", "全部"), "search_priority": parsed.get("search_priority", "语义均衡")}
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} failed, retrying...")
                time.sleep(0.5)
        except:
            if attempt < 2:
                _log.warning(f"  Rewrite attempt {attempt+1} exception, retrying...")
                time.sleep(0.5)
    return {"search_queries": [query], "core_entity": [], "filter_rule": "全部", "search_priority": "语义均衡"}

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
