"""Implement fixed-size and structure-aware chunking."""
import re
from bisect import bisect_right

from .models import Chunk, DocumentPage

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _meta(unit: DocumentPage) -> dict:
    return {"section": unit.metadata["section"], "unit_id": unit.metadata["unit_id"]}


def _make(strategy: str, unit: DocumentPage, n: int, text: str) -> Chunk:
    meta = _meta(unit)
    return Chunk(f"{strategy}-{meta['unit_id']}-{n:03d}", unit.document_id,
                 unit.source, unit.page, text, meta)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Overlapping windows over one unit; every chunk keeps the unit's metadata."""
    return fixed_size_corpus([page], size, overlap)


def fixed_size_corpus(units: list[DocumentPage], size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Cut the concatenated corpus (units joined by "\\n") into overlapping windows.

    A chunk belongs to the unit in which it starts.
    """
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("need size > 0 and 0 <= overlap < size")
    if not units:
        return []
    text = "\n".join(u.text for u in units)
    starts, pos = [], 0
    for u in units:
        starts.append(pos)
        pos += len(u.text) + 1
    step = size - overlap
    counters: dict[str, int] = {}
    chunks: list[Chunk] = []
    s = 0
    while True:
        unit = units[bisect_right(starts, s) - 1]
        uid = unit.metadata["unit_id"]
        counters[uid] = counters.get(uid, 0) + 1
        chunks.append(_make("A", unit, counters[uid], text[s:s + size]))
        if s + size >= len(text):
            break
        s += step
    return chunks


def _pieces(paragraph: str, max_size: int) -> list[tuple[str, str]]:
    """(text, separator-before) pieces, each <= max_size."""
    if len(paragraph) <= max_size:
        return [(paragraph, "\n")]
    out: list[tuple[str, str]] = []
    for sentence in _SENTENCE_END.split(paragraph):
        if not sentence:
            continue
        sep = " "
        for i in range(0, len(sentence), max_size):
            out.append((sentence[i:i + max_size], sep))
            sep = ""
    out[0] = (out[0][0], "\n")
    return out


def by_paragraph(page: DocumentPage, max_size: int = 800) -> list[Chunk]:
    """Pack whole paragraphs up to max_size; split oversized ones on sentences, then hard-cut."""
    if max_size <= 0:
        raise ValueError("max_size must be > 0")
    pieces: list[tuple[str, str]] = []
    for paragraph in page.text.split("\n"):
        if paragraph.strip():
            pieces.extend(_pieces(paragraph, max_size))
    texts: list[str] = []
    current = ""
    for text, sep in pieces:
        if current and len(current) + len(sep) + len(text) <= max_size:
            current += sep + text
        else:
            if current:
                texts.append(current)
            current = text
    if current:
        texts.append(current)
    return [_make("B", page, n, t) for n, t in enumerate(texts, 1)]
