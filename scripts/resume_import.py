#!/usr/bin/env python3
"""Resume import: process remaining JSONL files into pgvector."""

import os, json, time, psycopg2
from pathlib import Path

os.environ["TRANSFORMERS_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).parent.parent
MODEL = str(BASE / "processed" / "models" / "bge-base-zh-v1.5")
CHUNKS = BASE / "processed" / "chunks"
DB = dict(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Get existing source names
cur.execute("SELECT title FROM document_sources")
existing = set(r[0] for r in cur.fetchall())
print(f"Already imported: {len(existing)} sources\n", flush=True)

model = SentenceTransformer(MODEL)

files = sorted(Path(CHUNKS).glob("*_chunks.jsonl"))
total = 0
for idx, jl in enumerate(files):
    data = [json.loads(l) for l in open(jl, encoding="utf-8") if l.strip()]
    if not data:
        continue
    src = data[0].get("source", jl.stem[:30])
    if src in existing:
        print(f"  SKIP [{idx+1}/{len(files)}] {jl.stem[:30]:30s} (already imported)")
        continue

    cur.execute("INSERT INTO document_sources (title, file_name) VALUES (%s,%s) RETURNING id", (src, src[:60]))
    sid = cur.fetchone()[0]

    t1 = time.time()
    ok = 0
    for i in range(0, len(data), 32):
        batch = data[i:i+32]
        try:
            embs = model.encode([x["content"] for x in batch], show_progress_bar=False)
        except:
            continue
        for j, x in enumerate(batch):
            pg = x.get("pages", [0])[0]
            cid = f"{sid}_{x['chunk_id']}"
            meta = json.dumps({"section_path": x.get("section_path",""), "page_range": x.get("pages",[pg]), "material_tags": x.get("material_tags",[]), "source": src})
            try:
                cur.execute("INSERT INTO chunks(source_id,chunk_id,page,chunk_type,content_text,table_shape,table_header,embedding,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(chunk_id) DO NOTHING", (sid, cid, pg, x["type"], x["content"], x.get("table_shape"), json.dumps(x.get("table_header",[])), embs[j].tolist(), meta))
                if cur.rowcount: ok += 1
            except: pass
        conn.commit()
    print(f"  [{idx+1}/{len(files)}] {jl.stem[:28]:28s} {len(data):4d}ch -> {ok:4d}ok ({time.time()-t1:.0f}s)", flush=True)
    total += ok

cur.execute("SELECT count(*) FROM chunks")
print(f"\nDone! {cur.fetchone()[0]} total chunks", flush=True)
conn.close()
