import os, json, time, psycopg2
from pathlib import Path
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from sentence_transformers import SentenceTransformer

B = Path(r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base")
M = str(B / "processed" / "models" / "bge-base-zh-v1.5")
D = dict(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")

conn = psycopg2.connect(**D)
cur = conn.cursor()
model = SentenceTransformer(M)
cur.execute("""
    INSERT INTO knowledge_sources (name, source_type, visibility, description, metadata)
    VALUES ('ASM Handbook Vol.2', 'standard_manual', 'public', '当前系统默认标准手册知识源', '{"source": "asm_handbook_vol_2"}')
    ON CONFLICT DO NOTHING
""")
cur.execute("SELECT id FROM knowledge_sources WHERE name=%s AND source_type=%s ORDER BY id LIMIT 1", ("ASM Handbook Vol.2", "standard_manual"))
ASM_SOURCE_ID = cur.fetchone()[0]

for idx, jl in enumerate(sorted((B / "processed" / "chunks").glob("*_chunks.jsonl"))):
    data = [json.loads(l) for l in open(jl, encoding="utf-8") if l.strip()]
    if not data: continue
    src = data[0].get("source", jl.stem[:30])
    cur.execute("SELECT id FROM document_sources WHERE title=%s", (src,))
    r = cur.fetchone()
    if r:
        sid = r[0]
    else:
        cur.execute("""INSERT INTO document_sources
            (knowledge_source_id, source_type, title, file_name, visibility, confidentiality)
            VALUES (%s, 'standard_manual', %s, %s, 'public', 'public') RETURNING id""", (ASM_SOURCE_ID, src, src[:60]))
        sid = cur.fetchone()[0]
    t1 = time.time(); ok = 0
    for i in range(0, len(data), 32):
        batch = data[i:i+32]
        try:
            embs = model.encode([x["content"] for x in batch], show_progress_bar=False)
        except: continue
        for j, x in enumerate(batch):
            pg = x.get("pages", [0])[0]
            cid = "%s_%s" % (sid, x["chunk_id"])
            meta = json.dumps({"section_path": x.get("section_path",""), "page_range": x.get("pages",[pg]), "material_tags": x.get("material_tags",[]), "source": src})
            try:
                cur.execute("INSERT INTO chunks(source_id,document_id,source_type,chunk_id,page,chunk_type,content_text,table_shape,table_header,embedding,metadata) VALUES(%s,%s,'standard_manual',%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(chunk_id) DO NOTHING", (sid, sid, cid, pg, x["type"], x["content"], x.get("table_shape"), json.dumps(x.get("table_header",[])), embs[j].tolist(), meta))
                if cur.rowcount: ok += 1
            except: pass
        conn.commit()
    print("  [%d/25] %s %dch -> %dok (%ds)" % (idx+1, jl.stem[:28].ljust(28), len(data), ok, time.time()-t1), flush=True)

cur.execute("SELECT count(*) FROM chunks")
print("\nDone! %d chunks" % cur.fetchone()[0], flush=True)
conn.close()
