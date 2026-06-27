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




## 9. 检索评估（Retrieval Evaluation）

### 评估体系

```
generate_eval_dataset.py           eval_retrieval.py
      │                                   │
      ▼                                   ▼
LLM 从 chunks 采样 → 生成真实风格查询  ──▶  逐条调 search() → 比对预期结果 → 算分
      │                                   │
      ▼                                   ▼
eval_queries 表                        eval_runs 表 / eval_results 表
```

### 第一次完整评估（基线）

| 指标 | 值 | 含义 |
|------|-----|------|
| 测试集 | 87 条 LLM 生成查询 | 从 Vol.2 随机抽样，每条 chunk → 2-3 条查询变体 |
| Hit Rate@5 | 0.276 | 27.6% 的查询在前 5 条命中正确答案 |
| Hit Rate@10 | 0.322 | 32.2% 的查询在前 10 条命中 |
| MRR | 0.239 | 命中时平均排名 ~4 |
| Precision@5 | 0.055 | 前 5 条结果中仅 5.5% 相关 |
| 平均延迟 | 276ms | 每次检索耗时 |

**改进方向（按预期收益排序）：**

| # | 方向 | 预期提升 | 状态 |
|---|------|---------|------|
| 1 | 启用 Reranker（Cross-Encoder，代码已有） | MRR +0.1~0.2 | ❌ 未启用 |
| 2 | 调优 RRF 融合权重（当前向量:FTS = 1:1） | Hit Rate +5-10% | ❌ 未调优 |
| 3 | 合金牌号精确匹配 Boosting | Precision + | ✅ 已开启（+0.08） |
| 4 | Query Rewrite Prompt 优化 | Hit Rate + | ❌ 未优化 |
| 5 | Dynamic Top-K 阈值微调 | 小幅度 | ❌ 未调优 |



### 实验记录

#### Exp #1: 启用 Cross-Encoder Reranker

在 `search.py` 的 `search()` 函数中，在 SQL 查询返回结果后、返回前插入 reranker 调用：

```python
# Apply cross-encoder reranker
try:
    if len(results) >= 2:
        from agent import rerank
        results = rerank(query, results, top_k=len(results))
except Exception:
    pass
```

| 指标 | Baseline | +Reranker | 变化 |
|------|----------|-----------|------|
| Hit Rate@5 | 0.276 | 0.310 | **+12.3%** |
| Hit Rate@10 | 0.322 | 0.322 | 持平 |
| MRR | 0.239 | 0.297 | **+24.3%** |
| Precision@5 | 0.055 | 0.062 | **+12.7%** |
| Avg Latency | 262 ms | 1057 ms | 4x 慢 |

**结论：** Reranker 有效提升了检索精度，尤其是 MRR（正确答案排名更靠前）。代价是延迟增加了约 4 倍。后续可以优化：缓存 CrossEncoder 模型（避免每次重新加载）、对候选结果做 batch 预测、或只在候选数量 > threshold 时启用。

**查看实验对比：**
```bash
python -c "from eval_db import print_runs_table, list_recent_runs; print_runs_table(list_recent_runs(10))"
```



#### Exp #2: RRF 权重融合改造

**改动：** 重写 `search()` 中 hybrid SQL 的融合逻辑

| 改造项 | 之前 | 之后 |
|--------|------|------|
| FTS 分数 | 原始 ts_rank（未归一化） | 除以 MAX 归一化到 0-1 |
| JOIN 类型 | LEFT JOIN（丢弃纯 FTS 结果） | FULL OUTER JOIN（保留全部结果） |
| 融合公式 | `vec + (0.1 if FTS matches else 0)` | `alpha * vec + (1-alpha) * fts_norm` |
| 权重控制 | 硬编码 0.1 | `alpha` 参数，默认 0.5 |

**结果对比（alpha=0.5）：**

| 指标 | 旧融合 | RRF(alpha=0.5) | 提升 |
|------|--------|----------------|------|
| Hit Rate@5 | 0.310 | 0.448 | **+44.5%** |
| Hit Rate@10 | 0.322 | 0.460 | **+42.9%** |
| MRR | 0.297 | 0.428 | **+44.1%** |
| Precision@5 | 0.062 | 0.090 | **+45.2%** |
| Latency | 1057ms | 1060ms | 持平 |

核心改进是 FULL OUTER JOIN 让纯 FTS 命中的结果不再被丢弃，FTS 分数归一化让向量和全文可以在同一量级下融合。

#### Exp #3: alpha 权重调优

测试不同 alpha 值（向量:FTS 权重比）:

| alpha | 向量:FTS | Hit@5 | Hit@10 | MRR | P@5 | Latency |
|-------|----------|-------|--------|-----|-----|---------|
| 0.3 | 3:7 (FTS 重) | 0.448 | 0.460 | 0.427 | 0.090 | 1108ms |
| 0.5 | 5:5 (均等) | 0.448 | 0.460 | 0.428 | 0.090 | 1060ms |
| 0.7 | 7:3 (向量重) | 0.448 | 0.460 | 0.430 | 0.090 | 1051ms |

**结论：** 当前 reranker 开启的情况下，alpha 值对最终结果几乎无影响。因为 reranker（Cross-Encoder）在 SQL 查询之后独立重排序，其语义匹配分数决定了最终顺序，初始 SQL 的加权融合只是候选集筛选，而 FULL OUTER JOIN 已经保证了候选集完整。推荐保持 alpha=0.5 作为对称默认值。

### 评估命令

```bash
# 1. 生成测试查询
python scripts/generate_eval_dataset.py --n 100 --source-id 2 --dataset-name my_test

# 2. 跑评估
python scripts/eval_retrieval.py --queries eval_results/my_test.json --top-k 10

# 3. 查看历史
python -c "from eval_db import print_runs_table, list_recent_runs; print_runs_table(list_recent_runs(10))"
```


## 面试准备

- 阅读 `docs/architecture-deep-dive.md` 理解每一层的架构决策
- 阅读 `docs/interview-deep-dive.md` 准备追问回答
