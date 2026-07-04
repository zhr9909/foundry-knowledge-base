#!/usr/bin/env python3
"""Hybrid PDF to MD: fast pipeline for text pages, marker subprocess for table pages."""

import os, sys, time, subprocess, tempfile, json, fitz
from PIL import Image
from pathlib import Path

MODEL_DIR = r"E:\AgentProjects\ai-solution-architect-lab\surya_models"
os.environ["SURYA_MODEL_DIR"] = MODEL_DIR
from surya.settings import settings
settings.MODEL_CACHE_DIR = MODEL_DIR
DPI = 2.0

MARKER_WORKER = None

def get_marker_worker():
    global MARKER_WORKER
    if MARKER_WORKER is None:
        MARKER_WORKER = Path(__file__).parent / "_marker_worker.py"
        md = MODEL_DIR.replace("\\", "\\\\")
        code = (
            '#!/usr/bin/env python3\n'
            'import os, sys, json\n'
            f'os.environ["SURYA_MODEL_DIR"] = r"{md}"\n'
            'from surya.settings import settings\n'
            f'settings.MODEL_CACHE_DIR = r"{md}"\n'
            'from marker.converters.pdf import PdfConverter\n'
            'from marker.models import create_model_dict\n'
            'from marker.output import text_from_rendered\n'
            'pdf_path, out_path = sys.argv[1], sys.argv[2]\n'
            'converter = PdfConverter(artifact_dict=create_model_dict())\n'
            'rendered = converter(pdf_path)\n'
            'text, metadata, images = text_from_rendered(rendered)\n'
            'with open(out_path, "w", encoding="utf-8") as f:\n'
            '    f.write(text)\n'
            'with open(out_path + ".img.json", "w") as f:\n'
            '    json.dump({k: list(img.size) for k, img in images.items()}, f)\n'
        )
        MARKER_WORKER.write_text(code, encoding="utf-8")
    return MARKER_WORKER


def load_layout_model():
    from surya.foundation import FoundationPredictor
    from surya.layout import LayoutPredictor
    print("Loading layout model...", end=" ", flush=True)
    t0 = time.time()
    lm = LayoutPredictor(FoundationPredictor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT, device="cuda"))
    print(f"done ({time.time()-t0:.1f}s)")
    return lm


def page_to_temp_pdf(page, tmpdir):
    fn = tmpdir / f"p{page.number+1}.pdf"
    doc = fitz.open()
    doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
    doc.save(str(fn))
    doc.close()
    return str(fn)


def process_page_fast(page, lm, sx, sy, out_dir=None):
    pix = page.get_pixmap(matrix=fitz.Matrix(DPI, DPI))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    bboxes = sorted(lm([img])[0].bboxes, key=lambda b: (b.bbox[1], b.bbox[0]))
    md, img_n = [], 0
    for box in bboxes:
        label, b = box.label, box.bbox
        r = fitz.Rect(b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy)
        if label in ("Text", "List", "Table"):
            t = fmt_text(page, r)
            if t: md.append(t)
        elif label in ("Title", "Section-header"):
            t = fmt_text(page, r)
            if t: md.append(f"\n## {t}\n")
        elif label in ("Figure", "Picture", "Image") and out_dir:
            fn = f"_page_{page.number}_Figure_{img_n}.jpeg"
            page.get_pixmap(matrix=fitz.Matrix(DPI, DPI), clip=r).save(str(out_dir / fn))
            md.append(f"\n![]({fn})\n")
            img_n += 1
    return "\n".join(md), img_n


def process_page_table(page, out_dir):
    worker = get_marker_worker()
    with tempfile.TemporaryDirectory() as tmpdir:
        T = Path(tmpdir)
        pdf_path = page_to_temp_pdf(page, T)
        out_path = str(T / "marker_out.md")
        py = r"E:\conda_envs\marker\python.exe"
        result = subprocess.run([py, str(worker), pdf_path, out_path],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return f"Table extraction error", 0
        text = Path(out_path).read_text(encoding="utf-8")
        img_count = 0
        return text, img_count


def fmt_text(page, rect):
    blocks = page.get_text("dict", clip=rect)["blocks"]
    lines = []
    for b in blocks:
        if b["type"] != 0: continue
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
    p.add_argument("--end", "-e", type=int)
    args = p.parse_args()
    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"Error: {args.pdf} not found", file=sys.stderr); sys.exit(1)
    out_dir = Path(args.out_dir or pdf.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = get_page_count(str(pdf))
    start, end = (args.start or 1), min(args.end or total, total)
    
    get_marker_worker()
    lm = load_layout_model()
    doc = fitz.open(str(pdf))
    tp = doc[0].get_pixmap(matrix=fitz.Matrix(DPI, DPI))
    sx, sy = doc[0].rect.width / tp.width, doc[0].rect.height / tp.height
    
    print(f"\nConverting: {pdf.name}  ({total}p, range {start}-{end})")
    t_total = time.time()
    table_count, fast_count = 0, 0
    
    for pn in range(start, end + 1):
        page = doc[pn-1]
        pix = page.get_pixmap(matrix=fitz.Matrix(DPI, DPI))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        bboxes = sorted(lm([img])[0].bboxes, key=lambda b: (b.bbox[1], b.bbox[0]))
        has_table = any(box.label == "Table" for box in bboxes)
        
        out_fn = f"{args.name or pdf.stem}_p{pn:04d}.md"
        out_path = out_dir / out_fn
        if out_path.exists() and out_path.stat().st_size > 50:
            print(f"  p{pn} exists, skip")
            continue
        
        t1 = time.time()
        if has_table:
            table_count += 1
            print(f"  p{pn} [TABLE]...", end=" ", flush=True)
            m, n = process_page_table(page, out_dir)
        else:
            fast_count += 1
            print(f"  p{pn} [FAST]...", end=" ", flush=True)
            m, n = process_page_fast(page, lm, sx, sy, out_dir)
        
        out_path.write_text(f"--- PAGE {pn} ---\n{m}", encoding="utf-8")
        sec = time.time() - t1
        print(f"{sec:.0f}s")
    
    doc.close()
    h = (time.time()-t_total)/3600
    print(f"\nDone! {end-start+1}p ({fast_count} fast, {table_count} table) in {h:.2f}h")

if __name__ == "__main__":
    main()
