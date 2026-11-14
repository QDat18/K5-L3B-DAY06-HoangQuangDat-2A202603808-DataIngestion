"""Tests for docx loading and text normalization (plan Task 1)."""
from pathlib import Path

import pytest
from docx import Document

from src.ingestion import load_docx, normalize_text


# ---- normalize_text -------------------------------------------------------

def test_normalize_nfc_equals_precomposed():
    # "e" + combining circumflex must become the single character "ê"
    assert normalize_text("ê") == "ê"


def test_normalize_collapses_spaces_keeps_newline():
    assert normalize_text("a   b\nc") == "a b\nc"


def test_normalize_zero_width_becomes_space():
    assert normalize_text("a​b") == "a b"


# ---- load_docx ------------------------------------------------------------

@pytest.fixture
def docx_path(tmp_path: Path):
    def _make(build) -> Path:
        doc = Document()
        build(doc)
        p = tmp_path / "t.docx"
        doc.save(p)
        return p
    return _make


def test_load_docx_keeps_order_and_flattens_table(docx_path):
    def build(doc):
        doc.add_paragraph("Trước")
        t = doc.add_table(rows=2, cols=2)
        t.rows[0].cells[0].text = "STT"
        t.rows[0].cells[1].text = "Tên thuốc"
        t.rows[1].cells[0].text = "1"
        t.rows[1].cells[1].text = "Metformin"
        doc.add_paragraph("Sau")

    blocks = load_docx(docx_path(build))

    assert [b.kind for b in blocks] == ["p", "table", "p"]
    assert [b.index for b in blocks] == [0, 1, 2]
    assert blocks[1].text == "STT: 1; Tên thuốc: Metformin"


def test_load_docx_skips_empty_cells(docx_path):
    def build(doc):
        t = doc.add_table(rows=2, cols=3)
        for i, h in enumerate(["STT", "Tên thuốc", "Ghi chú"]):
            t.rows[0].cells[i].text = h
        t.rows[1].cells[0].text = "1"
        t.rows[1].cells[1].text = "Metformin"
        t.rows[1].cells[2].text = ""

    (table,) = load_docx(docx_path(build))

    assert table.text == "STT: 1; Tên thuốc: Metformin"
    assert "Ghi chú" not in table.text


def test_load_docx_merged_cell_value_not_duplicated(docx_path):
    def build(doc):
        t = doc.add_table(rows=2, cols=3)
        for i, h in enumerate(["A", "B", "C"]):
            t.rows[0].cells[i].text = h
        merged = t.rows[1].cells[0].merge(t.rows[1].cells[1])
        merged.text = "X"
        t.rows[1].cells[2].text = "Y"

    (table,) = load_docx(docx_path(build))

    assert table.text == "A: X; C: Y"


def test_load_docx_skips_empty_paragraphs(docx_path):
    def build(doc):
        doc.add_paragraph("Một")
        doc.add_paragraph("   ")
        doc.add_paragraph("Hai")

    blocks = load_docx(docx_path(build))

    assert [b.text for b in blocks] == ["Một", "Hai"]
    assert [b.index for b in blocks] == [0, 1]


def test_load_docx_normalizes_text(docx_path):
    def build(doc):
        doc.add_paragraph("ê x")

    (block,) = load_docx(docx_path(build))

    assert block.text == "ê x"


def test_skipped_empty_blocks_reports_position_and_kind(tmp_path):
    from docx import Document
    from src.ingestion import skipped_empty_blocks
    d = Document()
    d.add_paragraph("a")
    d.add_paragraph("")
    d.add_paragraph("b")
    path = tmp_path / "t.docx"
    d.save(str(path))
    assert skipped_empty_blocks(path) == [(1, "p")]
