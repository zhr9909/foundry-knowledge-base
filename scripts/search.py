#!/usr/bin/env python3
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

"""search.py - RAG Retrieval API with hybrid search + section filtering"""

import json, os, sys, time, urllib.request
from typing import Optional
from pathlib import Path

try:
    import psycopg2, psycopg2.extras, logging
    _sqllog = logging.getLogger("agent")
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
            get_embedding_model._model = SentenceTransformer("BAAI/bge-small-zh-v1.5", device="cpu")
        except Exception as e:
            print(f"  Primary model failed: {e}")
            print("  Trying all-MiniLM-L6-v2...")
            try:
                get_embedding_model._model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            except Exception as e2:
                print(f"  All models failed: {e2}")
                sys.exit(1)
    return get_embedding_model._model
def search(query: str, top_k: int = 10, hybrid: bool = True, section: str = None) -> dict:
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
        # Hybrid: vector + FTS + section filter
        sql = f"""
        WITH vector_results AS (
            SELECT c.id, c.chunk_id, c.page, c.chunk_type,
                c.content_text, c.table_shape,
                ds.title as source_title, c.metadata,
                1 - (c.embedding <=> %(query_vec)s::vector) AS score,
                ROW_NUMBER() OVER (ORDER BY c.embedding <=> %(query_vec)s::vector) AS rn
            FROM chunks c
            JOIN document_sources ds ON ds.id = c.source_id
            WHERE 1=1 {section_where}
            ORDER BY c.embedding <=> %(query_vec)s::vector
            LIMIT %(limit)s
        ),
        fts_results AS (
            SELECT c.id, c.chunk_id, c.page, c.chunk_type,
                c.content_text, c.table_shape,
                ds.title as source_title, c.metadata,
                ts_rank(c.tsv, plainto_tsquery('english', %(query)s)) AS score,
                ROW_NUMBER() OVER (ORDER BY ts_rank(c.tsv, plainto_tsquery('english', %(query)s)) DESC) AS rn
            FROM chunks c
            JOIN document_sources ds ON ds.id = c.source_id
            WHERE c.tsv @@ plainto_tsquery('english', %(query)s) {section_where}
            ORDER BY ts_rank(c.tsv, plainto_tsquery('english', %(query)s)) DESC
            LIMIT %(limit)s
        ),
        combined AS (
            SELECT vr.id, vr.chunk_id, vr.page, vr.chunk_type, vr.content_text,
                vr.table_shape, vr.source_title, vr.metadata,
                vr.score AS vec_score,
                COALESCE(fr.score, 0) AS fts_score
            FROM vector_results vr
            LEFT JOIN fts_results fr ON vr.id = fr.id AND vr.chunk_id = fr.chunk_id
        )
        SELECT id, chunk_id, page, chunk_type, content_text, table_shape, source_title, metadata,
            ROUND((vec_score + CASE WHEN fts_score > 0 THEN 0.1 ELSE 0 END)::numeric, 4) AS score
        FROM combined
        ORDER BY score DESC LIMIT %(top_k)s
        """
        params = {"query_vec": query_vec, "query": query, "limit": top_k * 2, "top_k": top_k}
        if section:
            params["section_filter"] = section
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
    
    _sqllog.info(f"SQL [{'hybrid' if hybrid else 'vec'}] query='{query[:60]}' top_k={top_k} section={section or 'all'}")
    _sqllog.info(f"  params: limit={params.get('limit','?')}, top_k={params.get('top_k','?')}")
    start = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    elapsed = (time.time() - start) * 1000
    _sqllog.info(f"  returned {len(rows)} rows in {elapsed:.0f}ms")
    
    results = []
    for row in rows:
        section_path = ""
        if row["metadata"] and "section_path" in row["metadata"]:
            section_path = row["metadata"]["section_path"]
        results.append({
            "id": row["id"],
            "chunk_id": row["chunk_id"],
            "page": row["page"],
            "type": row["chunk_type"],
            "text": row["content_text"][:500] + ("..." if len(row["content_text"]) > 500 else ""),
            "text_full": row["content_text"],
            "table_shape": row["table_shape"],
            "source": row["source_title"],
            "section": section_path,
            "score": round(float(row["score"]), 4),
        })
    
    # Log
    log_query = query + (f" [section:{section}]" if section else "") + (" [hybrid]" if hybrid else "")
    cur.execute(
        "INSERT INTO retrieval_log (query, top_k, results, latency_ms) VALUES (%s, %s, %s, %s)",
        (log_query, top_k, json.dumps(results[:5]), int(elapsed)),
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

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--query":
        q = sys.argv[2] if len(sys.argv) > 2 else "铝合金"
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
            
            app = FastAPI(title="铸造知识库检索 API", version="0.2.0")
            
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
            print("Or use: python search.py --query \"你的问题\"")

if __name__ == "__main__":
    main()







