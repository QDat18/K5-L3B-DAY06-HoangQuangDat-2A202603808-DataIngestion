"""Tests for rule-based cleaning and section assignment (plan Task 2)."""
import pytest

from src.cleaning import clean
from src.models import Block


def blocks(*items: tuple[str, str]) -> list[Block]:
    return [Block(kind=k, text=t, index=i) for i, (k, t) in enumerate(items)]


def p(text: str) -> tuple[str, str]:
    return ("p", text)


def test_drops_head_before_phan_1():
    result = clean(blocks(
        p("QUYẾT ĐỊNH"), p("LỜI NÓI ĐẦU"),
        p("PHẦN 1"), p("ĐỊNH NGHĨA"), p("nội dung"),
        p("TÀI LIỆU THAM KHẢO"), p("1. ADA 2020"),
    ))

    assert [s.section for s in result.sections] == ["PHAN_1"]
    assert result.sections[0].paragraphs == ["ĐỊNH NGHĨA", "nội dung"]


def test_stops_at_first_tai_lieu_tham_khao():
    result = clean(blocks(
        p("PHẦN 1"), p("a"),
        p("PHẦN 2"), p("b"),
        p("TÀI LIỆU THAM KHẢO"), p("1. ADA 2020"),
        p("PHẦN 3"), p("mục lục lặp"),
        p("TÀI LIỆU THAM KHẢO"),
    ))

    assert [s.section for s in result.sections] == ["PHAN_1", "PHAN_2"]
    assert result.sections[1].paragraphs == ["b"]


def test_section_ids_phan_and_phu_luc():
    result = clean(blocks(
        p("PHẦN 1"), p("a"),
        p("PHẦN 2"), p("b"),
        p("PHẦN 10"), p("c"),
        p("PHỤ LỤC 01"), p("d"),
        p("PHỤ LỤC 03"), p("e"),
        p("TÀI LIỆU THAM KHẢO"),
    ))

    assert [s.section for s in result.sections] == [
        "PHAN_1", "PHAN_2", "PHAN_10", "PHU_LUC_01", "PHU_LUC_03",
    ]


def test_phan_inside_sentence_is_not_boundary():
    result = clean(blocks(
        p("PHẦN 1"), p("a"),
        p("Xem PHẦN 4 để biết thêm"),
        p("TÀI LIỆU THAM KHẢO"),
    ))

    assert [s.section for s in result.sections] == ["PHAN_1"]
    assert "Xem PHẦN 4 để biết thêm" in result.sections[0].paragraphs


def test_table_text_is_never_a_section_boundary():
    result = clean(blocks(
        p("PHẦN 1"), p("a"),
        ("table", "PHẦN 5"),
        p("TÀI LIỆU THAM KHẢO"),
    ))

    assert [s.section for s in result.sections] == ["PHAN_1"]


def test_table_rows_become_separate_paragraphs():
    result = clean(blocks(
        p("PHẦN 1"),
        ("table", "Thuốc: A; Liều: 1\nThuốc: B; Liều: 2"),
        p("TÀI LIỆU THAM KHẢO"),
    ))

    assert result.sections[0].paragraphs == ["Thuốc: A; Liều: 1", "Thuốc: B; Liều: 2"]


def test_dropped_ranges_recorded_with_reason():
    result = clean(blocks(
        p("QUYẾT ĐỊNH"),        # 0
        p("LỜI NÓI ĐẦU"),       # 1
        p("PHẦN 1"),            # 2
        p("nội dung"),          # 3
        p("TÀI LIỆU THAM KHẢO"),  # 4
        p("1. ADA 2020"),       # 5
    ))

    head, tail = result.dropped
    assert (head.start, head.end) == (0, 1)
    assert head.chars == len("QUYẾT ĐỊNH") + len("LỜI NÓI ĐẦU")
    assert (tail.start, tail.end) == (4, 5)
    assert tail.chars == len("TÀI LIỆU THAM KHẢO") + len("1. ADA 2020")
    assert head.reason and tail.reason and head.reason != tail.reason


def test_missing_start_marker_raises():
    with pytest.raises(ValueError, match="PHẦN 1"):
        clean(blocks(p("QUYẾT ĐỊNH"), p("TÀI LIỆU THAM KHẢO")))


def test_missing_end_marker_raises():
    with pytest.raises(ValueError, match="TÀI LIỆU THAM KHẢO"):
        clean(blocks(p("PHẦN 1"), p("a")))
