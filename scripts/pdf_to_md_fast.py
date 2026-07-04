#!/usr/bin/env python3
"""Fast PDF to MD: layout + PyMuPDF text + cell-polygon table extraction."""

import os, sys, time, fitz
from PIL import Image
from pathlib import Path

MODEL_DIR = r"E:\AgentProjects\ai-solution-architect-lab\surya_models"
os.environ["SURYA_MODEL_DIR"] = MODEL_DIR
from surya.settings import settings
settings.MODEL_CACHE_DIR = MODEL_DIR
BATCH_SIZE, DPI = 50, 2.0


def load_models():
    from surya.foundation import FoundationPredictor
    from surya.layout import LayoutPredictor
    from surya.table_rec import TableRecPredictor
    print("Loading models...", end=" ", flush=True)
    t0 = time.time()
    lm = LayoutPredictor(FoundationPredictor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT, device="cuda"))
    tm = TableRecPredictor(checkpoint=settings.TABLE_REC_MODEL_CHECKPOINT, device="cuda")
    print(f"done ({time.time()-t0:.1f}s)")
    return lm, tm


def _cell_words(cell, page, ox, oy, sx, sy, all_words=None):
    """Extract cell text: words mode with expanded margin for boundary capture."""
    if not cell.polygon:
        return ""
    pts = cell.polygon
    ve, he = 8, 2
    r = fitz.Rect(
        (min(p[0] for p in pts) + ox) * sx - he,
        (min(p[1] for p in pts) + oy) * sy - ve,
        (max(p[0] for p in pts) + ox) * sx + he,
        (max(p[1] for p in pts) + oy) * sy + ve,
    )
    raw_words = [w[4] for w in page.get_text("words", clip=r)]
    clean = [w for w in raw_words if len(w) > 1 or w in ("I","A","a")]
    return " ".join(clean)


def table_to_md(result, page, sx, sy, ox=0, oy=0, all_words=None):
    cells = [c for c in result.cells if hasattr(c, "col_id") and hasattr(c, "row_id")]
    if not cells:
        return ""
    if all_words is None:
        all_words = page.get_text("words")
    mx_r, mx_c = max(c.row_id for c in cells), max(c.col_id for c in cells)
    grid = [[""] * (mx_c + 1) for _ in range(mx_r + 1)]
    for c in cells:
        if 0 <= c.row_id <= mx_r and 0 <= c.col_id <= mx_c:
            grid[c.row_id][c.col_id] = _cell_words(c, page, ox, oy, sx, sy, all_words)
    lines = []
    for i, row in enumerate(grid):
        lines.append("| " + " | ".join(row) + " |")
        if i == 0:
            lines.append("|" + "|".join(["---"] * len(row)) + "|")
    return "\n".join(lines)


def process_page(page, lm, tm, sx, sy, out_dir=None):
    pix = page.get_pixmap(matrix=fitz.Matrix(DPI, DPI))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    bboxes = sorted(lm([img])[0].bboxes, key=lambda b: (b.bbox[1], b.bbox[0]))
    md, img_n = [], 0
    for box in bboxes:
        label, b = box.label, box.bbox
        r = fitz.Rect(b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy)
        if label == "Table":
            try:
                res = tm([img.crop((b[0], b[1], b[2], b[3]))])[0]
                tbl = table_to_md(res, page, sx, sy, ox=b[0], oy=b[1])
                # Extract any text in table bbox not captured by cells (footnotes, etc.)
                extra = _fmt_text(page, r)
                if extra:
                    tbl_flat = " ".join(tbl.split()).lower().replace("|","").replace("*",""); tbl_flat = " ".join(tbl_flat.split())
                    new_lines = []
                    for l in extra.split("\n"):
                        l = l.strip()
                        if not l:
                            continue
                        l_clean = l.replace("*","")
                        if len(l_clean) < 15:
                            continue
                        l_norm = " ".join(l.split()).lower().replace("|","").replace("*","")
                        if l_norm in tbl_flat:
                            continue
                        words = l_clean.split()
                        num_words = sum(1 for w in words if any(c.isdigit() for c in w))
                        if num_words > len(words) * 0.3:
                            continue
                        new_lines.append(l)
                    if new_lines:
                        tbl += "\n\n" + "\n".join(new_lines)
                if tbl.strip():
                    md.append("\n" + tbl + "\n")
            except Exception:
                md.append(f"\nTable:\n{page.get_text('text', clip=r).strip()}\n")
        elif label in ("Text", "List"):
            t = _fmt_text(page, r)
            if t:
                md.append(t)
        elif label in ("Title", "Section-header"):
            t = _fmt_text(page, r)
            if t:
                md.append(f"\n## {t}\n")
        elif label in ("Figure", "Picture", "Image") and out_dir:
            fn = f"_page_{page.number}_Figure_{img_n}.jpeg"
            page.get_pixmap(matrix=fitz.Matrix(DPI, DPI), clip=r).save(str(out_dir / fn))
            md.append(f"\n![]({fn})\n")
            img_n += 1
    # Catch-all: lines not captured by layout (footnotes, bullets). Max 5.
    all_text = page.get_text("text")
    captured_normalized = " ".join(" ".join(md).split()).lower().replace("|","").replace("*","")
    captured_normalized = " ".join(captured_normalized.split())
    added = 0
    for cl in all_text.split("\n"):
        if added >= 5:
            break
        cl = cl.strip()
        cl_clean = cl.replace("*", "")
        if len(cl_clean) < 15:
            continue
        cl_norm = " ".join(cl.split()).lower()
        cl_norm_stripped = cl_norm.replace("*", "").replace("|", "")
        cl_nobullet = cl_norm_stripped.replace(chr(8226), " ")
        if cl_norm_stripped in captured_normalized or cl_nobullet in captured_normalized:
            continue
        words = cl_clean.split()
        num_words = sum(1 for w in words if any(c.isdigit() for c in w))
        if num_words > len(words) * 0.3:
            continue
        md.append(cl.replace(chr(8226), "- "))
        added += 1
    return "\n".join(md), img_n


def _fmt_text(page, rect):
    """Extract text from rect with bold formatting preserved."""
    blocks = page.get_text("dict", clip=rect)["blocks"]
    lines = []
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            parts = []
            for span in line["spans"]:
                t = span["text"]
                if (span["flags"] & 2) != 0 or "Bold" in span.get("font", ""):
                    t = f"**{t}**"
                parts.append(t)
            lines.append("".join(parts))
    return "\n".join(lines).strip()


def get_page_count(p):
    return len(fitz.open(p))


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("pdf"); p.add_argument("out_dir", nargs="?")
    p.add_argument("--name", "-n"); p.add_argument("--start", "-s", type=int)
    p.add_argument("--end", "-e", type=int); p.add_argument("--batch", "-b", type=int, default=BATCH_SIZE)
    args = p.parse_args()
    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"Error: {args.pdf} not found", file=sys.stderr); sys.exit(1)
    out_dir = Path(args.out_dir or pdf.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = get_page_count(str(pdf))
    start, end = (args.start or 1), min(args.end or total, total)
    lm, tm = load_models()
    doc = fitz.open(str(pdf))
    tp = doc[0].get_pixmap(matrix=fitz.Matrix(DPI, DPI))
    sx, sy = doc[0].rect.width / tp.width, doc[0].rect.height / tp.height
    print(f"\nConverting: {pdf.name}  ({total}p, range {start}-{end})")
    pages = list(range(start, end + 1))
    batches = [pages[i:i+args.batch] for i in range(0, len(pages), args.batch)]
    for bi, batch in enumerate(batches):
        bn = f"{(args.name or pdf.stem)}_p{batch[0]}-{batch[-1]}"
        batch_dir = out_dir / bn
        batch_dir.mkdir(parents=True, exist_ok=True)
        out = batch_dir / f"{bn}.md"
        if out.exists():
            print(f"  [{bi+1}/{len(batches)}] p{batch[0]}-{batch[-1]} exists, skip")
            continue
        print(f"  [{bi+1}/{len(batches)}] p{batch[0]}-{batch[-1]}...", end=" ", flush=True)
        t1 = time.time()
        pmd, img_c = [], 0
        for pn in batch:
            m, n = process_page(doc[pn-1], lm, tm, sx, sy, batch_dir)
            pmd.append(f"--- PAGE {pn} ---\n{m}")
            img_c += n
        out.write_text("\n\n".join(pmd), encoding="utf-8")
        sec = time.time() - t1
        print(f"{sec:.0f}s ({sec/len(batch):.1f}s/p, {img_c} img)")
    doc.close()
    print(f"\nDone! {end-start+1}p -> {out_dir}")

if __name__ == "__main__":
    main()
