"""Tests for source units and the corpus manifest (plan Task 3)."""
import json

import pytest

from src.cleaning import CleanResult, DroppedRange, SectionText
from src.manifest import validate_corpus, write_manifest
from src.models import DocumentPage
from src.units import build_units

MIN = 20  # small threshold so the tests stay readable


def result(*sections: tuple[str, list[str]]) -> CleanResult:
    return CleanResult(sections=[SectionText(s, paras) for s, paras in sections])


def test_units_at_least_min_chars_except_short_sections():
    units = build_units(result(
        ("PHAN_1", ["a" * 12] * 5),
        ("PHAN_2", ["x" * 5]),
    ), min_chars=MIN)

    for u in units:
        if not u.metadata["short"]:
            assert u.metadata["chars"] >= MIN
    assert [u.metadata["short"] for u in units if u.metadata["section"] == "PHAN_2"] == [True]


def test_units_never_cross_sections():
    units = build_units(result(
        ("PHAN_1", ["a" * 12] * 3),
        ("PHAN_2", ["b" * 12] * 3),
    ), min_chars=MIN)

    for u in units:
        letters = set(u.text.replace("\n", ""))
        assert letters == {"a"} if u.metadata["section"] == "PHAN_1" else letters == {"b"}


def test_leftover_merges_into_previous_unit_same_section():
    units = build_units(result(("PHAN_1", ["a" * 12, "b" * 12, "c" * 12])), min_chars=MIN)

    # first two paragraphs reach 25 chars and close a unit; "c" is a leftover
    assert len(units) == 1
    assert units[0].text == "\n".join(["a" * 12, "b" * 12, "c" * 12])
    assert units[0].metadata["chars"] == len(units[0].text)
    assert units[0].metadata["short"] is False


def test_no_text_lost_or_reordered():
    paras = [f"đoạn {i} " + "x" * 9 for i in range(11)]
    units = build_units(result(("PHAN_4", paras)), min_chars=MIN)

    assert "\n".join(u.text for u in units) == "\n".join(paras)


def test_short_section_becomes_single_short_unit():
    units = build_units(result(("PHU_LUC_03", ["abc", "def"])), min_chars=MIN)

    assert len(units) == 1
    assert units[0].text == "abc\ndef"
    assert units[0].metadata["short"] is True


def test_ids_sequential_and_stable_on_rerun():
    clean = result(("PHAN_1", ["a" * 12] * 6), ("PHAN_2", ["b" * 12] * 6))

    first = build_units(clean, min_chars=MIN)
    second = build_units(clean, min_chars=MIN)

    assert [u.page for u in first] == list(range(1, len(first) + 1))
    assert [u.metadata["unit_id"] for u in first] == [f"5481-U{i:03d}" for i in range(1, len(first) + 1)]
    assert first == second
    assert first[0].document_id == "5481"
    assert first[0].source == "5481_QD-BYT_460925.docx"


def _unit(i: int, short: bool) -> DocumentPage:
    return DocumentPage("5481", "f.docx", i, "t", {"unit_id": f"5481-U{i:03d}",
                                                     "section": "PHAN_1", "chars": 1500, "short": short})


def test_validate_corpus_raises_below_30():
    short_units = [_unit(100 + i, True) for i in range(5)]  # never count towards 30
    with pytest.raises(ValueError, match="30"):
        validate_corpus([_unit(i, False) for i in range(29)] + short_units)

    validate_corpus([_unit(i, False) for i in range(30)] + short_units)  # no error


def test_manifest_has_required_fields(tmp_path):
    units = build_units(result(("PHAN_1", ["a" * 12] * 3)), min_chars=MIN)
    dropped = [DroppedRange(reason="đầu tài liệu", start=0, end=4, chars=99)]
    out = tmp_path / "manifest.json"

    write_manifest(units, dropped, out, accessed_at="2026-11-14T10:00:00+07:00",
                   license_note="Văn bản hành chính công khai", sha256="abc123",
                   notes=["3 lưu đồ bị loại"])

    m = json.loads(out.read_text(encoding="utf-8"))
    doc = m["documents"][0]
    for key in ("source_id", "title", "source_path_or_url", "license_or_permission",
                "accessed_at", "sha256", "unit_ids", "chars", "page_counting_rule"):
        assert key in doc
    assert doc["source_id"] == "5481"
    assert doc["accessed_at"] == "2026-11-14T10:00:00+07:00"
    assert doc["unit_ids"] == [u.metadata["unit_id"] for u in units]
    assert doc["chars"] == sum(u.metadata["chars"] for u in units)
    assert m["units"][0].keys() >= {"unit_id", "page", "section", "chars", "short"}
    assert m["dropped_ranges"] == [{"reason": "đầu tài liệu", "start": 0, "end": 4, "chars": 99}]
    assert m["notes"] == ["3 lưu đồ bị loại"]
