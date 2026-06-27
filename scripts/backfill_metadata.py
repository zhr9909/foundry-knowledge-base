#!/usr/bin/env python3
"""
backfill_metadata.py
====================
Extract PDF table of contents → build section map → backfill chunks.metadata JSONB.

Usage:
    python backfill_metadata.py <pdf_path>
    
    python backfill_metadata.py raw/asm-handbook-v2.pdf
"""

import json
import os
import sys
from pathlib import Path

import PyPDF2

CONFIG = {
    "host": "127.0.0.1",
    "port": 15432,
    "dbname": "foundry_kb",
    "user": "findmyjob",
    "password": "findmyjob_dev_password",
}


def extract_toc(pdf_path: str) -> list:
    """Extract table of contents from PDF, return list of {title, page, level}."""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        
        def walk(items, level=0):
            results = []
            for item in items:
                if isinstance(item, list):
                    results.extend(walk(item, level + 1))
                else:
                    try:
                        page = reader.get_destination_page_number(item) + 1
                        title = item.get("/Title", str(item)) if isinstance(item, dict) else getattr(item, "title", str(item))
                        if title and isinstance(title, str):
                            results.append({"level": level, "title": title.strip(), "page": page})
                    except:
                        pass
            return results
        
        return walk(reader.outline) if reader.outline else []


def build_section_map(entries: list) -> dict:
    """Build page → section_path mapping."""
    # Sort by page
    sorted_entries = sorted(entries, key=lambda e: e["page"])
    
    # Build hierarchy stack
    section_map = {}  # page → section_path (list)
    active_paths = {}  # level → {title, page}
    
    all_pages = sorted(set(e["page"] for e in sorted_entries))
    
    for entry in sorted_entries:
        level = entry["level"]
        title = entry["title"]
        page = entry["page"]
        
        # Clear any deeper levels
        for l in list(active_paths.keys()):
            if l >= level:
                del active_paths[l]
        
        active_paths[level] = {"title": title, "page": page}
        
        # Build the full path for this entry
        path = []
        for l in sorted(active_paths.keys()):
            path.append(active_paths[l]["title"])
        
        section_map[page] = {
            "section_path": " / ".join(path),
            "sections": path,
            "page": page,
        }
    
    return section_map


def section_for_page(section_map: dict, page: int) -> dict:
    """Find the section for a given page by checking the nearest preceding section entry."""
    if page in section_map:
        return section_map[page]
    
    # Find the nearest section that starts before this page
    sorted_pages = sorted(section_map.keys())
    best_page = None
    for p in sorted_pages:
        if p <= page:
            best_page = p
        else:
            break
    
    if best_page:
        meta = dict(section_map[best_page])
        meta["page"] = page
        return meta
    
    return {"section_path": "Preliminary", "sections": ["Preliminary"], "page": page}


def backfill(pdf_path: str, dry_run: bool = False):
    """Extract TOC, build section map, backfill metadata."""
    import psycopg2
    import psycopg2.extras
    
    print("=== Backfill: PDF TOC → chunks.metadata ===\n")
    
    # Step 1: Extract TOC
    print("1. Extracting PDF table of contents...")
    entries = extract_toc(pdf_path)
    print(f"   Found {len(entries)} entries")
    
    # Show structure
    for e in entries[:20]:
        indent = "  " * e["level"]
        print(f"{indent}[pg.{e['page']}] {e['title'][:60]}")
    if len(entries) > 20:
        print(f"   ... ({len(entries)} entries total)")
    
    # Step 2: Build section map
    print("\n2. Building page → section map...")
    section_map = build_section_map(entries)
    print(f"   {len(section_map)} section boundaries mapped")
    
    # Step 3: Connect to DB
    conn = psycopg2.connect(**CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get all chunks
    cur.execute("SELECT id, page, chunk_id, chunk_type, metadata FROM chunks ORDER BY page")
    chunks = cur.fetchall()
    print(f"   Processing {len(chunks)} chunks...")
    
    # Step 4: Backfill metadata
    updated = 0
    errors = 0
    
    for chunk in chunks:
        page = chunk["page"]
        meta = section_for_page(section_map, page)
        
        new_metadata = {
            "section_path": meta["section_path"],
            "sections": meta["sections"],
            "section_page": meta.get("_page", page),
            "type": chunk["chunk_type"],
        }
        
        if dry_run:
            if updated < 5:
                print(f"   [DRY-RUN] {chunk['chunk_id']}: section={meta['section_path'][:60]}")
            elif updated == 5:
                print(f"   [DRY-RUN] ... ({len(chunks)} chunks total)")
        else:
            try:
                cur.execute(
                    "UPDATE chunks SET metadata = %s WHERE id = %s",
                    (json.dumps(new_metadata, ensure_ascii=False), chunk["id"]),
                )
                updated += 1
            except Exception as e:
                errors += 1
                if errors < 3:
                    print(f"   [ERROR] chunk {chunk['chunk_id']}: {e}")
        
        updated += 1
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print(f"\nDone! {updated} chunks metadata updated" + (f" (dry-run)" if dry_run else ""))
    if errors:
        print(f"Errors: {errors}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill metadata from PDF TOC")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    
    backfill(args.pdf_path, dry_run=args.dry_run)
