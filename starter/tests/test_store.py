"""Needs the Docker Postgres from docker-compose.yml (DATABASE_URL or the local default)."""
import os
import uuid

import psycopg
import pytest
from src.models import Chunk
from src.store import PgVectorStore

URL = os.environ.get("DATABASE_URL", "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab")
DIM = 1024


def vec(*head):
    """Sparse test vector: given leading coordinates, zero elsewhere."""
    return list(head) + [0.0] * (DIM - len(head))


def chunk(cid, text="t", section="PHAN_1", page=1):
    return Chunk(cid, "5481", "5481.docx", page, text, {"section": section, "unit_id": "5481-U001"})


@pytest.fixture
def store():
    s = PgVectorStore(URL, DIM)
    s.create_schema()
    yield s


@pytest.fixture
def strategy():
    name = f"T-{uuid.uuid4().hex[:8]}"
    yield name
    with psycopg.connect(URL) as conn:
        conn.execute("DELETE FROM chunks WHERE strategy = %s", (name,))


def test_upsert_twice_no_duplicates(store, strategy):
    chunks = [chunk("c1"), chunk("c2")]
    vectors = [vec(1.0), vec(0.0, 1.0)]
    store.upsert(strategy, chunks, vectors)
    store.upsert(strategy, chunks, vectors)
    assert store.count(strategy) == 2


def test_upsert_removes_obsolete_chunks(store, strategy):
    store.upsert(strategy, [chunk("c1"), chunk("c2")], [vec(1.0), vec(0.0, 1.0)])
    store.upsert(strategy, [chunk("c1", "new text")], [vec(1.0)])
    assert store.count(strategy) == 1
    assert store.search(strategy, vec(1.0))[0]["text"] == "new text"


def test_search_orders_by_cosine(store, strategy):
    store.upsert(strategy, [chunk("near"), chunk("mid"), chunk("far")],
                 [vec(1.0, 0.1), vec(1.0, 1.0), vec(-1.0)])
    hits = store.search(strategy, vec(1.0), top_k=3)
    assert [h["chunk_id"] for h in hits] == ["near", "mid", "far"]
    assert hits[0]["score"] > hits[1]["score"] > hits[2]["score"]
    assert hits[2]["score"] == pytest.approx(-1.0, abs=1e-6)
    assert {"chunk_id", "text", "score", "document_id", "source", "page", "metadata"} <= set(hits[0])
    assert hits[0]["metadata"]["section"] == "PHAN_1"


def test_search_respects_top_k(store, strategy):
    store.upsert(strategy, [chunk(f"c{i}") for i in range(5)], [vec(1.0, i) for i in range(5)])
    assert len(store.search(strategy, vec(1.0), top_k=2)) == 2


def test_filter_only_returns_section(store, strategy):
    store.upsert(strategy, [chunk("a", section="PHAN_1"), chunk("b", section="PHAN_2")],
                 [vec(1.0), vec(1.0, 0.1)])
    hits = store.search(strategy, vec(1.0), filters={"section": "PHAN_2"})
    assert [h["chunk_id"] for h in hits] == ["b"]


def test_unknown_section_returns_empty(store, strategy):
    store.upsert(strategy, [chunk("a")], [vec(1.0)])
    assert store.search(strategy, vec(1.0), filters={"section": "PHAN_99"}) == []


def test_sql_injection_value_is_inert(store, strategy):
    store.upsert(strategy, [chunk("a")], [vec(1.0)])
    assert store.search(strategy, vec(1.0), filters={"section": "x'; DROP TABLE chunks;--"}) == []
    assert store.count(strategy) == 1                       # table still there


def test_filter_key_not_allowed(store, strategy):
    with pytest.raises(ValueError):
        store.search(strategy, vec(1.0), filters={"text; DROP TABLE chunks": "x"})


def test_strategies_are_isolated(store, strategy):
    other = strategy + "x"
    try:
        store.upsert(strategy, [chunk("a")], [vec(1.0)])
        store.upsert(other, [chunk("b")], [vec(1.0)])
        assert [h["chunk_id"] for h in store.search(strategy, vec(1.0))] == ["a"]
    finally:
        with psycopg.connect(URL) as conn:
            conn.execute("DELETE FROM chunks WHERE strategy = %s", (other,))


def test_dimension_mismatch_raises(store, strategy):
    with pytest.raises(ValueError):
        store.upsert(strategy, [chunk("a")], [[1.0, 0.0, 0.0]])
    with pytest.raises(ValueError):
        store.upsert(strategy, [chunk("a"), chunk("b")], [vec(1.0)])    # count mismatch
    with pytest.raises(ValueError):
        store.search(strategy, [1.0, 0.0])
    assert store.count(strategy) == 0


def test_unreachable_db_raises():
    bad = PgVectorStore("postgresql://x:y@127.0.0.1:1/none", DIM)
    with pytest.raises(RuntimeError):
        bad.create_schema()
