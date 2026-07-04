#!/usr/bin/env python3
"""PDF to MD v3: uses cached layout results, no layout model. OCR fallback for table cells."""

import os, sys, time, json, fitz
from PIL import Image
from pathlib import Path

MODEL_DIR = r"E:\AgentProjects\ai-solution-architect-lab\surya_models"
os.environ["SURYA_MODEL_DIR"] = MODEL_DIR
from surya.settings import settings
settings.MODEL_CACHE_DIR = MODEL_DIR
from surya.table_rec import TableRecPredictor
DPI = 2.0

_REC = None
def _get_rec():
    global _REC
    if _REC is None:
        from surya.recognition import RecognitionPredictor
        from surya.foundation import FoundationPredictor
        enc = FoundationPredictor(checkpoint=settings.RECOGNITION_MODEL_CHECKPOINT, device="cuda")
        _REC = RecognitionPredictor(enc)
    return _REC

LAYOUT = []
def load_layout(path):
    global LAYOUT
    lines = open(path, encoding="utf-8").readlines()
    LAYOUT = [json.loads(l) for l in lines]
    return {d["page_num"]: d for d in LAYOUT}

def _cell_words(cell, page, ox, oy, sx, sy):
    ve, he = 8, 2
    pts = cell.polygon
    r = fitz.Rect((min(p[0] for p in pts)+ox)*sx-he, (min(p[1] for p in pts)+oy)*sy-ve,
                  (max(p[0] for p in pts)+ox)*sx+he, (max(p[1] for p in pts)+oy)*sy+ve)
    raw = [w[4] for w in page.get_text("words", clip=r)]
    clean = [w for w in raw if len(w) > 1 or w in ("I","A","a")]
    return " ".join(clean)

def table_to_md(result, page, sx, sy, ox=0, oy=0, table_img=None):
    cells = [c for c in result.cells if hasattr(c,"col_id") and hasattr(c,"row_id")]
    if not cells: return ""
    mx_r = max(c.row_id for c in cells); mx_c = max(c.col_id for c in cells)
    grid = [[""]*(mx_c+1) for _ in range(mx_r+1)]
    empty = []
    for c in cells:
        if 0 <= c.row_id <= mx_r and 0 <= c.col_id <= mx_c:
            t = _cell_words(c, page, ox, oy, sx, sy)
            if t.strip(): grid[c.row_id][c.col_id] = t
            else: empty.append(c)
    if empty and table_img:
        try:
            rec = _get_rec()
            cboxes = []
            for c in empty:
                pts = c.polygon
                cboxes.append([min(p[0] for p in pts), min(p[1] for p in pts),
                               max(p[0] for p in pts), max(p[1] for p in pts)])
            if cboxes:
                rs = rec([table_img], bboxes=[cboxes])
                ocr = rs[0]
                txts = []
                if hasattr(ocr, "text_lines"):
                    for tl in ocr.text_lines:
                        txts.append(getattr(tl, "text", str(tl)).strip())
                elif isinstance(ocr, list):
                    txts = [str(r).strip() for r in ocr]
                for i, c in enumerate(empty):
                    if i < len(txts) and txts[i]:
                        grid[c.row_id][c.col_id] = txts[i]
        except Exception as e:
            print(f"OCR error: {e}")
    ml = ["| " + " | ".join(row) + " |" for row in grid]
    ml.insert(1, "|" + "|".join(["---"]*len(grid[0]))+"|")
    return "\n".join(ml)

def process_page(page, sx, sy, blocks, tm, out_dir=None):
    """Process a single page using cached layout blocks."""
    md, img_n = [], 0
    for blk in blocks:
        label = blk["label"]
        b = blk["bbox"]  # image pixel coords (from layout scan)
        r = fitz.Rect(b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy)
        
        if label == "Table":
            try:
                # Need page image for table_rec + OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(DPI, DPI))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                table_crop = img.crop((int(b[0]), int(b[1]), int(b[2]), int(b[3])))
                res = tm([table_crop])[0]
                tbl = table_to_md(res, page, sx, sy, ox=b[0], oy=b[1], table_img=table_crop)
                extra = _fmt(page, r)
                if extra:
                    tbl_flat = " ".join(tbl.split()).lower().replace("|","").replace("*","")
                    tbl_flat = " ".join(tbl_flat.split())
                    nl = []
                    for l in extra.split("\n"):
                        l = l.strip()
                        if not l: continue
                        lc = l.replace("*","")
                        if len(lc) < 15: continue
                        ln = " ".join(l.split()).lower().replace("|","").replace("*","")
                        if ln in tbl_flat: continue
                        wc = sum(1 for w in lc.split() if any(c.isdigit() for c in w))
                        if wc > len(lc.split())*0.3: continue
                        nl.append(l)
                    if nl: tbl += "\n\n" + "\n".join(nl)
                if tbl.strip(): md.append("\n" + tbl + "\n")
            except: md.append(f"\nTable:\n{page.get_text('text', clip=r).strip()}\n")
        elif label in ("Text","List"):
            t = _fmt(page, r)
            if t: md.append(t)
        elif label in ("Title","Section-header"):
            t = _fmt(page, r)
            if t: md.append(f"\n## {t}\n")
        elif label in ("Figure","Picture","Image") and out_dir:
            fn = f"_page_{page.number}_Figure_{img_n}.jpeg"
            page.get_pixmap(matrix=fitz.Matrix(DPI,DPI), clip=r).save(str(out_dir/fn))
            md.append(f"\n![]({fn})\n")
            img_n += 1
    # catch-all
    all_text = page.get_text("text")
    cn = " ".join(" ".join(md).split()).lower().replace("|","").replace("*","")
    cn = " ".join(cn.split())
    added = 0
    for cl in all_text.split("\n"):
        if added >= 5: break
        cl = cl.strip()
        cc = cl.replace("*","")
        if len(cc) < 15: continue
        ck = " ".join(cl.split()).lower().replace("*","").replace("|","")
        cb = ck.replace(chr(8226)," ")
        if ck in cn or cb in cn: continue
        if sum(1 for w in cc.split() if any(c.isdigit() for c in w)) > len(cc.split())*0.3: continue
        md.append(cl.replace(chr(8226),"- "))
        added += 1
    return "\n".join(md), img_n

def _fmt(page, rect):
    blocks = page.get_text("dict", clip=rect)["blocks"]
    lines = []
    for b in blocks:
        if b["type"] != 0: continue
        for line in b["lines"]:
            parts = []
            for span in line["spans"]:
                t = span["text"]
                if (span["flags"] & 2) != 0 or "Bold" in span.get("font",""):
                    t = f"**{t}**"
                parts.append(t)
            lines.append("".join(parts))
    return "\n".join(lines).strip()

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("pdf"); p.add_argument("layout_jsonl"); p.add_argument("out_dir", nargs="?")
    p.add_argument("--name","-n"); p.add_argument("--start","-s",type=int); p.add_argument("--end","-e",type=int)
    args = p.parse_args()
    pdf = Path(args.pdf)
    if not pdf.exists(): print(f"Error: no pdf",file=sys.stderr); sys.exit(1)
    out_dir = Path(args.out_dir or pdf.parent)
    out_dir.mkdir(parents=True,exist_ok=True)
    
    t0 = time.time()
    layout_map = load_layout(args.layout_jsonl)
    print(f"Layout loaded: {len(layout_map)} pages in {time.time()-t0:.1f}s", flush=True)
    
    doc = fitz.open(str(pdf))
    total = len(doc)
    start, end = (args.start or 1), min(args.end or total, total)
    
    # Pre-compute sx,sy from first page
    tp = doc[0].get_pixmap(matrix=fitz.Matrix(DPI,DPI))
    sx, sy = doc[0].rect.width / tp.width, doc[0].rect.height / tp.height
    
    # Load table_rec + OCR models (no layout model!)
    print("Loading table_rec + OCR models...", end=" ", flush=True)
    tm = TableRecPredictor(checkpoint=settings.TABLE_REC_MODEL_CHECKPOINT, device="cuda")
    _get_rec()
    print(f"done ({time.time()-t0:.1f}s, rec only, no detection)", flush=True)
    
    print(f"\nConverting: {pdf.name} ({total}p, range {start}-{end})", flush=True)
    print(f"Output: {out_dir}/page_*.md (one per page)", flush=True)
    t1 = time.time()
    done = 0
    for pn in range(start, end+1):
        page = doc[pn-1]
        layout_data = layout_map.get(pn, {"blocks": []})
        m, n = process_page(page, sx, sy, layout_data["blocks"], tm, out_dir)
        (out_dir / f"page_{pn:05d}.md").write_text(
            f"--- PAGE {pn} ---\n{m}", encoding="utf-8")
        done += 1
        img_c = (img_c if 'img_c' in dir() else 0) + n
        elapsed = time.time()-t1
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - start + 1 - done) / rate if rate > 0 else 0
        if pn % 50 == 0 or pn == end:
            print(f"  [{done}/{(end-start+1)}] p{pn} {rate:.1f}p/s, eta {eta/60:.0f}min, mem={n}img", flush=True)
    sec = time.time()-t1
    print(f"\nDone! {done}p in {sec:.0f}s ({sec/done:.1f}s/p)", flush=True)
    doc.close()

if __name__ == "__main__":
    main()
