import os, sys, json, time, psycopg2
from pathlib import Path
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).parent
DB = dict(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")
MODEL = str(BASE / "processed" / "models" / "bge-base-zh-v1.5")
CHUNKS = BASE / "processed" / "chunks"

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Drop and recreate
cur.execute("DROP TABLE IF EXISTS chunks, document_sources, retrieval_log, qa_log CASCADE")
cur.execute("""CREATE TABLE IF NOT EXISTS knowledge_sources (id SERIAL PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'standard_manual', owner_user_id INT, organization_id INT, visibility TEXT NOT NULL DEFAULT 'public', description TEXT DEFAULT '', metadata JSONB DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""")
cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_sources_name_type_unique ON knowledge_sources(name, source_type)")
cur.execute("""INSERT INTO knowledge_sources (name, source_type, visibility, description, metadata) VALUES ('ASM Handbook Vol.2', 'standard_manual', 'public', '当前系统默认标准手册知识源', '{"source": "asm_handbook_vol_2"}') ON CONFLICT DO NOTHING""")
cur.execute("SELECT id FROM knowledge_sources WHERE name=%s AND source_type=%s ORDER BY id LIMIT 1", ("ASM Handbook Vol.2", "standard_manual"))
ASM_SOURCE_ID = cur.fetchone()[0]
cur.execute("""CREATE TABLE document_sources (id SERIAL PRIMARY KEY, knowledge_source_id INT REFERENCES knowledge_sources(id), source_type TEXT NOT NULL DEFAULT 'standard_manual', title TEXT NOT NULL, file_name TEXT NOT NULL, file_path TEXT, total_pages INT, visibility TEXT NOT NULL DEFAULT 'public', organization_id INT, owner_user_id INT, domain_tags JSONB DEFAULT '[]', confidentiality TEXT DEFAULT 'public', metadata JSONB DEFAULT '{}', ingested_at TIMESTAMPTZ DEFAULT NOW())""")
cur.execute("""CREATE TABLE chunks (id SERIAL PRIMARY KEY, source_id INT REFERENCES document_sources(id), document_id INT, source_type TEXT NOT NULL DEFAULT 'standard_manual', visibility TEXT NOT NULL DEFAULT 'public', organization_id INT, owner_user_id INT, project_id INT, domain_tags JSONB DEFAULT '[]', confidentiality TEXT DEFAULT 'public', evidence_level TEXT DEFAULT 'standard', chunk_id TEXT UNIQUE NOT NULL, page INT NOT NULL, chunk_type TEXT NOT NULL, content_text TEXT NOT NULL, table_shape TEXT, table_header JSONB, embedding vector(768), metadata JSONB DEFAULT '{}', tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED, fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED, created_at TIMESTAMPTZ DEFAULT NOW())""")
cur.execute("CREATE INDEX idx_chunks_source_id ON chunks(source_id)")
cur.execute("CREATE INDEX idx_chunks_source_type ON chunks(source_type)")
cur.execute("CREATE INDEX idx_chunks_tsv ON chunks USING GIN (tsv)")
cur.execute("CREATE INDEX idx_chunks_fts ON chunks USING GIN (fts)")
cur.execute("CREATE INDEX idx_chunks_metadata_gin ON chunks USING GIN (metadata jsonb_path_ops)")
conn.commit()
print("Tables ready", flush=True)

# Load model
model = SentenceTransformer(MODEL)
print(f"Model loaded: dim={model.get_sentence_embedding_dimension()}", flush=True)

# Process files
files = sorted(Path(CHUNKS).glob("*_chunks.jsonl"))
total = 0
for idx, jl in enumerate(files):
    data = [json.loads(l) for l in open(jl, encoding="utf-8") if l.strip()]
    if not data: continue
    src = data[0].get("source", jl.stem[:40])
    cur.execute("SELECT id FROM document_sources WHERE title=%s", (src,))
    r = cur.fetchone()
    if r: sid = r[0]
    else:
        cur.execute("""INSERT INTO document_sources
            (knowledge_source_id, source_type, title, file_name, visibility, confidentiality)
            VALUES (%s, 'standard_manual', %s, %s, 'public', 'public') RETURNING id""", (ASM_SOURCE_ID, src, src[:60]))
        sid = cur.fetchone()[0]
    
    t1 = time.time()
    ok = 0
    for i in range(0, len(data), 32):
        batch = data[i:i+32]
        try:
            embs = model.encode([c["content"] for c in batch], show_progress_bar=False)
        except:
            continue
        for j, c in enumerate(batch):
            pg = c.get("pages", [0])[0]
            meta = json.dumps({"section_path":c.get("section_path",""), "page_range":c.get("pages",[pg]), "material_tags":c.get("material_tags",[]), "source":src})
            cur.execute("INSERT INTO chunks (source_id,document_id,source_type,chunk_id,page,chunk_type,content_text,table_shape,table_header,embedding,metadata) VALUES (%s,%s,'standard_manual',%s,%s,%s,%s,%s,%s,%s,%s)", (sid,sid,c["chunk_id"],pg,c["type"],c["content"],c.get("table_shape"),json.dumps(c.get("table_header",[])),embs[j].tolist(),meta))
            ok += 1
        conn.commit()
    
    print(f"  [{idx+1}/{len(files)}] {jl.stem[:30]:30s} {len(data):4d}ch -> {ok:4d}ok ({time.time()-t1:.0f}s)", flush=True)
    total += ok

cur.execute("SELECT count(*) FROM chunks")
dbc = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM document_sources")
dbs = cur.fetchone()[0]
conn.close()
print(f"\nDone! {dbc} chunks from {dbs} sources", flush=True)
