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

### 当前架构（v0.1）- 单体管线

```
前端 (HTML/CSS/JS)
    → FastAPI (app_server.py)
        → agent_chat()
            → rewrite → search → select_ctx → generate
    → PostgreSQL (pgvector + tsvector)
    → Reranker (MiniLM)
    → LLM (deepseek-v4-flash)
```

### 目标架构（v0.2+）- 独立服务多 Agent + Orchestrator

```
用户提问 → Gateway (:8000)
    → Orchestrator Agent（分析意图、编排任务）
        ├── Search Agent (:8001) → 搜索 + 重排，返回上下文
        ├── Generate Agent (:8002) → LLM 生成回答
        ├── Mind Map Agent (:8003) → 导图（未来）
        └── Orchestrator → 合并结果，流式返回

Orchestrator 职责：意图识别、任务编排、状态推送
Search Agent：检索 + reranker（不生成）
Generate Agent：接收上下文 → LLM 生成（不检索）
```

### A2A 任务编排

当前是单线程流水线（先搜完再生成）。改造后：
Search Agent 处理 → 实时推送 "正在搜索..."
Generate Agent 处理 → 逐字流式输出回答
Orchestrator 编排 → 任务级并行，前端实时显示进度
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

### Phase 2 - 服务化拆分（2周）
- 从单体拆分为独立服务
  - gateway.py（API 网关）
  - agent_rag.py（RAG Agent 独立服务）
- 定义 Agent 间通信协议（A2A-like REST API）
- 接口契约：每个 Agent 清晰的输入/输出规范
- 确保现有功能不受影响
- Docker Compose 一键部署

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
- ✅ 渐进式改造 = 低风险## 十、Agent 通信协议设计

### 协议概述

参考 Google A2A (Agent-to-Agent) 协议标准，核心思路是让 Agent 间通过标准化的方式发现彼此、交换任务和数据。关键要素：

1. **Agent Card** — 能力声明，每个 Agent 发布自己能干什么
2. **Task** — 工作单元，包含完整的生命周期
3. **Message** — 通信单元，由多个 Part 组成
4. **Part** — 内容单元，支持纯文本、结构化数据、流式 token

```
 ┌──────────────┐         A2A Protocol         ┌──────────────┐
 │  RAG Agent    │ ◄════════════════════════►  │  API Gateway  │
 │  (:8001)      │    Agent Card / Task /        │  (:8000)      │
 │               │    Message / Part             │               │
 └──────────────┘                                └──────────────┘
        │ A2A                                            │ A2A
        ▼                                                ▼
 ┌──────────────┐                                ┌──────────────┐
 │ Mind Map     │                                │ Comparison   │
 │ Agent (:8002)│                                │ Agent (:8003)│
 └──────────────┘                                └──────────────┘
```

### 一、Agent Card（能力声明）

每个 Agent 通过 GET /a2a/card 发布能力：

```
GET /a2a/card
{
    "agent": "rag",
    "name": "RAG Knowledge Base Agent",
    "version": "0.1.0",
    "description": "基于 ASM 手册的知识库检索与问答",
    "capabilities": [
        {
            "id": "chat",
            "name": "知识问答",
            "input": {"query": "string", "history": "array(optional)", "stream": "boolean"},
            "output": {"answer": "string", "citations": "array"}
        },
        {
            "id": "search",
            "name": "知识检索",
            "input": {"query": "string", "top_k": "int"},
            "output": {"results": "array"}
        }
    ],
    "rate_limit": {"rpm": 60}
}
```

### 二、Task（任务协议）

任务是 A2A 的核心单位，有完整生命周期。

#### 创建任务

```
POST /a2a/tasks
{
    "task_id": "task_001",
    "source": "gateway",
    "target": "rag",
    "type": "chat",
    "input": {"query": "铝合金6061的力学性能", "history": [], "stream": false},
    "ttl_seconds": 120
}

响应:
{
    "task_id": "task_001",
    "status": "completed",
    "output": {"answer": "6061-T6抗拉强度310MPa...", "citations": [...]},
    "metrics": {"total_ms": 5890}
}
```

#### 流式任务

```
POST /a2a/tasks  (input.stream = true)
响应: text/event-stream

event: task.status  data: {"status": "running"}
event: task.status  data: {"status": "rewriting"}
event: task.token   data: {"content": "6061"}
event: task.token   data: {"content": " aluminum"}
event: task.status  data: {"status": "completed"}
```

#### 查询状态 / 取消任务

```
GET  /a2a/tasks/{task_id}   → 当前状态
DELETE /a2a/tasks/{task_id}  → 取消任务
```

### 三、Agent 间调用场景

#### 场景1：问答（Gateway → RAG）

```
用户提问 → Gateway → POST /a2a/tasks → RAG Agent
                               → 返回 {answer, citations}
                               → Gateway 返回前端
```

#### 场景2：导图（Gateway → RAG → Mind Map）

```
用户请求导图 → Gateway → POST RAG Agent（取上下文）
                    → Gateway → POST Mind Map Agent（带上下文）
                    → 合并结果返回前端
```

#### 场景3：对比（Gateway → RAG → Comparison）

```
用户请求对比 → Gateway → POST RAG Agent（取多种材料数据）
                    → Gateway → POST Comparison Agent（带数据）
                    → 返回对比表格
```

### 四、内容类型

```
# 上下文块 (RAG → Mind Map)
ContextPart = {"type": "context", "chunks": [{"chunk_id": "...", "text": "..."}]}

# 导图块 (Mind Map → Gateway)
MermaidPart = {"type": "mermaid", "code": "graph TD...", "format": "mermaid"}

# 对比块 (Comparison → Gateway)
ComparePart = {"type": "comparison", "headers": [], "rows": []}

# 错误块
ErrorPart = {"type": "error", "code": "RAG_TIMEOUT", "message": "检索超时"}
```

### 五、Agent 发现机制

```
Gateway 启动时:
1. 读配置文件 agent_registry.yaml
2. 对所有 Agent 发 GET /a2a/card
3. 注册到内部路由表
4. 每30秒健康检查
5. Agent 离线则标记不可用

路由表:
  rag:     :8001  online   skills: [chat, search]
  mindmap: :8002  online   skills: [mindmap]
  compare: :8003  offline  skills: [comparison]
```

### 六、错误传播

```
RAG Agent 出错:
  → 返回 task.status = failed, error.code = "RAG_SEARCH_FAILED"
  → Gateway 收到后:
      - 超时则自动重试1次
      - 不可恢复则透传错误给前端
```

### 七、目录结构

```
scripts/a2a/
├── protocol.py           A2A 基础类 (AgentCard, Task, Message)
├── agent_card.py         Agent Card 生成与解析
├── task_manager.py       任务生命周期管理
└── content_types.py      内容类型定义
```## 九、业界多 Agent RAG 架构调研

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
