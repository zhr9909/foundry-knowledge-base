#!/usr/bin/env python3
"""
pdf_extractor.py - Step 1: Coarse Extraction
=============================================
Extract text and tables from PDF into JSONL format.
Each line = one extractable unit (page text block or table).

Usage:
    python pdf_extractor.py <pdf_path> <output_dir>
    
    python pdf_extractor.py raw/asm-handbook-v2.pdf processed/
    
Options:
    --start-page N   开始页（从1开始）
    --end-page N     结束页
    --max-pages N    最多处理N页（用于测试）
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)


def extract_page(page, page_num: int) -> list:
    """Extract text and tables from a single page, return list of chunks."""
    chunks = []
    
    # 1. Extract text
    text = page.extract_text() or ""
    
    # 2. Extract tables
    tables = page.extract_tables() or []
    
    # Build page-level chunk with text
    if text.strip():
        chunk = {
            "id": f"page-{page_num:05d}",
            "type": "page_text",
            "source_file": pdf_path_name,
            "page": page_num,
            "text": text.strip(),
            "has_tables": len(tables) > 0,
            "num_tables": len(tables),
            "metadata": {}
        }
        chunks.append(chunk)
    
    # Build per-table chunks
    for ti, table in enumerate(tables):
        if not table or not any(any(cell for cell in row) for row in table):
            continue
        
        # Convert table to text representation
        rows = []
        for row in table:
            cleaned = [str(c).strip() if c else "" for c in row]
            rows.append(cleaned)
        
        # Flatten to markdown-like text
        table_text_lines = []
        for row in rows:
            table_text_lines.append(" | ".join(row))
        table_text = "\n".join(table_text_lines)
        
        chunk = {
            "id": f"table-{page_num:05d}-{ti+1:02d}",
            "type": "table",
            "source_file": pdf_path_name,
            "page": page_num,
            "table_index": ti + 1,
            "text": table_text,
            "shape": f"{len(rows)}r x {max(len(r) for r in rows) if rows else 0}c",
            "metadata": {
                "header": rows[0] if rows else [],
                "row_count": len(rows),
            }
        }
        chunks.append(chunk)
    
    return chunks


def process_pdf(pdf_path: str, output_dir: str, start_page: int = 1,
                end_page: int = None, max_pages: int = None):
    """Process PDF and write chunks to JSONL."""
    global pdf_path_name
    pdf_path_name = os.path.basename(pdf_path)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Output file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(pdf_path_name)[0]
    output_file = output_dir / f"{base_name}_extracted_{timestamp}.jsonl"
    
    # Stats
    total_chunks = 0
    total_tables = 0
    total_pages_processed = 0
    start_time = time.time()
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        end = end_page or total_pages
        
        print(f"PDF: {pdf_path_name} ({total_pages} pages)")
        print(f"Output: {output_file}")
        print(f"Range: pages {start_page}-{end}" + 
              (f" (max {max_pages} pages)" if max_pages else ""))
        print(f"{'='*60}")
        
        with open(output_file, "w", encoding="utf-8") as out:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                
                if page_num < start_page:
                    continue
                if end_page and page_num > end_page:
                    break
                if max_pages and total_pages_processed >= max_pages:
                    break
                
                chunks = extract_page(page, page_num)
                for chunk in chunks:
                    out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                
                total_chunks += len(chunks)
                total_tables += sum(1 for c in chunks if c["type"] == "table")
                total_pages_processed += 1
                
                if total_pages_processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = total_pages_processed / elapsed if elapsed > 0 else 0
                    print(f"  [{total_pages_processed}/{end-start_page+1}] "
                          f"{total_chunks} chunks, {total_tables} tables "
                          f"({rate:.1f} pg/s)")
    
    elapsed = time.time() - start_time
    print(f"{'='*60}")
    print(f"Done: {total_pages_processed} pages, {total_chunks} chunks "
          f"({total_tables} tables) in {elapsed:.1f}s")
    print(f"Output: {output_file}")
    return output_file


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract text and tables from PDF")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("output_dir", help="Output directory for JSONL")
    parser.add_argument("--start-page", type=int, default=1, help="Start page")
    parser.add_argument("--end-page", type=int, default=None, help="End page")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages to process")
    
    args = parser.parse_args()
    
    pdf_path_name = ""
    process_pdf(args.pdf_path, args.output_dir,
                start_page=args.start_page,
                end_page=args.end_page,
                max_pages=args.max_pages)
