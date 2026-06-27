# 铸造行业 RAG 知识库

> 面向 AI Solution Architect 岗位的旗舰项目
> 从 PDF 到 RAG 检索的全链路实现

## 项目结构

```
foundry-knowledge-base/
├── raw/                          ← 源 PDF 存放处
│   └── asm-handbook-v2.pdf       (3470页, 63MB)
├── processed/                    ← 提取后的 JSONL 数据
├── scripts/
│   ├── pdf_extractor.py          Step 1: PDF → JSONL 粗提取
│   ├── ingest.py                 Step 2: 清洗 + Embedding → pgvector
│   ├── search.py                 Step 3: 混合检索 API (向量+全文+章节过滤)
│   └── backfill_metadata.py      PDF TOC → metadata 章节回填
├── db/
│   └── schema.sql                PostgreSQL + pgvector 完整建表
└── docs/
    ├── architecture-deep-dive.md ← 全链路架构深度文档（面试武器）
    └── interview-deep-dive.md    ← 面试高频追问及回答策略
```

## 快速启动

```bash
# 1. 提取 PDF
python scripts/pdf_extractor.py raw/asm-handbook-v2.pdf processed/

# 2. 清洗 + Embedding + 入库
python scripts/ingest.py processed/asm-handbook-v2_extracted_*.jsonl

# 3. 章节元数据回填
python scripts/backfill_metadata.py raw/asm-handbook-v2.pdf

# 4. 启动检索服务
python scripts/search.py
# → http://127.0.0.1:8002
# → http://127.0.0.1:8002/docs (Swagger)
```

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

## 面试准备

- 阅读 `docs/architecture-deep-dive.md` 理解每一层的架构决策
- 阅读 `docs/interview-deep-dive.md` 准备追问回答
