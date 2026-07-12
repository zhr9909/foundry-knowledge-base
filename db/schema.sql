-- foundry-knowledge-base DB Schema
-- Target: PostgreSQL 17 + pgvector
-- How to run:
--   docker exec findmyjob-postgres psql -U findmyjob -c "CREATE DATABASE foundry_kb;"
--   docker exec findmyjob-postgres psql -U findmyjob -d foundry_kb -c "CREATE EXTENSION IF NOT EXISTS vector;"
--   psql -U findmyjob -d foundry_kb -f schema.sql

-- =====================================================
-- 文档源管理
-- =====================================================
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'standard_manual',
    owner_user_id INT,
    organization_id INT,
    visibility TEXT NOT NULL DEFAULT 'public',
    description TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_sources_name_type_unique
    ON knowledge_sources(name, source_type);

CREATE TABLE IF NOT EXISTS document_sources (
    id SERIAL PRIMARY KEY,
    knowledge_source_id INT REFERENCES knowledge_sources(id),
    source_type TEXT NOT NULL DEFAULT 'standard_manual',
    title TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT,
    total_pages INT,
    visibility TEXT NOT NULL DEFAULT 'public',
    organization_id INT,
    owner_user_id INT,
    domain_tags JSONB DEFAULT '[]',
    confidentiality TEXT DEFAULT 'public',
    metadata JSONB DEFAULT '{}',
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- Chunks：核心存储表（原文 + 向量 + 全文索引 + metadata）
-- =====================================================
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,

    -- 来源
    source_id INT REFERENCES document_sources(id),
    document_id INT,
    source_type TEXT NOT NULL DEFAULT 'standard_manual',
    visibility TEXT NOT NULL DEFAULT 'public',
    organization_id INT,
    owner_user_id INT,
    project_id INT,
    domain_tags JSONB DEFAULT '[]',
    confidentiality TEXT DEFAULT 'public',
    evidence_level TEXT DEFAULT 'standard',
    chunk_id TEXT UNIQUE NOT NULL,         -- "page-00042" 或 "table-00042-03"
    page INT NOT NULL,

    -- 内容
    chunk_type TEXT NOT NULL,              -- "page_text" | "table"
    content_text TEXT NOT NULL,            -- 清洗后的文本

    -- 表格专用
    table_shape TEXT,
    table_header JSONB,

    -- 向量（512维 = bge-small-zh-v1.5）
    embedding vector(512),

    -- 元数据（章节路径、实体标签等，JSONB 可扩展）
    metadata JSONB DEFAULT '{}',

    -- 全文检索（自动从 content_text 生成）
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED,
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 普通索引
CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_source_type ON chunks(source_type);
CREATE INDEX IF NOT EXISTS idx_chunks_visibility ON chunks(visibility);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(page);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);

-- 全文检索倒排索引
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING GIN (fts);

-- Metadata 过滤索引
CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin ON chunks USING GIN (metadata jsonb_path_ops);

-- 向量索引（大数据量时启用 HNSW）
-- CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

-- =====================================================
-- 检索日志（用于评估和调试）
-- =====================================================
CREATE TABLE IF NOT EXISTS retrieval_log (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    query_embedding vector(512),
    top_k INT DEFAULT 10,
    results JSONB,                         -- [{chunk_id, score, rank}, ...]
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 问答日志（预留，后续接 LLM 后使用）
-- =====================================================
CREATE TABLE IF NOT EXISTS qa_log (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    retrieved_chunks JSONB,
    answer TEXT,
    model TEXT,
    feedback_stars INT,
    feedback_comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 工程文档导入记录（MinIO/S3-ready，当前本地对象存储）
-- =====================================================
CREATE TABLE IF NOT EXISTS engineering_documents (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    project_id INT REFERENCES projects(id) ON DELETE CASCADE,
    artifact_id INT REFERENCES project_artifacts(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT '未命名工程文档',
    original_filename TEXT NOT NULL DEFAULT '',
    document_kind TEXT NOT NULL DEFAULT 'engineering_case',
    source_type TEXT NOT NULL DEFAULT 'current_project',
    storage_backend TEXT NOT NULL DEFAULT 'local',
    bucket TEXT NOT NULL DEFAULT '',
    object_key TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    mime_type TEXT DEFAULT '',
    file_size BIGINT DEFAULT 0,
    parse_status TEXT DEFAULT 'pending',
    extracted_text TEXT DEFAULT '',
    structured_data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engineering_documents_project ON engineering_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_engineering_documents_hash ON engineering_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_engineering_documents_status ON engineering_documents(parse_status);
