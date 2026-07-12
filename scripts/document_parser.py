#!/usr/bin/env python3
"""Deterministic parsers for uploaded engineering documents.

The parser intentionally avoids LLM calls. It extracts the document's native
structure first so later semantic extraction can cite concrete blocks/tables.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

NS = {"w": W_NS, "r": R_NS, "rel": REL_NS, "a": A_NS}


def _qn(ns, name):
    return f"{{{ns}}}{name}"


def _attr(node, ns, name, default=None):
    if node is None:
        return default
    return node.attrib.get(_qn(ns, name), default)


def _decode_text_bytes(data):
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_zip_xml(docx, name):
    try:
        return ET.fromstring(docx.read(name))
    except Exception:
        return None


def _parse_styles(docx):
    root = _read_zip_xml(docx, "word/styles.xml")
    styles = {}
    if root is None:
        return styles
    for style in root.findall(".//w:style", NS):
        style_id = _attr(style, W_NS, "styleId", "")
        name_node = style.find("w:name", NS)
        name = _attr(name_node, W_NS, "val", "")
        if style_id:
            styles[style_id] = name or style_id
    return styles


def _parse_relationships(docx):
    root = _read_zip_xml(docx, "word/_rels/document.xml.rels")
    rels = {}
    if root is None:
        return rels
    for rel in root.findall("rel:Relationship", NS):
        rel_id = rel.attrib.get("Id")
        if not rel_id:
            continue
        rels[rel_id] = {
            "id": rel_id,
            "type": rel.attrib.get("Type", ""),
            "target": rel.attrib.get("Target", ""),
        }
    return rels


def _paragraph_text(paragraph):
    parts = []
    for node in paragraph.iter():
        if node.tag == _qn(W_NS, "t"):
            parts.append(node.text or "")
        elif node.tag == _qn(W_NS, "tab"):
            parts.append("\t")
        elif node.tag in (_qn(W_NS, "br"), _qn(W_NS, "cr")):
            parts.append("\n")
    return "".join(parts).strip()


def _paragraph_images(paragraph, rels):
    images = []
    for blip in paragraph.findall(".//a:blip", NS):
        rel_id = blip.attrib.get(_qn(R_NS, "embed")) or blip.attrib.get(_qn(R_NS, "link"))
        if not rel_id:
            continue
        rel = rels.get(rel_id, {})
        target = rel.get("target", "")
        images.append(
            {
                "relation_id": rel_id,
                "target": target,
                "filename": Path(target).name if target else "",
            }
        )
    return images


def _paragraph_meta(paragraph, styles):
    ppr = paragraph.find("w:pPr", NS)
    style_id = ""
    style_name = ""
    heading_level = None
    list_level = None
    list_id = None
    if ppr is not None:
        pstyle = ppr.find("w:pStyle", NS)
        style_id = _attr(pstyle, W_NS, "val", "") or ""
        style_name = styles.get(style_id, style_id)
        outline = ppr.find("w:outlineLvl", NS)
        outline_level = _safe_int(_attr(outline, W_NS, "val"))
        if outline_level is not None:
            heading_level = outline_level + 1
        numpr = ppr.find("w:numPr", NS)
        if numpr is not None:
            ilvl = numpr.find("w:ilvl", NS)
            numid = numpr.find("w:numId", NS)
            list_level = _safe_int(_attr(ilvl, W_NS, "val"), 0)
            list_id = _attr(numid, W_NS, "val", "")
    combined = f"{style_id} {style_name}".lower()
    if heading_level is None and ("heading" in combined or "标题" in combined):
        match = re.search(r"(\d+)", combined)
        heading_level = _safe_int(match.group(1), 1) if match else 1
    if heading_level is not None:
        heading_level = max(1, min(6, heading_level))
    return {
        "style_id": style_id,
        "style_name": style_name,
        "heading_level": heading_level,
        "list_level": list_level,
        "list_id": list_id,
    }


def _parse_paragraph(paragraph, styles, rels, index):
    text = _paragraph_text(paragraph)
    images = _paragraph_images(paragraph, rels)
    meta = _paragraph_meta(paragraph, styles)
    block_type = "paragraph"
    if meta["heading_level"] is not None:
        block_type = "heading"
    elif meta["list_id"]:
        block_type = "list_item"
    elif images and not text:
        block_type = "image"
    return {
        "index": index,
        "type": block_type,
        "text": text,
        "level": meta["heading_level"],
        "list_level": meta["list_level"],
        "list_id": meta["list_id"],
        "style_id": meta["style_id"],
        "style_name": meta["style_name"],
        "images": images,
    }


def _cell_text(cell):
    paragraphs = []
    for para in cell.findall(".//w:p", NS):
        text = _paragraph_text(para)
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs).strip()


def _parse_table(table, index):
    rows = []
    for tr in table.findall("w:tr", NS):
        parsed_row = []
        for tc in tr.findall("w:tc", NS):
            tcpr = tc.find("w:tcPr", NS)
            grid_span = 1
            v_merge = None
            if tcpr is not None:
                span_node = tcpr.find("w:gridSpan", NS)
                grid_span = _safe_int(_attr(span_node, W_NS, "val"), 1) or 1
                merge_node = tcpr.find("w:vMerge", NS)
                if merge_node is not None:
                    v_merge = _attr(merge_node, W_NS, "val", "continue") or "continue"
            parsed_row.append(
                {
                    "text": _cell_text(tc),
                    "grid_span": grid_span,
                    "v_merge": v_merge,
                }
            )
        if parsed_row:
            rows.append(parsed_row)
    row_text = [[cell["text"] for cell in row] for row in rows]
    non_empty_rows = [row for row in row_text if any(cell.strip() for cell in row)]
    headers = non_empty_rows[0] if len(non_empty_rows) > 1 else []
    return {
        "index": index,
        "type": "table",
        "rows": rows,
        "row_text": row_text,
        "headers": headers,
        "row_count": len(rows),
        "column_count": max((len(row) for row in rows), default=0),
    }


def _table_to_markdown(block):
    rows = block.get("row_text") or []
    rows = [row for row in rows if any(str(cell).strip() for cell in row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    lines = [
        "| " + " | ".join(str(cell).replace("\n", "<br>") for cell in normalized[0]) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(lines)


def _blocks_to_text(blocks):
    parts = []
    for block in blocks:
        if block["type"] == "table":
            table_text = []
            for row in block.get("row_text") or []:
                line = " | ".join(cell.strip() for cell in row if cell and cell.strip())
                if line:
                    table_text.append(line)
            if table_text:
                parts.append("\n".join(table_text))
            continue
        text = block.get("text", "")
        if text:
            parts.append(text)
    return "\n".join(parts)


def _blocks_to_markdown(blocks):
    parts = []
    for block in blocks:
        btype = block.get("type")
        text = block.get("text", "")
        if btype == "heading" and text:
            level = max(1, min(6, int(block.get("level") or 1)))
            parts.append(f"{'#' * level} {text}")
        elif btype == "list_item" and text:
            indent = "  " * int(block.get("list_level") or 0)
            parts.append(f"{indent}- {text}")
        elif btype == "table":
            md = _table_to_markdown(block)
            if md:
                parts.append(md)
        elif btype == "image":
            image_names = ", ".join(img.get("filename") or img.get("relation_id") for img in block.get("images") or [])
            parts.append(f"[图片：{image_names or '未命名图片'}]")
        elif text:
            parts.append(text)
    return "\n\n".join(parts)


def parse_docx(data, filename=""):
    try:
        docx = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        return {
            "parser": "docx_ooxml_v1",
            "parse_status": "failed",
            "error": str(exc),
            "text": "",
            "markdown": "",
            "blocks": [],
            "tables": [],
            "images": [],
            "outline": [],
        }
    with docx:
        document = _read_zip_xml(docx, "word/document.xml")
        if document is None:
            return {
                "parser": "docx_ooxml_v1",
                "parse_status": "failed",
                "error": "word/document.xml not found",
                "text": "",
                "markdown": "",
                "blocks": [],
                "tables": [],
                "images": [],
                "outline": [],
            }
        styles = _parse_styles(docx)
        rels = _parse_relationships(docx)
        body = document.find("w:body", NS)
        blocks = []
        tables = []
        images = []
        index = 0
        for child in list(body or []):
            if child.tag == _qn(W_NS, "p"):
                block = _parse_paragraph(child, styles, rels, index)
                if block["text"] or block["images"]:
                    blocks.append(block)
                    images.extend(block.get("images") or [])
                    index += 1
            elif child.tag == _qn(W_NS, "tbl"):
                block = _parse_table(child, index)
                blocks.append(block)
                tables.append(block)
                index += 1
    outline = [
        {
            "index": block["index"],
            "level": block.get("level") or 1,
            "text": block.get("text", ""),
        }
        for block in blocks
        if block.get("type") == "heading" and block.get("text")
    ]
    return {
        "parser": "docx_ooxml_v1",
        "parse_status": "parsed",
        "filename": filename,
        "text": _blocks_to_text(blocks),
        "markdown": _blocks_to_markdown(blocks),
        "blocks": blocks,
        "tables": tables,
        "images": images,
        "outline": outline,
        "statistics": {
            "block_count": len(blocks),
            "table_count": len(tables),
            "image_count": len(images),
            "heading_count": len(outline),
        },
    }


def parse_document(filename, data, mime_type=""):
    lower = str(filename or "").lower()
    if lower.endswith(".docx") or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return parse_docx(data, filename)
    if lower.endswith((".txt", ".md", ".markdown", ".csv")) or str(mime_type or "").startswith("text/"):
        text = _decode_text_bytes(data)
        return {
            "parser": "plain_text_v1",
            "parse_status": "parsed",
            "filename": filename,
            "text": text,
            "markdown": text,
            "blocks": [
                {"index": idx, "type": "paragraph", "text": line.strip()}
                for idx, line in enumerate(text.splitlines())
                if line.strip()
            ],
            "tables": [],
            "images": [],
            "outline": [],
            "statistics": {"block_count": len([line for line in text.splitlines() if line.strip()]), "table_count": 0, "image_count": 0, "heading_count": 0},
        }
    return {
        "parser": "stored_without_parser_v1",
        "parse_status": "stored",
        "filename": filename,
        "text": "",
        "markdown": "",
        "blocks": [],
        "tables": [],
        "images": [],
        "outline": [],
        "statistics": {"block_count": 0, "table_count": 0, "image_count": 0, "heading_count": 0},
    }
