#!/usr/bin/env python3
"""Batch layout scan for all PDFs in raw folder."""

import os, sys, time, json, fitz, re
from PIL import Image
from pathlib import Path

MODEL_DIR = r"E:\AgentProjects\ai-solution-architect-lab\surya_models"
os.environ["SURYA_MODEL_DIR"] = MODEL_DIR
from surya.settings import settings
settings.MODEL_CACHE_DIR = MODEL_DIR
from surya.foundation import FoundationPredictor
from surya.layout import LayoutPredictor

RAW = Path(r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\raw")
OUT = Path(r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\processed\layout")
OUT.mkdir(parents=True, exist_ok=True)
BATCH = 8
DPI = 2.0

def sanitize(name):
    """Sanitize filename for use as directory name."""
    name = name.replace(".pdf", "").strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r'\s+', "_", name)
    if len(name) > 80:
        name = name[:80].rstrip("_")
    return name

# Find all PDFs
pdfs = sorted(RAW.glob("*.pdf"), key=lambda p: p.name)
print(f"Found {len(pdfs)} PDFs", flush=True)

# Load layout model once
t0 = time.time()
print("Loading layout model...", end=" ", flush=True)
lm = LayoutPredictor(FoundationPredictor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT, device="cuda"))
print(f"done ({time.time()-t0:.1f}s)", flush=True)

total_pages, total_time = 0, 0
summary = []

for pdf_path in pdfs:
    fname = pdf_path.name
    dir_name = sanitize(fname)
    out_dir = OUT / dir_name
    out_file = out_dir / "layout_results.jsonl"
    
    # Skip if already done
    if out_file.exists():
        pages_done = len(open(out_file, encoding="utf-8").readlines())
        print(f"  SKIP {fname[:50]}... ({pages_done} pages already done)", flush=True)
        summary.append(f"  SKIP {fname[:50]} => {pages_done}p (exists)")
        continue
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        doc = fitz.open(str(pdf_path))
        total = len(doc)
        print(f"\n[{pdfs.index(pdf_path)+1}/{len(pdfs)}] {fname[:60]} ({total}p)", flush=True)
        
        file_start = time.time()
        f_out = open(out_file, "w", encoding="utf-8")
        table_count = 0
        
        for batch_start in range(0, total, BATCH):
            batch_end = min(batch_start + BATCH, total)
            pages = list(range(batch_start, batch_end))
            
            images = []
            dims = []
            for pn in pages:
                page = doc[pn]
                pix = page.get_pixmap(matrix=fitz.Matrix(DPI, DPI))
                images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
                dims.append((page.rect.width, page.rect.height))
            
            results = lm(images)
            
            for i, result in enumerate(results):
                pn = pages[i] + 1
                blocks = []
                has_table = False
                for bbox_obj in result.bboxes:
                    blocks.append({
                        "label": bbox_obj.label,
                        "bbox": [round(v, 1) for v in bbox_obj.bbox],
                        "confidence": round(bbox_obj.confidence, 3)
                    })
                    if bbox_obj.label == "Table":
                        has_table = True
                        table_count += 1
                
                page_data = {
                    "page_num": pn,
                    "width": round(dims[i][0], 1),
                    "height": round(dims[i][1], 1),
                    "blocks": blocks
                }
                f_out.write(json.dumps(page_data, ensure_ascii=False) + "\n")
        
        f_out.close()
        doc.close()
        file_time = time.time() - file_start
        total_pages += total
        total_time += file_time
        rate = total / file_time if file_time > 0 else 0
        
        print(f"  => {total}p in {file_time:.0f}s ({rate:.1f}p/s, {table_count} tables)", flush=True)
        summary.append(f"  OK  {fname[:50]} => {total}p in {file_time:.0f}s, {table_count}tables")
        
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
        summary.append(f"  ERR  {fname[:50]} => {e}")
        if out_file.exists():
            out_file.unlink()  # Delete partial file

print(f"\n=== Summary ===")
for s in summary:
    print(s)
print(f"\nTotal: {total_pages} pages in {total_time:.0f}s ({total_pages/total_time:.1f}p/s)")
print(f"Output: {OUT}/")
