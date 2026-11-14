import csv

import pytest
from src.audit import make_audit_samples, summarize_labels
from src.models import Chunk, DocumentPage


def make_units(n=12):
    return [DocumentPage("5481", "5481.docx", i, f"text {i}",
                         {"section": "PHAN_1" if i < 6 else "PHAN_2", "unit_id": f"5481-U{i:03d}",
                          "chars": 6, "short": False}) for i in range(1, n + 1)]


def make_chunks(prefix, n=12, per_unit=2):
    return [Chunk(f"{prefix}-5481-U{u:03d}-{k:03d}", "5481", "5481.docx", u, f"chunk {prefix} {u} {k}",
                  {"section": "PHAN_1" if u < 6 else "PHAN_2", "unit_id": f"5481-U{u:03d}"})
            for u in range(1, n + 1) for k in range(1, per_unit + 1)]


def make_traces(strategies=("A", "B", "C"), n_questions=5):
    traces = []
    for s in strategies:
        for q in range(1, n_questions + 1):
            traces.append({
                "strategy": s, "id": f"q{q:02d}", "split": "test", "question": f"question {q}?",
                "filter": {"section": "PHAN_2"} if q == 1 else None, "gold_page": q, "evidence_quote": "ev",
                "hits": [{"chunk_id": f"{'A' if s == 'A' else 'B'}-5481-U{q + r:03d}-001", "text": f"hit {r}",
                          "score": 0.5, "document_id": "5481", "source": "5481.docx", "page": q + r,
                          "metadata": {"section": "PHAN_1" if q + r < 6 else "PHAN_2",
                                       "unit_id": f"5481-U{q + r:03d}"}} for r in range(3)]})
    return traces


@pytest.fixture
def out(tmp_path):
    chunks = {"A": make_chunks("A"), "B": make_chunks("B"), "C": make_chunks("B")}
    questions = [{"id": f"q{q:02d}", "expected_answer": f"answer {q}"} for q in range(1, 6)]
    make_audit_samples(make_units(), chunks, make_traces(), tmp_path, questions=questions)
    return tmp_path


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_coherence_uses_first_10_sorted_unit_ids_same_for_all_strategies(out):
    rows = read(out / "audit_coherence.csv")
    expected = [f"5481-U{i:03d}" for i in range(1, 11)]
    for s in "ABC":
        assert [r["unit_id"] for r in rows if r["strategy"] == s] == expected
    assert len(rows) == 30


def test_audit_label_columns_are_empty(out):
    for name in ("audit_coherence.csv", "audit_metadata.csv", "audit_grounding.csv"):
        rows = read(out / name)
        assert rows and all(r["label"] == "" and r["reason"] == "" for r in rows), name


def test_metadata_sample_is_5_test_questions_times_3(out):
    rows = read(out / "audit_metadata.csv")
    for s in "ABC":
        mine = [r for r in rows if r["strategy"] == s]
        assert len(mine) == 15 and len({r["question_id"] for r in mine}) == 5
    r = rows[0]                                   # original values to compare against are pre-filled
    assert r["expected_source"] == "5481.docx" and r["expected_section"] in ("PHAN_1", "PHAN_2")
    assert any(r["filter_requested"] == "PHAN_2" for r in rows)


def test_grounding_has_one_row_per_strategy_and_question_with_top3(out):
    rows = read(out / "audit_grounding.csv")
    assert len(rows) == 15
    r = rows[0]
    assert r["expected_answer"] == "answer 1" and r["top1_text"] == "hit 0" and r["top3_text"] == "hit 2"


def test_summarize_labels_mean_and_counts(tmp_path):
    p = tmp_path / "labels.csv"
    p.write_text("strategy,label,reason\nA,2,ok\nA,1,x\nA,,\nB,0,x\nB,2,ok\nB,2,ok\n", encoding="utf-8")
    s = summarize_labels(p)
    assert s["A"] == {"n": 3, "labeled": 2, "unlabeled": 1, "counts": {"0": 0, "1": 1, "2": 1}, "mean": 1.5}
    assert s["B"]["counts"] == {"0": 1, "1": 0, "2": 2} and s["B"]["mean"] == pytest.approx(4 / 3)
    p.write_text("strategy,label,reason\nA,5,bad\n", encoding="utf-8")
    with pytest.raises(ValueError):
        summarize_labels(p)
