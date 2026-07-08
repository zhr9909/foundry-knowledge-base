# 项目手稿 — Foundry Knowledge Base RAG System

> 生成日期：2026-07-07 | 用于新对话快速上手

---

## 一、项目概况

铸造行业材料知识库 AI 助手。基于 ASM Handbook（27 本）构建，通过 RAG 技术实现材料牌号、力学性能、热处理工艺等专业知识的智能问答。

**技术栈：** Python 3.9 + FastAPI + PostgreSQL 17(pgvector) + bge-base-zh-v1.5 + MiniLM-L6 reranker + deepseek-v4-flash(cc-switch) + 纯 HTML/CSS/JS 前端

---

## 二、Git 仓库

```bash
cd E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base
```

**远程：** `https://github.com/zhr9909/foundry-knowledge-base`

**最新提交：** `ac5babf` — add .gitignore + clean cached files

---

## 三、当前架构

### 运行中（由旧 start_multiagent.cmd 启动）

| 端口 | 服务 | 文件 |
|------|------|------|
| 8000 | Gateway | `scripts/gateway.py` |
| 8001 | RAG Agent | `scripts/agent_rag.py`（已支持外部 context） |

### 已写好待启用

| 端口 | 服务 | 文件 |
|------|------|------|
| 8002 | Search Agent | `scripts/agent_search.py`（新建，只搜索）|

### 演进路线

```
当前: Gateway(:8000) → A2A → RAG Agent(:8001) → 一体化

目标: Gateway(:8000) → Orchestrator
        ├── Search Agent(:8002) → 搜索+重排
        └── Generate Agent(:8001) → LLM 生成
```

---

## 四、核心文件

### `scripts/`

| 文件 | 说明 |
|------|------|
| `agent.py` | RAG 核心逻辑（重写/搜索/重排/生成/LangGraph 工作流） |
| `search.py` | 混合检索引擎（pgvector + tsvector BM25 + RRF） |
| `agent_rag.py` | RAG Agent FastAPI 服务（:8001，已支持外部 context） |
| `agent_search.py` | **新建** Search Agent（:8002，只搜索，待启用） |
| `gateway.py` | API 网关（:8000，静态文件 + A2A 代理） |
| `a2a/protocol.py` | AgentCard, Task, TaskStatus, Part |
| `a2a/task_manager.py` | 线程安全的任务生命周期管理 |
| `a2a/content_types.py` | Part 类型工厂 |
| `app_server.py` | **废弃** — 旧单体服务 |

### `docs/`

| 文件 | 说明 |
|------|------|
| `product-spec.md` | 完整产品需求文档 |
| `handoff.md` | **本文件** — 对话手稿 |

---

## 五、A2A 协议

- **Agent Card**: `GET /a2a/card`
- **Task**: `POST /a2a/tasks` → 返回任务状态 + 输出
- **Streaming**: `POST /a2a/tasks` + `stream: true` → SSE 事件流
- **Part 类型**: text / token / context / mermaid / comparison / error

---

## 六、数据库

`host=127.0.0.1 port=15432 dbname=foundry_kb user=findmyjob`

| 表 | 说明 |
|----|------|
| `chunks` | ~33K 文档切片，含向量、文本、元数据 |
| `document_sources` | 27 本 ASM 手册来源 |

---

## 七、今天（7/7）完成的工作

| 条目 | 说明 |
|------|------|
| A2A 协议层 | `scripts/a2a/` — protocol.py, task_manager.py, content_types.py |
| RAG Agent | `scripts/agent_rag.py` — 独立 FastAPI + A2A 服务 |
| API Gateway | `scripts/gateway.py` — 静态文件 + A2A 转发 |
| Search Agent | `scripts/agent_search.py` **已新建待启用** |
| agent_rag.py 修改 | **已修改** — 支持外部传入 context（skip search）|
| 产品文档 | `docs/product-spec.md` — 含竞品分析、A2A 协议、架构设计 |
| Codex 修复 | 修复方法记录为 Skill |
| Git 推送 | 已推送到 GitHub |

---

## 八、待完成任务（新对话顺序）

### 第1步：验证当前状态
1. 检查 :8000、:8001 是否在运行
2. 验证 `agent_search.py` 和 `agent_rag.py` 语法
3. 停止旧服务，启动新服务

### 第2步：创建 Orchestrator
- 修改 `gateway.py` 使其调用 Search Agent(:8002) → Generate Agent(:8001)
- 前端看到 "正在搜索..." → "正在生成..." 的实时进度

### 第3步：流式输出
- 配合 Orchestrator 实现生成阶段逐字显示

### 第4步：后续
- Mind Map Agent（导图生成）
- 材料对比 Agent
- 重新跑 eval 验证

---

## 九、启动指南

```bash
# 1. 确保 Docker 数据库在运行
# 2. 启动 Search Agent
cd scripts && python agent_search.py     # :8002
# 3. 启动 Generate Agent
cd scripts && python agent_rag.py         # :8001
# 4. 启动 Gateway（Orchestrator）
cd scripts && python gateway.py          # :8000
```

---

## 十、注意事项

1. **exec_command 限制**：单会话调用过多会被限，新对话自动恢复
2. **GPU 显存**：RTX 3060 6GB，够用
3. **清 __pycache__**：修改 agent.py/search.py 后需手动清除
4. **Codex 修复**：`Rename-Item %APPDATA%\Codex\web\Codex Codex.bak-xxx`
5. **数据库**：Docker 容器名 `findmyjob-postgres`

---

## 十一、Orchestrator 更新（2026-07-07 第二次对话）

### 新架构

| 端口 | 服务 | 文件 | 状态 |
|------|------|------|------|
| 8000 | Orchestrator Gateway | scripts/gateway.py（**新版**） | 已开发，已验证 |
| 8001 | RAG Generate Agent | scripts/agent_rag.py | 待微服务模式启用 |
| 8002 | Search Agent | scripts/agent_search.py | 待微服务模式启用 |

**当前运行方式：** 单进程模式，Orchestrator(:8000) 直接导入 agent.py 做搜索+生成，不走 HTTP 调用。

**前端 API 接口完全不变**（/chat、/chat/stream、/search、/sections、/health、/pdf）。

### 启动方式（推荐）

1. 确保 Docker PostgreSQL 在运行
2. cd E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\scripts
3. python gateway.py
4. 等待约 20 秒（加载 embedding 模型）
5. 浏览器打开 http://127.0.0.1:8000
6. 使用完毕后 Ctrl+C 停止服务

也可双击 scripts/start_orchestrator.bat。

### 关键改动说明

- gateway.py 改为直接 import agent as _agent，调用 gent_chat() 和 stream_chat()
- SSE 流式事件（rewritten/searched/context_ready/checked/result/error）保持兼容
- 移除 HTTP 代理，改为直接函数调用

### 何时切回微服务模式

- 环境支持后台进程常驻后
- 将 gateway.py 中的 import agent as _agent 替换为 HTTP 客户端调用
- 启动 Search Agent(:8002) 和 Generate Agent(:8001)
- a2a/ 协议层已就绪，直接可用

---

## 十二、最终架构（2026-07-07 终版）

### 三服务微服务架构

| 窗口 | 端口 | 服务 | 文件 | 依赖 |
|------|------|------|------|------|
| 第一个 | 8002 | Search Agent | scripts/agent_search.py | 数据库 / embedding 模型 |
| 第二个 | 8001 | Generate Agent | scripts/agent_rag.py | 数据库 / LLM API |
| 第三个 | 8000 | Orchestrator | scripts/gateway.py | 8002 + 8001 就绪后启动 |

### 调用链路

`
用户 → Orchestrator(:8000)
  ├── Search Agent(:8002) → 查询重写 → 搜索 → 重排 → 返回上下文
  └── Generate Agent(:8001) → 用上下文生成答案 → 流式返回
`

### 如何启动

| 方式 | 操作 |
|------|------|
| **三步走（推荐）** | 双击 scripts/00_search.bat → scripts/01_generate.bat → scripts/02_orchestrator.bat |
| **一键启动** | 双击 scripts/start.bat |
| **Python launcher** | python scripts/start_all.py（需保持终端运行） |

### 这次完成的改动

| 文件 | 改动 |
|------|------|
| scripts/gateway.py | 从 A2A 代理改为真正的 Orchestrator，HTTP 调用 Search 和 Generate Agent |
| scripts/agent_rag.py | _task_stream 支持外部 context（流式路径不再重复搜索） |
| scripts/00_search.bat | 单个启动脚本 |
| scripts/01_generate.bat | 单个启动脚本 |
| scripts/02_orchestrator.bat | 单个启动脚本 |
| scripts/start.bat | 三合一启动脚本 |

### 已知问题

- 在 Codex sandbox 内无法长期后台运行，需由用户手动双击 bat 启动
- 各个窗口必须保持打开状态，关闭即停止对应服务
