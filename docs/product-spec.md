# 铸造行业材料知识库 AI 助手 - 产品需求文档

> 版本：v0.1 | 状态：初步规划 | 更新日期：2026-07-06

---

## 一、产品背景与愿景

### 背景
工业材料领域（铸造、金属加工等）的技术人员日常需要查阅大量手册（ASM Handbook、铝合金手册、铜合金手册等）来获取材料牌号、力学性能、热处理工艺、焊接规范等信息。传统查阅方式效率低下，且跨手册对比困难。

### 愿景
打造一个面向工业材料领域的智能知识库助手，让技术人员通过自然语言问答即可快速获取精准的材料数据、工艺流程、对比分析，并能自动生成结构化的思维导图/流程图辅助决策。

### 目标用户
| 用户类型 | 使用场景 | 核心需求 |
|---------|---------|---------|
| 材料工程师 | 选材、性能对比、故障分析 | 快速查数据、多牌号对比 |
| 工艺工程师 | 热处理、焊接、铸造工艺设计 | 查工艺参数、流程步骤 |
| 质检人员 | 材料标准、检测方法 | 查标准、规范 |
| 技术管理者 | 知识传承、培训 | 生成知识导图、培训材料 |

---

## 二、核心功能清单

### P0 - 必须完成（MVP）

| # | 功能 | 描述 | 技术要点 |
|---|------|------|---------|
| 1 | 知识库检索问答 | 用户输入问题，系统检索知识库并生成回答 | 混合检索 + Reranker + LLM |
| 2 | 多轮对话 | 支持连续追问，上下文记忆 | message_store 记忆管理 |
| 3 | 引用溯源 | 回答中标注引用来源，可查看原文 | citation 机制已实现 |
| 4 | 知识库管理 | 支持上传/更新文档，自动解析入库 | PDF 解析 + chunk + embedding |

### P1 - 重要功能

| # | 功能 | 描述 | 技术要点 |
|---|------|------|---------|
| 5 | 思维导图/流程图生成 | 对于流程型问题，自动生成可视化导图 | Mermaid.js 前端渲染 |
| 6 | 流式输出 | LLM 回答逐字显示 | SSE + EventSource |
| 7 | 多知识库切换 | 支持切换不同手册/领域 | 按 source_id 过滤 |
| 8 | 回答质量评分 | 对回答进行质量评估，低分自动重试 | quality_check 机制 |

### P2 - 增强功能

| # | 功能 | 描述 |
|---|------|------|
| 9 | 材料对比分析 | 输入多种材料，自动生成对比表格/导图 |
| 10 | 工艺步骤导图 | 输入工艺名称，生成步骤流程图 |
| 11 | 报告生成 | 将问答结果导出为 PDF/Word 报告 |
| 12 | 知识图谱 | 材料-性能-工艺关系可视化导航 |

---

## 三、用户使用流程

用户打开网页 -> 输入问题 -> 系统分析问题拆解为检索语句 -> 并行检索知识库 -> Reranker 重排精选上下文 -> LLM 生成回答 -> 如果是流程型问题则额外生成导图 -> 前端渲染回答 + 导图 -> 用户可连续追问

---

## 四、技术架构

### 当前架构（v0.1）- 单 Agent

```
前端 (HTML/CSS/JS) → FastAPI
    → RAG Agent (LangGraph StateGraph)
        → rewrite → search → select_ctx → generate
    → PostgreSQL (pgvector + tsvector)
    → Reranker (MiniLM)
    → LLM (deepseek-v4-flash)
```

### 目标架构（v0.2+）- 多 Agent

```
用户 → Web UI
    → Orchestrator Agent（主控）
        → RAG Agent（子图）
            rewrite → search → select_ctx → generate
        → Mind Map Agent（子图）
            RAG → 结构化输出 → Mermaid 渲染
        → Comparison Agent（子图）
            RAG + 对比逻辑 → 对比表格
        → Report Agent（子图）
            RAG → 报告组装 → PDF/Word

各 Agent 职责：
- Orchestrator: 意图识别、Agent 调度、结果组装
- RAG Agent: 知识库检索 + 生成回答（现有管线封装）
- Mind Map Agent: 调 RAG 获取上下文 → 生成导图 JSON → 前端渲染
- Comparison Agent: 调 RAG 获取多种材料数据 → 对比输出
- Report Agent: 调 RAG → 结构化报告生成 → 导出
```

### 数据流（RAG Agent 内部）

用户输入 -> rewrite_query (LLM 重写为英文检索语句) -> search_parallel (多路并行搜索) -> pgvector + tsvector -> RRF 融合 -> select_context (reranker 重排) -> generate_answer (LLM) -> 前端展示

### 核心指标

| 指标 | 当前 | 目标 |
|------|------|------|
| HitRate@5 | 0.69~0.74 | >= 0.80 |
| MRR | 0.64~0.67 | >= 0.75 |
| 平均延迟 | ~6s | <= 3s |
| 数据量 | ~30K chunks | 持续增长 |

---

## 五、迭代路线图

### Phase 1 - MVP 稳定（当前）
- 已完成：检索问答、多轮对话、引用溯源、混合检索、Reranker
- 待完成：UI 打磨、错误处理优化

### Phase 2 - RAG Agent 子图化（1周）
- 将当前管线封装为 LangGraph 子图（Sub-graph）
- Orchestrator 主控 Agent 搭建
- RAG Agent 独立接口定义（输入/输出规范）
- 确保现有功能不受影响

### Phase 3 - 体验提升（2周）
- 流式输出（SSE + EventSource）
- 回答排版美化（表格渲染、引用卡片）
- 查询重写 prompt 优化
- 搜索候选池扩大

### Phase 4 - 导图 Agent（3周）
- Mermaid.js 前端集成
- Mind Map Agent 开发（调 RAG → 结构化输出）
- 流程型问题自动识别
- 导图 UI 交互优化

### Phase 5 - 增强功能（1-2月）
- Comparison Agent（材料对比）
- 材料元数据过滤
- embedding 升级（bge-base → bge-m3）
- 多知识库切换

### Phase 6 - 长期
- Report Agent（报告导出）
- 知识图谱
- 云端部署
- 用户系统 + 权限管理


## 七、竞品分析

### 通用 RAG 平台

| 产品 | 类型 | 优势 | 劣势 |
|------|------|------|------|
| RAGFlow | 开源 RAG 引擎 | 文档解析强、可视化配置 | 通用领域、材料无针对性 |
| Dify | 开源 LLMOps | 工作流编排、多模型 | 检索能力弱、知识库简单 |
| FastGPT | 开源知识库 QA | 中文友好、界面美观 | 大文档处理弱 |
| MaxKB | 开源知识库 QA | 轻量简洁 | 无 reranker、检索弱 |
| QAnything | 开源 RAG | 检索精度高 | 部署复杂 |
| MatWeb | 材料数据库 | 在线查性能数据 | 纯数据查询、无 AI |
| Total Materia | 材料数据库 | 全球最大材料数据库 | 无 AI 对话 |
| GRANTA MI (ANSYS) | 材料信息管理 | 企业级管理 | 价格高、太重 |

### 我们的核心竞争力

1. 领域深度：27 本 ASM 手册，材料术语优化
2. 检索质量：混合检索 + Reranker + 多查询重写，HitRate@5=0.73
3. GPU 加速：3060 本地，reranker ~100ms
4. 导图能力：将知识转化为可视化导图/流程图
5. 完全可控：开源、可定制、数据不出厂


## 九、业界多 Agent RAG 架构调研

### 主流方案汇总

| 方案 | 厂商 | 核心模式 | 适用场景 | 与我们设计对比 |
|------|------|---------|---------|--------------|
| **LangGraph Sub-graph** | LangChain | 子图嵌套 + Supervisor 路由 | 复杂工作流编排 | ✅ 最接近，我们就是基于此设计 |
| **AutoGen** | 微软 | 对话式多 Agent，GroupChat 路由 | 多角色协作 | ❌ 重量级，不适合我们的场景 |
| **CrewAI** | 开源 | 角色驱动，顺序/层级流程 | 自动化任务编排 | ❌ 偏自动化任务，非知识库场景 |
| **Semantic Kernel** | 微软 | Planner 自动规划 + 函数调用 | 企业应用集成 | ⚠️ Planner 黑盒，可控性差 |
| **Dify Workflow** | 开源 | 可视化工作流编排 | 快速原型开发 | ⚠️ 可视化好但灵活性不足 |
| **OpenAI Assistants** | OpenAI | 单 Agent + 多工具 | 通用助手场景 | ❌ 非多 Agent，工具模式不同 |

### LangGraph Sub-graph 模式详解（我们的参考）

LangGraph 的 sub-graph 模式是目前最适合我们的：

```
# 主图 (Orchestrator)
orchestrator = StateGraph(MainState)
orchestrator.add_node("router", intent_router)     # 意图识别
orchestrator.add_node("rag_agent", rag_subgraph)   # RAG 子图
orchestrator.add_node("mindmap_agent", ...)        # 导图子图

# RAG 子图 (封装现有管线)
rag_subgraph = StateGraph(RAGState)
rag_subgraph.add_node("rewrite", rewrite_query)
rag_subgraph.add_node("search", search_parallel)
rag_subgraph.add_node("select_ctx", select_context)
rag_subgraph.add_node("generate", generate_answer)
rag_subgraph.add_edge("rewrite", "search")
rag_subgraph.add_edge("search", "select_ctx")
rag_subgraph.add_edge("select_ctx", "generate")
```

### 关键设计模式对比

| 设计模式 | 说明 | 适用性 |
|---------|------|--------|
| **Supervisor (主管)** | 一个主 Agent 路由给子 Agent | ✅ 我们的设计 |
| **GroupChat (群聊)** | 多个 Agent 对话讨论 | ❌ 太复杂，不适用 |
| **Tool-based (工具)** | 主 Agent 调用多个工具 | ⚠️ 可做备选 |
| **Pipeline (管线)** | 固定顺序执行 | ❌ 不够灵活 |

### 业界趋势

1. **LangGraph Sub-graph 成为事实标准** — LangChain 生态最成熟的模式
2. **从单 Agent 到多 Agent 是自然演进** — 不是推翻重来，而是封装现有管线
3. **Orchestrator 专注路由，子 Agent 专注能力** — 职责分离
4. **状态管理是关键** — 每个子 Agent 有独立状态，主图管理全局状态

### 对我们设计的验证

- ✅ LangGraph sub-graph = 业界最佳实践
- ✅ 我们的 RAG Agent 子图化 = 标准做法
- ✅ Orchestrator + 子 Agent = Supervisor 模式
- ✅ 渐进式改造 = 低风险
