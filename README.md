# 铸造行业 RAG 知识库

> 面向 AI Solution Architect 岗位的旗舰项目
> 从 PDF 到 RAG 检索的全链路实现

## 项目结构

```
foundry-knowledge-base/
├── app/                          ← 前端页面
│   ├── index.html                Chat UI
│   ├── style.css                 样式
│   ├── app.js                    前端逻辑
│   ├── pdf-viewer.html           PDF.js 查看器（自包含）
│   └── pdfjs/                    PDF.js v3 UMD 库
├── raw/                          ← 源 PDF 存放处
├── processed/                    ← 提取后的 JSONL 数据
├── scripts/
│   ├── pdf_extractor.py          Step 1: PDF → JSONL 粗提取
│   ├── ingest.py                 Step 2: 清洗 + Embedding → pgvector
│   ├── search.py                 混合检索核心 (向量+全文+RRF)
│   ├── agent.py                  Agent 智能调度系统
│   ├── app_server.py             FastAPI 服务入口（含前端静态文件）
│   └── backfill_metadata.py      PDF TOC → metadata 章节回填
├── db/
│   └── schema.sql                PostgreSQL + pgvector 完整建表
├── docs/
│   ├── architecture-deep-dive.md ← 全链路架构深度文档（面试武器）
│   └── interview-deep-dive.md    ← 面试高频追问及回答策略
└── start_server.bat              一键启动
```

## 快速启动

```bash
# 1. 提取 PDF
python scripts/pdf_extractor.py raw/asm-handbook-v2.pdf processed/

# 2. 清洗 + Embedding + 入库
python scripts/ingest.py processed/asm-handbook-v2_extracted_*.jsonl

# 3. 章节元数据回填
python scripts/backfill_metadata.py raw/asm-handbook-v2.pdf

# 4. 启动全功能服务（API + 前端）
python scripts/app_server.py
# → http://127.0.0.1:8002/    （Chat UI + PDF 查看器）
# → http://127.0.0.1:8002/docs （Swagger API 文档）
```

> 也可以双击 `start_server.bat` 一键启动。

## 数据库连接

```
主机:   127.0.0.1
端口:   15432 (容器) / 5432 (本地)
数据库: foundry_kb
用户:   findmyjob
密码:   findmyjob_dev_password
```

## 关键能力

| 能力 | 实现 |
|------|------|
| PDF 粗提取 | pdfplumber，~4页/秒 |
| 清洗去重 | 表格-正文去重 + 空白合并 |
| 中文 Embedding | BAAI/bge-small-zh-v1.5（512维） |
| 向量存储 + 检索 | pgvector（余弦距离） |
| 全文检索 | PostgreSQL tsvector + GIN 索引 |
| 混合检索 | RRF 融合（向量 + 全文） |
| 章节过滤 | PDF TOC → metadata → JSONB GIN 索引 |
| API 服务 | FastAPI + Swagger 文档 |
| 数据规模 | 3470 页 → 5849 chunks / 8.8MB / 50ms 延迟 |


## 新增功能（2026-06）

### 5. Agent 智能调度系统

```
用户提问 → Query Rewrite → Parallel Search → Context Selection → LLM 生成 → Quality Check → 重试/兜底 → 回答
```

| 模块 | 职责 |
|------|------|
| `rewrite_query()` | 中文问题 → 1-3 条英文专业检索语句（保留合金牌号、热处理状态） |
| `search_parallel()` | 多线程并发检索（3 worker），RRF 交互相交结果 |
| `select_context()` | 动态 top-K + 关键词 boosting（引用材料牌号加权 +0.08） |
| `generate_answer()` | 结构化 Prompt → LLM 生成 + 引用标记 |
| `quality_check()` | 三维评分（0-4 数据完整性 / 0-3 引用规范 / 0-3 结构）≥7 通过 |
| `agent_chat()` | 主循环：最大 2 轮重试，质量 < 7 则修改查询重试 |
| 兜底 | 知识库无结果 → 使用 LLM 自身知识 + 免责声明 |

**Prompt 体系：**
- `QUERY_REWRITE_PROMPT` — 中文→英文改写，材料专业约束
- `IMPROVED_SYSTEM_PROMPT` — 回答生成，4 种场景模板（单一参数/多材料对比/成分查询/无匹配）
- `FALLBACK_SYSTEM_PROMPT` — 知识库兜底时的 LLM 自身知识
- Quality Check Prompt — 三维评分标准

### 6. 前端 Chat UI

- 纯原生 HTML/CSS/JS（无框架依赖）
- 侧边栏章节筛选
- 深色/浅色主题切换
- SSE 流式进度步骤（5 步：分析→检索→精选→生成→质检）
- 实时处理日志面板（可折叠，精确到毫秒）
- SSE 优先，失败自动降级到 POST

### 7. PDF.js 文档查看器

- 基于 PDF.js v3（UMD 构建，兼容无模块浏览器）
- Worker 通过 fetch→blob 加载，绕过 MIME 类型限制
- **连续滚动**：上下翻页，延迟加载（一次 ~10 页窗口）
- **精确引用高亮**：取引用数据的精确文本 → 在 PDF 页面文字层搜索匹配 → 仅高亮匹配段落
- 浮动面板：可拖拽、可缩放、可关闭
- 工具栏：翻页 ▲/▼、缩放 +/−、适合宽度、跳转输入
- 键盘快捷键：方向键 / PageUp/Down
- 两种触发方式：顶栏 📄 按钮 / 点击引用卡片自动跳转

### 8. SSE 流式接口

```http
GET /chat/stream?query=铝合金6061的力学性能&section=Aluminum+Alloys
```

返回事件流：
```
data: {"step":"rewritten","queries":["6061 aluminum alloy mechanical properties"]}
data: {"step":"searched","count":12}
data: {"step":"context_ready","count":8}
data: {"type":"result","data":{"answer":"...","citations":[...]}}
```

前端 `EventSource` 消费，同时触发进度条 + 日志面板更新。


## 面试准备

- 阅读 `docs/architecture-deep-dive.md` 理解每一层的架构决策
- 阅读 `docs/interview-deep-dive.md` 准备追问回答
