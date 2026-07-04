#!/usr/bin/env python3
"""layout_chunker.py - Layout-aware chunking → JSONL for RAG ingestion."""

import os, sys, json, re, time
from pathlib import Path
from collections import OrderedDict

MATERIAL_FAMILIES = json.loads(
    open(Path(__file__).parent.parent / "processed" / "materials_taxonomy.json", encoding="utf-8").read())
MATERIAL_FAMILIES = {n: i["patterns"] for n, i in MATERIAL_FAMILIES.items()}

ALLOY_PATTERN = re.compile(
    r'(\d{4}(?:-[A-Z]\d*)?(?:\.\d)?)\s+'   # 6061-T6, 356.0
    r'(?=alloy|aluminum|temper|grade|al|mg|si|cu)', re.I
)

TEMPERS = {"O","H111","H112","H116","H321","T3","T4","T5","T6","T651","T7","T73","T7351","T8","W"}

def sanitize(name):
    name = name.replace(".pdf","").strip()
    name = re.sub(r'[<>:"/\\|?*]',"_", name)
    name = re.sub(r'\s+',"_", name)
    return name[:60].rstrip("_")

def extract_material_tags(text, section_path):
    tags = set()
    sp = section_path.lower()
    for family, patterns in MATERIAL_FAMILIES.items():
        for pat in patterns:
            if re.search(pat, sp):
                tags.add(family)
                break
    for m in ALLOY_PATTERN.finditer(text):
        tags.add(m.group(1).lower())
    for t in TEMPERS:
        if len(t) == 1:
            # Single-letter: only match as alloy suffix "1100-O" or "O temper"
            if re.search(r'\d{4}(?:-[A-Z]\d*)?-' + t + r'\b', text):
                tags.add(t.lower())
            elif re.search(r'\b' + t + r'\s+(?:temper|condition)\b', text, re.I):
                tags.add(t.lower())
            continue
        if re.search(r'\b' + t + r'\b', text):
            tags.add(t.lower())
    return sorted(tags)

def count_cols(table_text):
    first = table_text.strip().split("\n")[0] if table_text.strip() else ""
    return len([c for c in first.split("|") if c.strip()]) if first else 0

def count_tokens(text):
    """Rough estimation: ~2 chars per token for mixed CN/EN."""
    return max(1, len(text) // 2)

class LayoutChunker:
    def __init__(self, md_dir, layout_jsonl, source_name, pdf_path=None, source_id=None):
        self.md_dir = Path(md_dir)
        self.source_name = source_name
        self.source_id = source_id
        self.prefix = sanitize(source_name)[:10]
        
        self.layout = {}
        for line in open(layout_jsonl, encoding="utf-8"):
            d = json.loads(line)
            self.layout[d["page_num"]] = d
        
        self.pdf_doc = None
        self.sx = self.sy = 0.5  # default DPI=2.0
        if pdf_path:
            import fitz
            self.pdf_doc = fitz.open(pdf_path)
            tp = self.pdf_doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            self.sx = self.pdf_doc[0].rect.width / tp.width
            self.sy = self.pdf_doc[0].rect.height / tp.height
        
        self.chunks = []
        self.section_num = 0
        self.text_seq = 0
        self.table_seq = 0
        
        self.cur_section = ""
        self.cur_section_pages = []
        self.cur_text = []
        self.cur_table = None
        self.cur_table_pages = []
    
    def run(self):
        pages = sorted(self.layout.keys())
        for pn in pages:
            self._process_page(pn)
        self._flush_text()
        self._flush_table()
        return self.chunks
    
    def _extract_title_from_md(self, content):
        for line in content.split("\n"):
            s = line.strip()
            if s and not s.startswith("---") and not s.startswith("|") and not s.startswith("!"):
                return s[:120]
        return ""
    
    def _get_title_from_pdf(self, pn):
        import fitz
        if not self.pdf_doc:
            return None
        blocks = self.layout.get(pn, {}).get("blocks", [])
        for blk in blocks:
            if blk["label"] in ("Title","SectionHeader"):
                b = blk["bbox"]
                r = fitz.Rect(b[0]*self.sx, b[1]*self.sy, b[2]*self.sx, b[3]*self.sy)
                title = self.pdf_doc[pn-1].get_text("text", clip=r).strip()
                if title:
                    return title
        return None

    def _process_page(self, pn):
        md_file = self.md_dir / f"page_{pn:05d}.md"
        if not md_file.exists():
            return
        content = md_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        
        layout_blocks = self.layout.get(pn, {}).get("blocks", [])
        has_new_section = any(b["label"] in ("Title","SectionHeader") for b in layout_blocks)
        
        page_tables = []
        
        if has_new_section:
            title = self._get_title_from_pdf(pn) if self.pdf_doc else None
            if not title:
                for line in lines:
                    if line.startswith("## "):
                        title = line[3:].strip()
                        break
            if not title:
                title = self._extract_title_from_md(content)
            if title and title != self.cur_section:
                if self.cur_section:
                    self._flush_text()
                    self._flush_table()
                self.cur_section = title
                self.section_num += 1
                self.text_seq = 0
                self.table_seq = 0
        
        for line in lines:
            if line.startswith("--- PAGE") or line.startswith("---"):
                continue
            if line.startswith("|") and line.endswith("|") and not line.startswith("|---"):
                page_tables.append(line)
                continue
            if line.startswith("|---"):
                continue
            if line.strip():
                self._add_text(line.strip(), pn)
        
        if page_tables:
            self._flush_text()
            cols = count_cols("\n".join(page_tables[:2]))
            if self.cur_table and self.cur_table["cols"] == cols and not has_new_section:
                self.cur_table["lines"].extend(page_tables)
                self.cur_table_pages.append(pn)
            else:
                self._flush_table()
                self.cur_table = {"lines": page_tables, "cols": cols}
                self.cur_table_pages = [pn]
    
    def _add_text(self, text, pn):
        self.cur_text.append((text, pn))
        if pn not in self.cur_section_pages:
            self.cur_section_pages.append(pn)
    
    def _flush_text(self):
        if not self.cur_text:
            return
        self.text_seq += 1
        combined = "\n".join(t for t, p in self.cur_text)
        section_path = self.cur_section or "__front_matter__"
        tags = extract_material_tags(combined, section_path)
        
        chunk = {
            "chunk_id": f"{self.prefix}_s{self.section_num:03d}_text_{self.text_seq:03d}",
            "type": "text",
            "section_path": section_path,
            "content": combined,
            "pages": sorted(set(p for t, p in self.cur_text)),
            "tokens": count_tokens(combined),
            "material_tags": tags,
            "source": self.source_name,
        }
        self.chunks.append(chunk)
        self.cur_text = []
    
    def _flush_table(self):
        if not self.cur_table:
            return
        self.table_seq += 1
        table_text = "\n".join(self.cur_table["lines"])
        section_path = self.cur_section or "__front_matter__"
        tags = extract_material_tags(table_text, section_path)
        
        # Extract table header
        first = self.cur_table["lines"][0] if self.cur_table["lines"] else ""
        header = [c.strip() for c in first.split("|")[1:-1]] if first else []
        
        chunk = {
            "chunk_id": f"{self.prefix}_s{self.section_num:03d}_t{self.table_seq:03d}",
            "type": "table",
            "section_path": section_path,
            "content": table_text,
            "pages": sorted(set(self.cur_table_pages)),
            "tokens": count_tokens(table_text),
            "table_shape": f"{len(self.cur_table['lines']) - 1}x{self.cur_table['cols']}",
            "table_header": header,
            "material_tags": tags,
            "source": self.source_name,
        }
        self.chunks.append(chunk)
        self.cur_table = None
        self.cur_table_pages = []

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--md-dir", required=True)
    p.add_argument("--layout", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--pdf", help="PDF for accurate section title extraction")
    p.add_argument("--output", help="Output JSONL path (default: stdout)")
    p.add_argument("--embed", action="store_true", help="Generate embeddings")
    p.add_argument("--db", action="store_true", help="Insert to PostgreSQL")
    args = p.parse_args()
    
    t0 = time.time()
    chunker = LayoutChunker(args.md_dir, args.layout, args.source, pdf_path=args.pdf)
    chunks = chunker.run()
    
    out_lines = [json.dumps(c, ensure_ascii=False) for c in chunks]
    
    if args.output:
        Path(args.output).write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    
    # Stats
    sec = time.time() - t0
    types = {}
    for c in chunks:
        types[c["type"]] = types.get(c["type"], 0) + 1
    total_tokens = sum(c["tokens"] for c in chunks)
    
    print(f"\n=== Layout Chunker Results ===")
    print(f"Source: {args.source}")
    print(f"Total chunks: {len(chunks)}")
    for t, n in sorted(types.items()):
        print(f"  {t}: {n}")
    print(f"Total tokens: {total_tokens}")
    print(f"Avg tokens/chunk: {total_tokens//max(len(chunks),1)}")
    print(f"Time: {sec:.1f}s")
    
    if args.output:
        print(f"Output: {args.output} ({len(out_lines)} lines)")
    
    # DB insertion
    if args.db:
        print("\nDB insertion not yet implemented (pipe JSONL to ingest script)")

if __name__ == "__main__":
    main()
