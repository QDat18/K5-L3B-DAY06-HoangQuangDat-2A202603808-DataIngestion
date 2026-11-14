"""Read and normalize source data. TODO: implement functions."""
import re
import unicodedata
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .models import Block, DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    raise NotImplementedError("TODO: load_pdf")


def load_docx(path: Path) -> list[Block]:
    """Read paragraphs and tables of a .docx in body order (see plan Task 1).

    Tables are flattened to "<header>: <value>; ..." lines. Empty blocks are
    skipped, so Block.index counts the blocks that were kept.
    """
    doc = Document(str(path))
    blocks: list[Block] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            kind, text = "p", normalize_text(Paragraph(child, doc).text)
        elif child.tag == qn("w:tbl"):
            kind, text = "table", _flatten_table(Table(child, doc))
        else:
            continue
        if text:
            blocks.append(Block(kind=kind, text=text, index=len(blocks)))
    return blocks


def _flatten_table(table: Table) -> str:
    """First row = column names; each later row becomes one "name: value" line."""
    rows = table.rows
    if not rows:
        return ""
    headers = [normalize_text(c.text) for c in rows[0].cells]
    lines = []
    for row in rows[1:]:
        seen: set[int] = set()
        pairs = []
        for col, cell in enumerate(row.cells):
            if id(cell._tc) in seen:  # merged cell is returned once per column
                continue
            seen.add(id(cell._tc))
            value = normalize_text(cell.text)
            if not value:
                continue
            pairs.append(f"{headers[col]}: {value}" if headers[col] else value)
        if pairs:
            lines.append("; ".join(pairs))
    return "\n".join(lines)


def normalize_text(text: str) -> str:
    """NFC; NBSP/zero-width -> space; collapse spaces; keep newlines."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub("[ ​‌‍﻿]", " ", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return text.strip()


def skipped_empty_blocks(path: Path) -> list[tuple[int, str]]:
    """(position in the docx body, kind) of every paragraph/table that `load_docx` drops as empty."""
    doc = Document(str(path))
    skipped: list[tuple[int, str]] = []
    pos = -1
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            kind, text = "p", normalize_text(Paragraph(child, doc).text)
        elif child.tag == qn("w:tbl"):
            kind, text = "table", _flatten_table(Table(child, doc))
        else:
            continue
        pos += 1
        if not text:
            skipped.append((pos, kind))
    return skipped
