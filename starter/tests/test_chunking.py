import pytest
from src.chunking import by_paragraph, fixed_size_corpus
from src.models import DocumentPage


def unit(n, text, section="PHAN_1"):
    return DocumentPage("5481", "5481_QD-BYT_460925.docx", n, text,
                        {"section": section, "unit_id": f"5481-U{n:03d}",
                         "chars": len(text), "short": False})


# ---- A ----
def test_fixed_size_len_and_overlap():
    chunks = fixed_size_corpus([unit(1, "a" * 400), unit(2, "b" * 400), unit(3, "c" * 400)])
    assert all(len(c.text) <= 500 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev.text[-50:] == nxt.text[:50]


def test_fixed_size_covers_all_text():
    units = [unit(1, "a" * 400), unit(2, "b" * 400), unit(3, "c" * 400)]
    chunks = fixed_size_corpus(units)
    rebuilt = chunks[0].text + "".join(c.text[50:] for c in chunks[1:])
    assert rebuilt == "\n".join(u.text for u in units)


def test_fixed_size_page_is_start_unit():
    units = [unit(1, "a" * 400, "PHAN_1"), unit(2, "b" * 400, "PHAN_2"), unit(3, "c" * 400, "PHAN_3")]
    chunks = fixed_size_corpus(units)
    assert [c.page for c in chunks] == [1, 2, 3]            # starts at 0, 450, 900
    assert [c.metadata["section"] for c in chunks] == ["PHAN_1", "PHAN_2", "PHAN_3"]


def test_fixed_size_rejects_bad_overlap():
    with pytest.raises(ValueError):
        fixed_size_corpus([unit(1, "a" * 100)], size=50, overlap=50)


# ---- B ----
def test_by_paragraph_respects_max_size():
    paras = [f"p{i} " + "x" * 98 for i in range(10)]
    chunks = by_paragraph(unit(1, "\n".join(paras)), max_size=300)
    assert all(len(c.text) <= 300 for c in chunks)
    assert "\n".join(c.text for c in chunks) == "\n".join(paras)   # nothing lost or reordered


def test_by_paragraph_splits_oversized_on_sentence():
    s1, s2, s3 = "A" * 60 + ".", "B" * 60 + ".", "C" * 60 + "."
    chunks = by_paragraph(unit(1, " ".join([s1, s2, s3])), max_size=100)
    assert [c.text for c in chunks] == [s1, s2, s3]


def test_by_paragraph_hard_cuts_a_sentence_longer_than_max():
    chunks = by_paragraph(unit(1, "x" * 250), max_size=100)
    assert [len(c.text) for c in chunks] == [100, 100, 50]


def test_by_paragraph_never_crosses_unit():
    u = unit(2, "một\nhai\nba", "PHAN_4")
    chunks = by_paragraph(u, max_size=800)
    assert all(c.page == 2 and c.metadata["unit_id"] == "5481-U002"
               and c.metadata["section"] == "PHAN_4" for c in chunks)


# ---- IDs ----
def test_chunk_ids_stable_and_unique():
    units = [unit(1, "a" * 400), unit(2, "b" * 400), unit(3, "c" * 400)]
    first, second = fixed_size_corpus(units), fixed_size_corpus(units)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.chunk_id for c in first][0] == "A-5481-U001-001"
    ids = [c.chunk_id for c in first] + [c.chunk_id for c in by_paragraph(units[0])]
    assert len(ids) == len(set(ids))
