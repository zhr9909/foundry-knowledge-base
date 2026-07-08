 # 铸造行业 RAG 知识库
 
 > 面向 AI Solution Architect 岗位的旗舰项目
 > 从 PDF 到多 Agent 编排 RAG 的全链路实现
 
 ## 架构
 
 ```
 用户 → Orchestrator(:8000)
   ├── Search Agent(:8002) → 查询重写 → 混合搜索 → Reranker → 返回上下文
   └── Generate Agent(:8001) → 接收上下文 → LLM 生成答案 → 流式返回
 ```
 
 | 服务 | 端口 | 职责 | 通信方式 |
 |------|------|------|---------|
 | Orchestrator | 8000 | 编排 RAG Agent，SSE 流式推送 | HTTP |
 | Search Agent | 8002 | 查询重写、混合检索（向量+BM25）、Reranker | A2A 协议 |
 | Generate Agent | 8001 | 接收上下文，LLM 生成带引用的回答 | A2A 协议 |
 
 详细架构说明见 [docs/product-spec.md](docs/product-spec.md) 和 [docs/architecture-deep-dive.md](docs/architecture-deep-dive.md)。
 
 ## 项目结构
 
 ```
 foundry-knowledge-base/
 ├── app/                          ← 前端页面
 │   ├── index.html                Chat UI + 进度条 + PDF 查看器
 │   ├── style.css                 样式
 │   ├── app.js                    前端逻辑（SSE 流式 + POST 降级）
 │   ├── pdf-viewer.html           PDF.js 查看器
 │   └── pdfjs/                    PDF.js v3 库
 ├── raw/                          ← 源 PDF 文件
 ├── processed/                    ← 提取后的数据
 ├── scripts/                      ← 全部核心代码
 │   ├── gateway.py                Orchestrator（:8000，编排 RAG Agent）
  │   ├── agent_rag.py              RAG Agent（:8001，搜索+生成一体）
 │   ├── a2a/                      A2A 协议层（Task/TaskManager/AgentCard）
 │   ├── agent.py                  RAG 核心逻辑（LangGraph 工作流）
 │   ├── search.py                 混合检索引擎（pgvector + tsvector + RRF）
 │   ├── pdf_extractor.py          Step 1: PDF → JSONL 粗提取
 │   ├── ingest.py                 Step 2: 清洗 + Embedding → pgvector
 │   ├── backfill_metadata.py      PDF TOC → metadata 章节回填
 │   ├── generate_eval_dataset.py  评估测试集生成
 │   ├── eval_retrieval.py         检索评估 (HitRate/MRR)
 │   ├── start.bat                 一键启动三个服务
 │   ├── 00_search.bat             启动 Search Agent
 │   ├── 01_generate.bat           启动 Generate Agent
 │   └── 02_orchestrator.bat       启动 Orchestrator
 ├── docs/
 │   ├── product-spec.md           ← 完整产品需求文档
 │   ├── architecture-deep-dive.md ← 架构深度分析
 │   ├── handoff.md                ← 交接手稿
 │   └── interview-deep-dive.md    ← 面试准备
 └── db/
     └── schema.sql                PostgreSQL + pgvector 完整建表
 ```
 
 ## 快速启动
 
 需要两个终端窗口，按顺序启动：
 
 ```bash
 # 窗口 1 - RAG Agent (:8001)
 cd E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\scripts
 python agent_search.py
 # 期待输出: Uvicorn running on http://0.0.0.0:8002
 
 # 窗口 2 - Generate Agent (:8001)
 cd E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\scripts
 python agent_rag.py
 # 期待输出: Uvicorn running on http://0.0.0.0:8001
 
 # 窗口 2 - Orchestrator (:8000) —— 等 RAG Agent 就绪再启动
 cd E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\scripts
 python gateway.py
 # 加载模型约 20 秒后: Uvicorn running on http://0.0.0.0:8000
 ```
 
 启动后在浏览器打开 **http://127.0.0.1:8000** 即可使用。
 
 也可以双击 `scripts/start.bat` 一键启动三个服务窗口。
 
 ## 数据库连接
 
 ```
 主机:   127.0.0.1
 端口:   15432 (Docker)
 数据库: foundry_kb
 用户:   findmyjob
 密码:   findmyjob_dev_password
 ```
 
 Docker 运行：
 ```bash
 docker run --name findmyjob-postgres -e POSTGRES_PASSWORD=findmyjob_dev_password -e POSTGRES_DB=foundry_kb -p 15432:5432 -d pgvector/pgvector:pg17
 ```
 
 ## 关键能力
 
 | 能力 | 实现 |
 |------|------|
 | PDF 解析 | PyMuPDF + Marker OCR（表格/图片兜底） |
 | 清洗去重 | 表格-正文去重 + 空白合并 |
 | Embedding | BAAI/bge-base-zh-v1.5（768维，GPU CUDA） |
 | 向量存储 + 检索 | pgvector（余弦距离） |
 | 全文检索 | PostgreSQL tsvector + GIN 索引 |
 | 混合检索 | RRF 融合（向量 + BM25 tsvector） |
 | 精排 Reranker | Cross-Encoder MiniLM-L6（GPU） |
 | Agent 编排 | 三服务微服务编排（Orchestrator + Search + Generate） |
 | 流式输出 | SSE + EventSource（Orchestrator 代理 Generate Agent） |
 | LLM | deepseek-v4-flash（cc-switch 路由） |
 | 数据规模 | 27 本 ASM 手册，37,317 页 |
 | 检索时延 | 混合 ~1.5s + Reranker ~0.36s + LLM ~14s |
 | 评估 | HitRate@5 / MRR / Precision@5 |
 
 ## Agent 核心流程
 
 ```
 Orchestrator 收到提问
   → POST Search Agent /a2a/tasks
     → rewrite_query() 中文→英文查询重写
     → search_parallel() 多路并行搜索（向量+BM25）
     → select_context() Reranker 重排
     → 返回上下文 + 子查询
   → POST Generate Agent /a2a/tasks
     → generate_answer() LLM 生成带引用标记的答案
     → quality_check() 质量评分，低分重试
     → 返回最终答案
   → SSE 流式推送至前端
 ```
 
 > 旧版单体服务 `app_server.py` 已废弃，改用多 Agent 架构。
 > 数据导入流程：`pdf_extractor.py` → `ingest.py` → `backfill_metadata.py`
