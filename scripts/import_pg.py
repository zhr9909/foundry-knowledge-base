#!/usr/bin/env python3
"""Import all JSONL chunks into pgvector. One pass, no frills."""

import os, sys, json, time
from pathlib import Path

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

BASE = Path(__file__).parent.parent
CHUNKS_DIR = BASE / "processed" / "chunks"
MODEL_PATH = str(BASE / "processed" / "models" / "bge-base-zh-v1.5")
DB_CONF = {"host":"127.0.0.1","port":15432,"dbname":"foundry_kb","user":"findmyjob","password":"findmyjob_dev_password"}

def ensure_standard_source(cur):
    cur.execute("""
        INSERT INTO knowledge_sources (name, source_type, visibility, description, metadata)
        VALUES ('ASM Handbook Vol.2', 'standard_manual', 'public', '当前系统默认标准手册知识源', '{"source": "asm_handbook_vol_2"}')
        ON CONFLICT DO NOTHING
    """)
    cur.execute("SELECT id FROM knowledge_sources WHERE name=%s AND source_type=%s ORDER BY id LIMIT 1", ("ASM Handbook Vol.2", "standard_manual"))
    return cur.fetchone()[0]

def register_source(cur, name):
    cur.execute("SELECT id FROM document_sources WHERE title=%s", (name,))
    r = cur.fetchone()
    if r: return r[0]
    knowledge_source_id = ensure_standard_source(cur)
    cur.execute("""INSERT INTO document_sources
        (knowledge_source_id, source_type, title, file_name, visibility, confidentiality)
        VALUES (%s, 'standard_manual', %s, %s, 'public', 'public')
        RETURNING id""",
        (knowledge_source_id, name, name.replace(" ","_")[:80]))
    return cur.fetchone()[0]

def main():
    import psycopg2
    from sentence_transformers import SentenceTransformer
    
    rebuild = "--rebuild" in sys.argv
    conn = psycopg2.connect(**DB_CONF)
    cur = conn.cursor()
    
    if rebuild:
        print("Rebuilding schema with vector(768)...", flush=True)
        cur.execute("DROP TABLE IF EXISTS chunks, document_sources, retrieval_log, qa_log CASCADE")
        exec(open(BASE / "db" / "schema.sql").read().replace("vector(512)", "vector(768)"))
        conn.commit()
        print("Schema ready\n", flush=True)
    
    print("Loading model...", end=" ", flush=True)
    t0 = time.time()
    model = SentenceTransformer(MODEL_PATH)
    print(f"done ({time.time()-t0:.1f}s)\n", flush=True)
    
    files = sorted(CHUNKS_DIR.glob("*_chunks.jsonl"))
    print(f"Processing {len(files)} files\n", flush=True)
    
    total = 0
    for idx, jl in enumerate(files):
        chunks = [json.loads(l) for l in open(jl, encoding="utf-8") if l.strip()]
        if not chunks: continue
        
        src_name = chunks[0].get("source", jl.stem[:40])
        sid = register_source(cur, src_name)
        
        t1 = time.time()
        ok = 0
        batch_size = 32
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            texts = [c["content"] for c in batch]
            
            try:
                embs = model.encode(texts, show_progress_bar=False)
            except Exception as e:
                print(f"  encode err: {e}", flush=True)
                continue
            
            for j, c in enumerate(batch):
                pg = c.get("pages", [0])[0]
                meta = json.dumps({
                    "section_path": c.get("section_path",""),
                    "page_range": c.get("pages",[pg]),
                    "material_tags": c.get("material_tags",[]),
                    "source": src_name,
                })
                try:
                    cur.execute("""
                        INSERT INTO chunks (source_id, chunk_id, page, chunk_type,
                            content_text, table_shape, table_header, embedding, metadata)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (sid, c["chunk_id"], pg, c["type"], c["content"],
                          c.get("table_shape"), json.dumps(c.get("table_header",[])),
                          embs[j].tolist(), meta))
                    ok += 1
                except Exception as e:
                    print(f"  insert err {c['chunk_id'][:30]}: {str(e)[:60]}", flush=True)
                    conn.rollback()
                    raise
        
        conn.commit()
        nm = jl.stem[:30].ljust(30)
        print(f"  [{idx+1}/{len(files)}] {nm} {len(chunks):4d}ch → {ok:4d}ok ({time.time()-t1:.0f}s)", flush=True)
        total += ok
    
    cur.execute("SELECT count(*) FROM chunks")
    dbc = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM document_sources")
    dbs = cur.fetchone()[0]
    conn.close()
    print(f"\nDone! {dbc} chunks from {dbs} sources ({time.time()-t0:.0f}s)", flush=True)

if __name__ == "__main__":
    main()
