#!/usr/bin/env python3
"""Batch convert all PDFs to markdown using cached layout + table_rec + OCR."""

import os, sys, time, json, re, fitz
from PIL import Image
from pathlib import Path

MODEL_DIR = r"E:\AgentProjects\ai-solution-architect-lab\surya_models"
os.environ["SURYA_MODEL_DIR"] = MODEL_DIR
from surya.settings import settings
settings.MODEL_CACHE_DIR = MODEL_DIR
from surya.table_rec import TableRecPredictor
from surya.recognition import RecognitionPredictor
from surya.foundation import FoundationPredictor
DPI = 2.0

RAW = Path(r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\raw")
LAYOUT_DIR = Path(r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\processed\layout")
OUT = Path(r"E:\AgentProjects\ai-solution-architect-lab\projects\foundry-knowledge-base\processed\markdown")
DPI = 2.0

_REC = None
def _get_rec():
    global _REC
    if _REC is None:
        enc = FoundationPredictor(checkpoint=settings.RECOGNITION_MODEL_CHECKPOINT, device="cuda")
        _REC = RecognitionPredictor(enc)
    return _REC

def sanitize(name):
    name = name.replace(".pdf", "").strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r'\s+', "_", name)
    if len(name) > 80:
        name = name[:80].rstrip("_")
    return name

def fmt_text(page, rect):
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

def cell_words(cell, page, ox, oy, sx, sy):
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
            t = cell_words(c, page, ox, oy, sx, sy)
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
            print(f"    OCR err: {e}")
    ml = ["| " + " | ".join(row) + " |" for row in grid]
    ml.insert(1, "|" + "|".join(["---"]*len(grid[0]))+"|")
    return "\n".join(ml)

def load_layout(jl_path):
    layout = {}
    if not jl_path.exists():
        return layout
    for l in open(jl_path, encoding="utf-8"):
        d = json.loads(l)
        layout[d["page_num"]] = d
    return layout

def process_page(page, sx, sy, blocks, tm, out_dir):
    md, img_n = [], 0
    for blk in blocks:
        label = blk["label"]; b = blk["bbox"]
        r = fitz.Rect(b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy)
        if label == "Table":
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(DPI,DPI))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                tc = img.crop((int(b[0]), int(b[1]), int(b[2]), int(b[3])))
                res = tm([tc])[0]
                tbl = table_to_md(res, page, sx, sy, ox=b[0], oy=b[1], table_img=tc)
                extra = fmt_text(page, r)
                if extra:
                    tf = " ".join(tbl.split()).lower().replace("|","").replace("*","")
                    tf = " ".join(tf.split())
                    nl = []
                    for l in extra.split("\n"):
                        l = l.strip()
                        if not l: continue
                        lc = l.replace("*","")
                        if len(lc) < 15: continue
                        ln = " ".join(l.split()).lower().replace("|","").replace("*","")
                        if ln in tf: continue
                        wc = sum(1 for w in lc.split() if any(c.isdigit() for c in w))
                        if wc > len(lc.split())*0.3: continue
                        nl.append(l)
                    if nl: tbl += "\n\n" + "\n".join(nl)
                if tbl.strip(): md.append("\n" + tbl + "\n")
            except:
                md.append(f"\nTable:\n{page.get_text('text',clip=r).strip()}\n")
        elif label in ("Text","List"):
            t = fmt_text(page, r)
            if t: md.append(t)
        elif label in ("Title","Section-header"):
            t = fmt_text(page, r)
            if t: md.append(f"\n## {t}\n")
        elif label in ("Figure","Picture","Image") and out_dir:
            fn = f"img_{page.number}_{img_n}.jpeg"
            page.get_pixmap(matrix=fitz.Matrix(DPI,DPI), clip=r).save(str(out_dir/fn))
            md.append(f"\n![]({fn})\n"); img_n += 1
    # catch-all
    all_text = page.get_text("text")
    cn = " ".join(" ".join(md).split()).lower().replace("|","").replace("*","")
    cn = " ".join(cn.split()); added = 0
    for cl in all_text.split("\n"):
        if added >= 5: break
        cl = cl.strip(); cc = cl.replace("*","")
        if len(cc) < 15: continue
        ck = " ".join(cl.split()).lower().replace("*","").replace("|","")
        cb = ck.replace(chr(8226)," ")
        if ck in cn or cb in cn: continue
        if sum(1 for w in cc.split() if any(c.isdigit() for c in w)) > len(cc.split())*0.3: continue
        md.append(cl.replace(chr(8226),"- ")); added += 1
    return "\n".join(md), img_n

# Main
print("Loading table_rec + recognition models...", end=" ", flush=True)
t0 = time.time()
tm = TableRecPredictor(checkpoint=settings.TABLE_REC_MODEL_CHECKPOINT, device="cuda")
_get_rec()
print(f"done ({time.time()-t0:.1f}s)", flush=True)

pdfs = sorted(RAW.glob("*.pdf"), key=lambda p: p.name)
print(f"Found {len(pdfs)} PDFs\n", flush=True)

total_all, time_all = 0, 0
for idx, pdf_path in enumerate(pdfs):
    fname = pdf_path.name
    sname = sanitize(fname)
    layout_jl = LAYOUT_DIR / sname / "layout_results.jsonl"
    out_dir = OUT / sname
    out_dir.mkdir(parents=True, exist_ok=True)
    
    layout = load_layout(layout_jl)
    if not layout:
        print(f"  [{idx+1}/{len(pdfs)}] {fname[:50]}... NO LAYOUT DATA, skip")
        continue
    
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    tp = doc[0].get_pixmap(matrix=fitz.Matrix(DPI,DPI))
    sx, sy = doc[0].rect.width / tp.width, doc[0].rect.height / tp.height
    
    print(f"  [{idx+1}/{len(pdfs)}] {fname[:55]} ({total}p)", flush=True)
    file_start = time.time()
    done = 0
    
    for pn in range(1, total+1):
        out_file = out_dir / f"page_{pn:05d}.md"
        if out_file.exists():
            done += 1
            continue
        page = doc[pn-1]
        blocks = layout.get(pn, {"blocks": []})["blocks"]
        m, n = process_page(page, sx, sy, blocks, tm, out_dir)
        out_file.write_text(f"--- PAGE {pn} ---\n{m}", encoding="utf-8")
        done += 1
        if done % 100 == 0 or done == total:
            print(f"    ...p{done}/{total}", flush=True)
    
    ft = time.time() - file_start
    total_all += total; time_all += ft
    print(f"    => {total}p in {ft:.0f}s ({total/ft:.1f}p/s)", flush=True)
    doc.close()

print(f"\n=== Done ===")
print(f"Files: {len(pdfs)}, Pages: {total_all}")
print(f"Time: {time_all:.0f}s ({time_all/3600:.1f}h)")
print(f"Output: {OUT}/")
