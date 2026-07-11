#!/usr/bin/env python3
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

"""search.py - RAG Retrieval API with hybrid search + section filtering"""

import json, os, sys, time, math, re
from typing import Optional
from pathlib import Path

try:
    import psycopg2, psycopg2.extras, logging
    _sqllog = logging.getLogger("agent")
    elapsed = 0
except ImportError:
    print("Missing psycopg2. Run: pip install psycopg2-binary")
    sys.exit(1)

CONFIG = {
    "host": "127.0.0.1", "port": 15432,
    "dbname": "foundry_kb", "user": "findmyjob",
    "password": "findmyjob_dev_password",
}

def get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        import torch.nn as nn
    except ImportError:
        print("Missing sentence-transformers. Run: pip install sentence-transformers")
        sys.exit(1)
    if not hasattr(get_embedding_model, "_model"):
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        print("Loading embedding model...")
        # Monkey-patch torch meta tensor issue
        _orig_to = nn.Module.to
        def _safe_to(self, *args, **kwargs):
            try:
                return _orig_to(self, *args, **kwargs)
            except NotImplementedError as e:
                if "meta tensor" in str(e):
                    device = args[0] if args else kwargs.get("device", "cpu")
                    return self.to_empty(device=device)
                raise
        nn.Module.to = _safe_to
        try:
            get_embedding_model._model = SentenceTransformer(r"E:/AgentProjects/ai-solution-architect-lab/projects/foundry-knowledge-base/processed/models/bge-base-zh-v1.5", device="cuda")
        except Exception as e:
            print(f"  Primary model failed: {e}")
            print("  Trying all-MiniLM-L6-v2...")
            try:
                get_embedding_model._model = SentenceTransformer(r"E:/AgentProjects/ai-solution-architect-lab/projects/foundry-knowledge-base/processed/models/bge-base-zh-v1.5", device="cuda")
            except Exception as e2:
                print(f"  All models failed: {e2}")
                sys.exit(1)
    return get_embedding_model._model

# BM25 index built on startup

def _rrf_fuse(vec_list, bm25_list, top_k=10):
    k = 60
    ranks = {}
    for rank, r in enumerate(vec_list, 1):
        ranks.setdefault(r["chunk_id"], {})["vr"] = rank
    for rank, r in enumerate(bm25_list, 1):
        ranks.setdefault(r["chunk_id"], {})["br"] = rank
    scored = []
    for cid, rd in ranks.items():
        vr = rd.get("vr", 999)
        br = rd.get("br", 999)
        rrf = 0.3 * (1.0 / (k + vr)) + 0.7 * (1.0 / (k + br))
        found = False
        for r in vec_list:
            if r["chunk_id"] == cid:
                d = dict(r)
                d["score"] = round(rrf, 4)
                d["vr"] = vr
                d["br"] = br
                scored.append(d)
                found = True
                break
        if not found:
            for r in bm25_list:
                if r["chunk_id"] == cid:
                    d = dict(r)
                    d["score"] = round(rrf, 4)
                    d["vr"] = vr
                    d["br"] = br
                    scored.append(d)
                    found = True
                    break
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    top = scored[:top_k]
    # Detailed RRF Scoring Breakdown
    _sqllog.info(f"=== RRF Scoring Breakdown (k={k}, top={top_k}) ===")
    for i, r in enumerate(top):
        cid = r.get("chunk_id", "?")
        vr = r.get("vr", 999)
        br = r.get("br", 999)
        term_v = 1.0 / (k + vr)
        term_b = 1.0 / (k + br)
        calc_rrf = round((term_v + term_b) / 2.0, 4)
        _sqllog.info(
            f"  [{i+1}] chunk={cid[-20:]} "
            f"VR={vr} -> {k}+{vr} -> 1/({k+vr})={term_v:.6f} | "
            f"BR={br} -> {k}+{br} -> 1/({k+br})={term_b:.6f} | "
            f"RRF=({term_v:.6f}+{term_b:.6f})/2={calc_rrf:.4f}"
        )
    _sqllog.info("=== End RRF Breakdown ===")
    return top


def _is_index_noise(text: str, section: str = "") -> bool:
    sample = (text or "").strip()[:160].lower()
    sec = (section or "").lower()
    return (
        sample.startswith("index |")
        or sample.startswith("subject index")
        or "index terms | links" in sample
        or sec in {"index", "subject index"}
    )


def _tsvector_search(query, top_k=40, cur=None):
    """PostgreSQL tsvector full-text search using existing DB cursor."""
    sql = f"""
        SELECT c.id, c.chunk_id, c.page, c.chunk_type,
            c.content_text, c.table_shape,
            ds.title as source_title, c.metadata,
            ts_rank(c.fts, plainto_tsquery('english', %(q)s)) AS score
        FROM chunks c
        JOIN document_sources ds ON ds.id = c.source_id
        WHERE c.fts @@ plainto_tsquery('english', %(q)s)
        ORDER BY score DESC
        LIMIT %(limit)s
        """
    cur.execute(sql, {"q": query, "limit": top_k})
    rows = cur.fetchall()
    result = []
    for row in rows:
        sp = (row["metadata"] or {}).get("section_path", "")
        if _is_index_noise(row["content_text"], sp):
            continue
        result.append({
            "id": row["id"],
            "chunk_id": row["chunk_id"],
            "page": row["page"],
            "type": row["chunk_type"],
            "text": (row["content_text"] or "")[:500],
            "text_full": row["content_text"] or "",
            "table_shape": row["table_shape"],
            "source": row["source_title"],
            "section": sp,
            "bm25_score": round(float(row["score"]), 4),
        })
    return result

MATERIAL_FAMILIES = json.loads(
    open(Path(__file__).parent / ".." / "processed" / "materials_taxonomy.json", encoding="utf-8").read())
MATERIAL_FAMILIES = {n: i["patterns"] for n, i in MATERIAL_FAMILIES.items()}

def detect_material_category(query):
    q = query.lower()
    for cat, patterns in MATERIAL_FAMILIES.items():
        for pat in patterns:
            if re.search(pat, q):
                return cat
    return None

def search(query: str, top_k: int = 10, hybrid: bool = True, section: str = None, alpha: float = 0.5) -> dict:
    """Search the knowledge base with optional section filter."""
    model = get_embedding_model()
    query_vec = model.encode(query).tolist()
    
    conn = psycopg2.connect(**CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Base section filter condition
    section_where = ""
    section_params = {}
    if section:
        section_where = "AND c.metadata->>'section_path' ILIKE '%%' || %(section_filter)s || '%%'"
        section_params["section_filter"] = section
    
    if hybrid:
        # BM25 + Vector RRF hybrid (no PostgreSQL ts_rank)
        vec_sql = f"""
        SELECT c.id, c.chunk_id, c.page, c.chunk_type,
            c.content_text, c.table_shape,
            ds.title as source_title, c.metadata,
            1 - (c.embedding <=> %(query_vec)s::vector) AS score
        FROM chunks c
        JOIN document_sources ds ON ds.id = c.source_id
        WHERE 1=1 {section_where}
        ORDER BY c.embedding <=> %(query_vec)s::vector
        LIMIT %(top_k)s
        """
        vec_params = {"query_vec": query_vec, "top_k": top_k * 3}
        if section:
            vec_params["section_filter"] = section
        cur.execute(vec_sql, vec_params)
        vec_rows = cur.fetchall()
        vec_results = []
        for row in vec_rows:
            sp = (row["metadata"] or {}).get("section_path", "")
            if _is_index_noise(row["content_text"], sp):
                continue
            vec_results.append({
                "id": row["id"], "chunk_id": row["chunk_id"], "page": row["page"],
                "type": row["chunk_type"],
                "text": (row["content_text"] or "")[:500],
                "text_full": row["content_text"] or "",
                "table_shape": row["table_shape"],
                "source": row["source_title"],
                "section": sp,
                "score": round(float(row["score"]), 4),
            })
        bm25_res = _tsvector_search(query, top_k * 3, cur)
        bm25_raw_json = json.dumps([{"chunk_id": r["chunk_id"], "bm25_score": r["bm25_score"]} for r in bm25_res[:20]], default=str)
        results = _rrf_fuse(vec_results, bm25_res, top_k)
    else:
        # Pure vector + section filter
        sql = f"""
        SELECT c.id, c.chunk_id, c.page, c.chunk_type,
            c.content_text, c.table_shape,
            ds.title as source_title, c.metadata,
            1 - (c.embedding <=> %(query_vec)s::vector) AS score
        FROM chunks c
        JOIN document_sources ds ON ds.id = c.source_id
        WHERE 1=1 {section_where}
        ORDER BY c.embedding <=> %(query_vec)s::vector
        LIMIT %(top_k)s
        """
        params = {"query_vec": query_vec, "top_k": top_k}
        if section:
            params["section_filter"] = section
    
        cur.execute(sql, params)
        rows = cur.fetchall()
        results = []
        for row in rows:
            sp = (row["metadata"] or {}).get("section_path", "")
            if _is_index_noise(row["content_text"], sp):
                continue
            results.append({
                "id": row["id"],
                "chunk_id": row["chunk_id"],
                "page": row["page"],
                "type": row["chunk_type"],
                "text": (row["content_text"] or "")[:500],
                "text_full": row["content_text"] or "",
                "table_shape": row["table_shape"],
                "source": row["source_title"],
                "section": sp,
                "score": round(float(row["score"]), 4),
            })
        bm25_raw_json = "[]"
    # Material category boost
    if hybrid and results:
        mat_cat = detect_material_category(query)
        if mat_cat:
            pos_kws = MATERIAL_FAMILIES[mat_cat]
            for r in results:
                txt = (r.get("text_full", r.get("text", "")) or "").lower()
                if any(kw.lower() in txt for kw in pos_kws):
                    r["score"] = min(1.0, (r.get("score", 0) or 0) + 0.15)
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    log_query = query + (f" [section:{section}]" if section else "") + (" [hybrid]" if hybrid else "")
    cur.execute(
        "INSERT INTO retrieval_log (query, top_k, results, latency_ms) VALUES (%s, %s, %s, %s)",
        (log_query, top_k, json.dumps(results[:5], default=str), int(elapsed)),
    )
    conn.commit()
    conn.close()
    
    return {
        "query": query,
        "top_k": top_k,
        "hybrid": hybrid,
        "section": section,
        "results": results,
        "latency_ms": int(elapsed),
    }


def list_sections() -> list:
    """List all available sections in the knowledge base."""
    conn = psycopg2.connect(**CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT metadata->>'section_path' as section
        FROM chunks
        WHERE metadata->>'section_path' IS NOT NULL
        ORDER BY section
    """)
    rows = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()
    return rows


def warmup():
    """Pre-load embedding model at startup (BM25 uses PostgreSQL tsvector, no preload needed)."""
    get_embedding_model()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--query":
        q = sys.argv[2] if len(sys.argv) > 2 else "茅聯聺氓聬聢茅聡聭"
        section = None
        if "--section" in sys.argv:
            idx = sys.argv.index("--section")
            section = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        result = search(q, 5, section=section)
        print(f"\nQuery: {result['query']}" + (f" [section: {section}]" if section else ""))
        print(f"Latency: {result['latency_ms']}ms\n")
        for r in result["results"]:
            sec = f" [{r['section']}]" if r.get('section') else ""
            print(f"[{r['score']:.4f}] pg.{r['page']} ({r['type']}){sec}")
            print(f"  {r['text'][:200]}\n")
    else:
        try:
            from fastapi import FastAPI, HTTPException, StaticFiles
            from pydantic import BaseModel
            from typing import Optional, List
            import uvicorn
            
            app = FastAPI(title="茅聯赂茅聙聽莽聼楼猫炉聠氓潞聯忙拢聙莽麓垄 API", version="0.2.0")
            
            class SearchRequest(BaseModel):
                query: str
                top_k: int = 10
                hybrid: bool = True
                section: Optional[str] = None
            
            class SearchResult(BaseModel):
                id: int; chunk_id: str; page: int; type: str
                text: str; text_full: str; score: float
                source: str = ""; table_shape: str = ""; section: str = ""
            
            class SearchResponse(BaseModel):
                query: str; top_k: int; hybrid: bool
                section: Optional[str] = None
                results: list; latency_ms: int
            
            @app.get("/health")
            def health():
                return {"status": "ok", "db": "pgvector", "chunks": 5849}
            
            @app.get("/sections")
            def sections():
                return {"sections": list_sections()}
            
            @app.post("/search", response_model=SearchResponse)
            def search_endpoint(req: SearchRequest):
                if not req.query.strip():
                    raise HTTPException(400, "query is required")
                return search(req.query, req.top_k, req.hybrid, req.section)
            
            @app.get("/search")
            def search_get(query: str = "", top_k: int = 10, hybrid: bool = True, section: Optional[str] = None):
                if not query.strip():
                    raise HTTPException(400, "query is required")
                return search(query, top_k, hybrid, section)
            
            uvicorn.run(app, host="0.0.0.0", port=8002)
        except ImportError:
            print("FastAPI not installed. Run: pip install fastapi uvicorn")
            print("Or use: python search.py --query \"盲陆聽莽職聞茅聴庐茅垄聵\"")

print("Loading search engine (embedding model + PostgreSQL tsvector)...", flush=True)
warmup()
print("Search engine ready\n", flush=True)

if __name__ == "__main__":
    main()







