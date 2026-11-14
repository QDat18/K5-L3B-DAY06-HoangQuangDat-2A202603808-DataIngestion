import json

import pytest
from src.models import DocumentPage
from src.run import run_pipeline
from src.store import PgVectorStore


class FakeEmbedder:
    model_name = "fake"
    dimensions = 4

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, question):
        return [1.0, 0.0, 0.0, 0.0]


class FakeStore:
    """Records every search so tests can inspect strategy and filters."""

    def __init__(self):
        self.upserts, self.searches = {}, []

    def create_schema(self):
        pass

    def upsert(self, strategy, chunks, vectors):
        self.upserts[strategy] = list(chunks)

    def count(self, strategy):
        return len(self.upserts.get(strategy, []))

    def search(self, strategy, query_vector, top_k=3, filters=None):
        self.searches.append((strategy, filters))
        return []


def units():
    text = "\n".join(f"Đoạn {i} " + "x" * 120 for i in range(20))
    return [DocumentPage("5481", "5481.docx", n, text,
                         {"section": "PHAN_4", "unit_id": f"5481-U{n:03d}", "chars": len(text), "short": False})
            for n in (1, 2)]


def questions():
    base = {"expected_answer": "a", "gold_source_id": "5481", "gold_page": 1,
            "evidence_quote": "Đoạn 0", "type": "t"}
    return [dict(base, id="q01", split="dev", question="no filter?", filter=None),
            dict(base, id="q02", split="dev", question="with filter?", filter={"section": "PHAN_4"}),
            dict(base, id="q03", split="test", question="test q", filter=None),
            dict(base, id="q04", split="test2", question="test2 q", filter={"section": "PHAN_4"})]


def test_strategy_c_filters_only_questions_with_filter(tmp_path):
    store = FakeStore()
    run_pipeline("dev", embedder=FakeEmbedder(), store=store, units=units(), questions=questions(),
                 out_dir=tmp_path)
    by_q = [(s, f) for s, f in store.searches]
    # per question the order is A, B, C
    assert by_q == [("A", None), ("B", None), ("B", None),
                    ("A", None), ("B", None), ("B", {"section": "PHAN_4"})]
    assert sorted(store.upserts) == ["A", "B"]        # C reuses B's vectors


def test_run_writes_traces_stats_and_metrics(tmp_path):
    run_pipeline("dev", embedder=FakeEmbedder(), store=FakeStore(), units=units(), questions=questions(),
                 out_dir=tmp_path)
    for s in "ABC":
        lines = (tmp_path / f"traces_{s}_dev.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2 and json.loads(lines[0])["strategy"] == s
    assert not (tmp_path / "traces_A_test.jsonl").exists()          # only the requested split
    stats = json.loads((tmp_path / "ingest_stats.json").read_text(encoding="utf-8"))
    assert stats["A"]["chunks"] > 0 and stats["B"]["chunks"] > 0 and stats["cost_usd"] == 0
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["summary"]["A"]["dev"]["hit3"] == [0, 2]


def test_test_split_is_run_only_once(tmp_path):
    kw = dict(embedder=FakeEmbedder(), units=units(), questions=questions(), out_dir=tmp_path)
    run_pipeline("test", store=FakeStore(), **kw)
    with pytest.raises(RuntimeError, match="test"):
        run_pipeline("test", store=FakeStore(), **kw)
    run_pipeline("test", store=FakeStore(), force_test=True, **kw)    # explicit, documented override


def test_run_aborts_loudly_when_db_down(tmp_path):
    bad = PgVectorStore("postgresql://x:y@127.0.0.1:1/none", 4)
    with pytest.raises(RuntimeError):
        run_pipeline("dev", embedder=FakeEmbedder(), store=bad, units=units(), questions=questions(),
                     out_dir=tmp_path)
    assert not list(tmp_path.glob("traces_*"))                     # no half-written results


def test_test2_runs_alone_once_and_is_summarised_with_test(tmp_path):
    kw = dict(embedder=FakeEmbedder(), units=units(), questions=questions(), out_dir=tmp_path)
    run_pipeline("test", store=FakeStore(), **kw)
    metrics = run_pipeline("test2", store=FakeStore(), **kw)          # test already on disk: allowed
    assert (tmp_path / "traces_C_test2.jsonl").exists()
    assert metrics["summary"]["A"]["test2"]["hit3"] == [0, 1]
    assert metrics["held_out"]["A"]["hit3"] == [0, 2]                  # test + test2 pooled
    with pytest.raises(RuntimeError, match="test2"):
        run_pipeline("test2", store=FakeStore(), **kw)
