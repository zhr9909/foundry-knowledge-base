#!/usr/bin/env python3
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
"""
ingest.py - Step 2: Import JSONL into PostgreSQL + pgvector
=============================================================
Read extracted JSONL, clean, embed, and insert into PostgreSQL.

Usage:
    python ingest.py <jsonl_path>
    
    python ingest.py processed/asm-handbook-v2_extracted_*.jsonl
    
Options:
    --batch-size N    Batch size for embedding & insert (default: 32)
    --dry-run         Preview without writing
    --rebuild         Drop and recreate tables before import
"""

import json
import os
import sys
import time
import re
from pathlib import Path


CONFIG = {
    "host": "127.0.0.1",
    "port": 15432,
    "dbname": "foundry_kb",
    "user": "findmyjob",
    "password": "findmyjob_dev_password",
}

# ---- Cleaning helpers ----


def clean_text(text: str) -> str:
    """Basic text cleaning."""
    text = re.sub(r"\s+", " ", text)  # collapse whitespace
    text = re.sub(r"\.\s+\.\s+\.", "…", text)  # ellipsis
    text = re.sub(r"(?<=\d)\s+(?=\d)", " ", text)  # keep numbers together
    return text.strip()


def should_skip_table(table_text: str, page_text: str) -> bool:
    """
    Skip table chunk if the page_text already contains the table content.
    This avoids duplication.
    """
    if not page_text:
        return False
    # If page text is significantly longer and contains table keywords similar to table text
    table_core = table_text[:100].strip().lower()
    return table_core in page_text.lower()


def process_chunks(filepath: str, batch_size: int = 32):
    """Read JSONL, clean, deduplicate."""
    chunks = []
    page_texts = {}  # page -> text for dedup

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            chunks.append(chunk)
            if chunk["type"] == "page_text":
                page_texts[chunk["page"]] = chunk["text"]

    # Clean and deduplicate
    cleaned = []
    for chunk in chunks:
        text = clean_text(chunk["text"])
        if not text:
            continue

        # Skip table if page_text already covers it
        if chunk["type"] == "table":
            pt = page_texts.get(chunk["page"], "")
            if should_skip_table(text, pt):
                continue
            # Also dump as descriptive text
            text = _table_to_description(text, chunk.get("shape", ""))

        cleaned.append(chunk)

    return cleaned


def _table_to_description(table_text: str, shape: str) -> str:
    """Convert a table to a descriptive text for better RAG retrieval."""
    lines = table_text.split("\n")
    if len(lines) >= 2:
        header = lines[0].strip()
        # Prepend context
        return f"[Table ({shape})] {header}\n{table_text}"
    return table_text


def import_to_pg(chunks, batch_size=32, dry_run=False, source_id=None, source_title=None):
    """Import cleaned chunks into PostgreSQL with embeddings."""
    try:
        import psycopg2
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("Missing dependencies. Run:")
        print("  pip install psycopg2-binary sentence-transformers")
        sys.exit(1)

    # Load embedding model
    print("Loading embedding model (bge-small-zh-v1.5)...")
    # Fallback to English model if Chinese not available
    try:
        model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    except Exception:
        print("  zh model not available, falling back to all-MiniLM-L6-v2")
        model = SentenceTransformer("all-MiniLM-L6-v2")
    embed_dim = model.get_sentence_embedding_dimension()
    print(f"  Model dimension: {embed_dim}")

    # Dry run
    if dry_run:
        print(f"\n[DRY-RUN] Would import {len(chunks)} chunks")
        type_counts = {}
        for c in chunks:
            t = c["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, n in type_counts.items():
            print(f"  {t}: {n}")
        return

    # Connect to PostgreSQL
    conn = psycopg2.connect(**CONFIG)
    cur = conn.cursor()

    # Verify vector extension
    cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
    if cur.rowcount == 0:
        print("ERROR: pgvector extension not found!")
        print("Run: CREATE EXTENSION IF NOT EXISTS vector;")
        conn.close()
        sys.exit(1)

    # Get source document ID
    if source_id is None:
        source_name = source_title or chunks[0].get("source_file", "unknown")
        total_pages = max(c["page"] for c in chunks)
        cur.execute(
            "INSERT INTO document_sources (title, file_name, total_pages) "
            "VALUES (%s, %s, %s) RETURNING id",
            (source_name.replace(".pdf", "").replace("_", " ").title(),
             source_name, total_pages),
        )
        source_id = cur.fetchone()[0]
        conn.commit()
        print(f"  Registered new source: id={source_id}")
    else:
        print(f"  Using existing source: id={source_id}")

    # Batch insert
    total = len(chunks)
    inserted = 0
    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]

        # Embed
        embeddings = model.encode(texts, show_progress_bar=False)

        # Insert
        for chunk, emb in zip(batch, embeddings):
            page_text = chunk.get("text", "")
            cur.execute(
                """
                INSERT INTO chunks
                    (source_id, chunk_id, page, chunk_type, content_text,
                     table_shape, table_header, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (
                    source_id,
                    chunk["id"],
                    chunk["page"],
                    chunk["type"],
                    page_text,
                    chunk.get("shape"),
                    json.dumps(chunk.get("metadata", {}).get("header", [])),
                    emb.tolist(),
                ),
            )
            inserted += cur.rowcount

        conn.commit()

        elapsed = time.time() - start_time
        rate = inserted / elapsed if elapsed > 0 else 0
        pct = inserted / total * 100
        print(f"  [{inserted}/{total} | {pct:.0f}%] "
              f"{rate:.0f} chunks/s")

    elapsed = time.time() - start_time
    conn.close()
    print(f"\nDone: {inserted} chunks imported in {elapsed:.0f}s")
    print(f"Rate: {inserted/elapsed:.0f} chunks/s")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import JSONL into pgvector")
    parser.add_argument("jsonl_path", help="Path to extracted JSONL file")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding (default: 32)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--rebuild", action="store_true", help="Drop all data before import")
    parser.add_argument("--mode", choices=["full", "increment"], default="full", help="full=new source | increment=append to existing")
    parser.add_argument("--title", help="Source document title (used for increment mode)")
    parser.add_argument("--source-id", type=int, help="Existing source_id to append to (increment mode)")
    args = parser.parse_args()

    print("=== Ingest: JSONL -> pgvector ===")
    print(f"Input: {args.jsonl_path}")

    # Process chunks
    print("\n1. Cleaning chunks...")
    chunks = process_chunks(args.jsonl_path, args.batch_size)
    print(f"   {len(chunks)} chunks after cleaning/dedup")

    # Rebuild if requested
    if args.rebuild and not args.dry_run:
        try:
            import psycopg2
            conn = psycopg2.connect(**CONFIG)
            cur = conn.cursor()
            cur.execute("TRUNCATE chunks RESTART IDENTITY CASCADE")
            cur.execute("DELETE FROM document_sources")
            conn.commit()
            conn.close()
            print("   Tables truncated")
        except ImportError:
            pass

    # Determine mode
    src_id = args.source_id
    src_title = args.title
    if args.mode == "increment":
        print("\n[MODE: Increment] Appending to existing source")
        if src_id is None and src_title is None:
            try:
                import psycopg2
                c2 = psycopg2.connect(**CONFIG)
                c2r = c2.cursor()
                c2r.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM document_sources")
                src_id = c2r.fetchone()[0]
                c2.close()
                print(f"  Auto-assigned source_id={src_id}")
            except Exception as ex:
                print(f"  Auto-assign failed: {ex}")
    else:
        print("\n[MODE: Full] New source registration")

    # Import
    print("\n2. Embedding & importing...")
    import_to_pg(chunks, args.batch_size, args.dry_run, source_id=src_id, source_title=src_title)

    print("\nDone!")


if __name__ == "__main__":
    main()


