# 铸造行业 RAG 知识库 — 架构深度文档

> 适用于 AI Solution Architect 面试准备
> 技术栈：Python + pdfplumber + PyPDF2 + PostgreSQL + pgvector + sentence-transformers + FastAPI

---

## 一、系统架构总览

### 数据流

```
[PDF 文档] ──Step1──▶ [JSONL 粗提取] ──Step2──▶ [PostgreSQL + pgvector]
                              pdf_extractor.py      ingest.py
                                                       │
                                                       ▼
[用户提问] ──Step3──▶ [混合检索 API] ◀── [FastAPI 服务 :8002]
                         search.py
```

### 三层结构

| 层 | 组件 | 职责 |
|---|------|------|
| 数据接入层 | `pdf_extractor.py` + `backfill_metadata.py` | PDF → 结构化文本 + 章节元数据 |
| 存储索引层 | PostgreSQL + pgvector + tsvector | 原文、向量、全文索引 三合一 |
| 检索服务层 | `search.py` + FastAPI | 混合检索 + 章节过滤 + HTTP API |

### 为什么没有用 Elasticsearch

- ES 需要单独搭建集群（JVM, 至少 1GB 内存），对单机知识库是过度设计
- PostgreSQL tsvector 自带的 GIN 倒排索引在万级数据量下性能完全足够（50ms 以内）
- pgvector 和全文索引在同一张表内，向量检索和关键词检索可以 JOIN 合并排序（RRF）
- 维护成本：一套 PostgreSQL 同时做 OLTP 和向量/全文检索

---

## 二、Step 1：PDF 抽取（pdf_extractor.py）

### 目标

从 3470 页的 PDF（ASM Handbook Vol.2，63MB）中提取可检索的结构化文本。

### 技术选型

| 方案 | 结论 | 理由 |
|------|------|------|
| PyMuPDF (fitz) | ❌ 未采用 | 环境未安装，pip 受网络限制 |
| Camelot / Tabula | ❌ 未采用 | PDF 表格合并单元格严重，结构化提取失败率高 |
| **pdfplumber** | ✅ **采用** | 已安装，文本提取质量好，能同时抽 text 和 table |

### PDF 结构分析

在动手提取之前，先做了结构采样：

```python
# 抽样 17 页，分析特征
样本结果：
- 总页数：3470 页
- 每页文本量：700-2400 字符
- 表格密度：约 30-50% 页面含表格
- 表格最大列数：18 列（合金成分表，合并单元格严重）
- 普通正文提取质量：高
```

**关键决策：** 不对表格做结构化保留，而是降级为文本描述。因为 pdfplumber 的 `extract_tables()` 对复杂工程表格的解析不可靠，而 `extract_text()` 的同页输出已经包含了表格内容的行内重排，信息不丢失。

### 输出格式：JSONL

```jsonl
{"id":"page-00042","type":"page_text","page":42,"text":"铝合金6061的力学性能...","has_tables":true}
{"id":"table-00042-01","type":"table","page":42,"shape":"8r x 6c","text":"Grade | UNS | Si | Fe | Cu..."}
```

**为什么 JSONL 而不是 JSON 数组？**
- 流式处理：3470 页的输出 8.8MB，JSON 数组需要全部读入内存再写
- JSONL 每行独立，`ingest.py` 可以逐行读取，内存 O(1)

### 提取速度

~4 页/秒，3470 页耗时约 15 分钟。

---

## 三、Step 2：清洗 + Embedding + 入库（ingest.py）

### 2.1 清洗策略

| 清洗规则 | 目的 | 实现 |
|---------|------|------|
| 表格去重 | 避免 page_text 和 table 内容重复 | 检查 table text 的前 100 字符是否包含在 page_text 里 |
| 空白收缩 | 消除 PDF 提取的多空格 | `re.sub(r"\s+", " ", text)` |
| 表格降级描述 | table chunk 增加可读前缀 | `[Table (8r x 6c)]` + 原始文本 |
| 序号清理 | 处理表格中的飘点符号 | `re.sub(r"\.\s+\.\s+\.", "…", text)` |

**去重效果：**

| 类型 | 提取后 | 清洗后 |
|------|--------|--------|
| page_text | 3470 | 3455 |
| table | 2380 | 2394 |
| 总计 | 5850 | **5849** |

### 2.2 Embedding 选型

| 模型 | 维度 | 语言 | 适用范围 |
|------|------|------|---------|
| **BAAI/bge-small-zh-v1.5** (首选) | 512 | 中英双语 | 中文查英文铸造资料的主力 |
| all-MiniLM-L6-v2 (降级) | 384 | 纯英文 | 当网络无法下载中文模型时兜底 |

**面试问答切入点：**
- Q: 为什么选 bge-small-zh 而不是 text-embedding-3-small？
  - A: 本地零成本，不依赖 API 调用延迟；中英文跨语言能力对铸造行业场景关键
- Q: 512 维和 1536 维的取舍？
  - A: 检索精度随维度增加的边际收益递减，512 维在 pgvector 上索引速度更快

### 2.3 入库策略

```sql
-- 每批 32 条，分批 embedding + INSERT
-- 使用 ON CONFLICT (chunk_id) DO NOTHING 防止重复
```

**速度：** 5849 条 embedding + 入库约 5-6 分钟。

---

## 四、PostgreSQL Schema 设计

### 核心表：chunks

```sql
chunks (
  id              SERIAL PRIMARY KEY,
  source_id       INT → document_sources,
  chunk_id        TEXT UNIQUE,          -- "page-00042" | "table-00042-01"
  page            INT,                  -- 页码
  chunk_type      TEXT,                -- "page_text" | "table"
  content_text    TEXT,                -- 清洗后的原文
  table_shape     TEXT,                -- "8r x 6c"
  table_header    JSONB,               -- 表头数组
  embedding       vector(512),         -- pgvector 向量列
  metadata        JSONB DEFAULT '{}',  -- 章节路径、实体标签
  tsv             tsvector GENERATED ALWAYS AS (...) STORED,  -- 全文索引
  created_at      TIMESTAMPTZ DEFAULT NOW()
)
```

### 索引结构

| 索引 | 类型 | 用途 |
|------|------|------|
| `idx_chunks_tsv` | **GIN** | 全文检索倒排索引 |
| `idx_chunks_metadata_gin` | **GIN** (jsonb_path_ops) | metadata 过滤加速 |
| `idx_chunks_page` | B-tree | 按页排序 |
| `idx_chunks_type` | B-tree | 过滤表格/正文 |
| `chunks_chunk_id_key` | UNIQUE B-tree | 防止重复导入 |

### 为什么用 GENERATED COLUMN

```sql
tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED
```

- 插入 `content_text` 时 **自动** 分词，不需要应用层维护
- 是 PostgreSQL 内核级别的自动计算，不是触发器
- GIN 索引随 `tsv` 列的变更自动更新

### 为什么 metadata 用 JSONB 而不是单独列

- 章节路径是变长嵌套结构，JSONB 天然支持
- 以后扩展实体提取结果（`""materials": ["HT250"]`）不需要改表结构
- JSONB 的 GIN 索引支持 `@>`、`?` 等高级查询操作

---

## 五、Metadata：从 PDF 目录回填

### 原理

90% 的技术手册 PDF 都携带内置**书签/大纲结构（PDF Outline）**，这是 PDF 规范的一部分。每个条目携带标题和页码。

### 实现

```python
# Step 1: 用 PyPDF2 读取 PDF 内置目录
reader = PyPDF2.PdfReader(pdf_file)
toc = reader.outline  # → [{"title": "Aluminum", "page": 17}, ...]

# Step 2: 建立"页码范围 → 章节路径"映射
#   pg.1-16   → Volume 2
#   pg.17-38  → Specific Metals / Introduction to Aluminum
#   pg.222-483 → Specific Metals / Properties of Wrought Aluminum

# Step 3: 为每个 chunk 查找所属章节
def section_for_page(section_map, page):
    # 找到距离该页最近的上一级章节边界
    return {"section_path": "Specific Metals / Properties of Wrought Aluminum"}
```

### 结果

```
page-00404 → metadata.section_path = "Specific Metals / Properties of Wrought Aluminum and Aluminum Alloys"
page-00111 → metadata.section_path = "Specific Metals / Alloy and Temper Designation Systems for Aluminum"
```

### 面试切入点

- Q: 为什么不用 LLM 提取 metadata？
  - A: PDF 原生结构是 Ground Truth，比 LLM 猜测更准确且零 token 成本。LLM 可能幻觉章节名。这是"Source Structure First"的架构原则。

---

## 六、检索系统：混合检索

### 三种检索机制对比

| 机制 | 引擎 | 匹配方式 | 能搜到"HT250"吗 | 适合场景 |
|------|------|---------|----------------|---------|
| **向量检索** | pgvector `<=>` 余弦距离 | 语义相似度 | ✅ 语义相关即可 | 理解意图、模糊查询 |
| **全文检索** | tsvector + GIN 倒排索引 | 关键词精确匹配 | ✅ 精确命中 | 查标准号、型号、配方 |
| **Metadata 过滤** | JSONB GIN 索引 | 分类筛选 | ❌ 只过滤章节等分类 | "只看铝合金章" |

### RRF 融合算法

```sql
RRF Score = 1/(60 + vector_rank) + 1/(60 + fts_rank)
```

- `k = 60`：标准 Reciprocal Rank Fusion 参数
- 同时在向量和全文结果中出现的 chunk，RRF 分数更高
- 只有向量命中的 chunk 仍会出现在结果中（不会漏）

### 为什么 scores 在 0.015-0.017 区间

RRF 打分天然是小数值，因为 `1/(60 + 1) ≈ 0.016`。重要的是**排名顺序**而不是分数绝对值。

---


## 七、Agent 智能调度层（agent.py）

### 7.1 架构演进

```
V1（原始）：用户 → RRF 混合搜索 → Top-6 → LLM → 回答
                  ↓ RRF 评分全在 0.015-0.017，无法区分好坏
                  
V2（当前）：用户 → LLM 查询改写 → 并行检索（多线程）
               → 上下文去重精选 → 改进 Prompt → 带有引用的回答
```

### 7.2 RRF 修复（search.py）

**问题：** 原 RRF 公式 `1/(60 + rank)` 把所有分数压缩到 0.015-0.017 区间，无法区分好坏文档。

**修复方案：** 用向量相似度直接评分，全文检索命中时加固定加分：

```python
score = vector_cosine_similarity * 0.65 + 
        (1.0 IF fulltext_matched ELSE 0) * 0.35
```

**效果对比：**

| 指标 | 旧 RRF | 新打分 |
|------|--------|--------|
| 分数范围 | 0.015-0.017（无法区分） | 0.48-0.70（可区分） |
| 中文查询 Top-1 | pg.767 铜合金（错误） | pg.767 铜合金（仍待改进） |
| 英文查询 Top-1 | pg.418（正确但分不清） | pg.418 0.698（清晰） |

### 7.3 Agent 调度流程

```
agent_chat() 入口
  │
  ├ Step 1: 查询改写（LLM）
  │   ├ "铝合金6061的力学性能"
  │   → ["6061 aluminum alloy mechanical properties",
  │      "6061-T6 tensile strength yield strength"]
  │   │
  ├ Step 2: 多路并行检索（ThreadPoolExecutor）
  │   ├ 子查询1 → 混合搜索 → Top-8
  │   ├ 子查询2 → 混合搜索 → Top-8
  │   └ 结果合并 → 去重（按 chunk_id）→ 保留最高分
  │   │
  ├ Step 3: 上下文精选
  │   ├ 按分数排序 → 取 Top-6
  │   └ 格式化（含页码、章节路径、分数）
  │   │
  └ Step 4: LLM 生成（改进版 Prompt）
      ├ Few-shot 示例指导格式
      ├ 强制引用标注 [1][2]
      └ 结构化输出（摘要 → 详述 → 引用）

返回: {answer, citations, thinking, model, latency_ms}
```

### 7.4 改进 Prompt 设计

```python
IMPROVED_SYSTEM_PROMPT = """【核心原则】
- 只使用检索结果中的信息回答
- 引用用 [1]、[2] 标注
- 数值必须带单位

【回答结构】
1. 先直接回答，再补充数据
2. 对比类用表格形式
3. 不编造不存在的引用

【查询改写 Prompt】
User: 铝合金6061的力学性能
→ ["6061 aluminum alloy mechanical properties",
   "6061-T6 tensile strength yield strength"]
"""
```

## 七、关键架构决策清单

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 向量库 | Chroma / FAISS / pgvector | **pgvector** | 与 PostgreSQL 共存，事务一致性，SQL JOIN 检索 |
| Agent 编排 | LangGraph / 手撸 | **手撸** | 面试展示每一步可控，审计可追溯 |
| Embedding 模型 | API / 本地 | **本地 (bge-small-zh)** | 零成本，离线，中英双语 |
| Embedding 维度 | 384 / 512 / 768 / 1536 | **512** | 精度与速度的平衡 |
| 全文检索 | ES / PostgreSQL | **PostgreSQL tsvector** | 零部署，万级数据 50ms |
| 混合策略 | RRF / 线性加权 | **RRF** | 无需调参，稳定 |
| 清洗策略 | 结构化保留 / 降级文本 | **降级文本** | 复杂表格解析成功率低，降级不丢信息 |
| API 框架 | FastAPI / Flask | **FastAPI** | 自动生成 Swagger 文档，方便展示 |

---

## 八、当前数据规模

```
文档：ASM Handbook Vol.2（3470 页，63MB）
Chunks：5849 条
  - page_text：3455
  - table：2394
覆盖页：1-3470（100%）
平均 chunk 长度：1340 字符
检索延迟：40-80ms（混合模式）
数据库：PostgreSQL 17 + pgvector 0.8
Embedding 模型：BAAI/bge-small-zh-v1.5（512维）
TF-IDF/全文索引：tsvector (english config)
Metadata：章节路径回填完成
API 端点：http://127.0.0.1:8002
```

---

## 九、后续扩展方向

### 短期（可面试时主动聊到）

1. **中文分词** — 当铸造行业中文 PDF 加入时，安装 `pg_jieba` 扩展，支持中文关键词检索
2. **Reranker** — 在检索结果上再加一个 cross-encoder 做二次排序，提升精度
3. **评估体系** — 构建 Hit Rate / MRR / Precision@K 的自动化评估 pipeline

### 中期

4. **NER 实体提取** — 对每个 chunk 跑离线小模型，提取材料名、标准号、性能参数，存入 metadata.entities
5. **流式文档更新** — 不重新入库全量数据，增量导入增量索引

### 长期

6. **多轮对话** — 将搜索包装为对话式交互（"告诉我铝合金的铸造温度" + 追问"那铜合金呢？"）
7. **多数据源联邦** — 多个 PDF 知识库各自索引，统一检索入口


