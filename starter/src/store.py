"""Store and search vectors using PostgreSQL + pgvector (exact cosine search)."""
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Chunk

_ALLOWED_FILTERS = {"section"}


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> psycopg.Connection:
        try:
            return psycopg.connect(self.database_url, connect_timeout=5)
        except psycopg.Error as exc:
            raise RuntimeError(f"cannot connect to the vector database: {exc}") from exc

    def _check_vector(self, vector: list[float], what: str) -> None:
        if len(vector) != self.dimensions:
            raise ValueError(f"{what} has {len(vector)} dimensions, expected {self.dimensions}")

    def create_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS chunks (
                        strategy    text    NOT NULL,
                        chunk_id    text    NOT NULL,
                        document_id text    NOT NULL,
                        source      text    NOT NULL,
                        page        integer NOT NULL,
                        section     text,
                        text        text    NOT NULL,
                        metadata    jsonb   NOT NULL DEFAULT '{{}}',
                        embedding   vector({self.dimensions}) NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )""")
                conn.execute("CREATE INDEX IF NOT EXISTS chunks_strategy_section "
                             "ON chunks (strategy, section)")
        except psycopg.Error as exc:
            raise RuntimeError(f"create_schema failed: {exc}") from exc

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace the whole chunk set of `strategy` (stale chunks are removed)."""
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        ids = [c.chunk_id for c in chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate chunk_id in one upsert")
        for c, v in zip(chunks, vectors):
            self._check_vector(v, f"vector for {c.chunk_id}")
        try:
            with self._connect() as conn:       # one transaction: all or nothing
                conn.execute("DELETE FROM chunks WHERE strategy = %s AND chunk_id <> ALL(%s)",
                             (strategy, ids))
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO chunks (strategy, chunk_id, document_id, source, page,
                                               section, text, metadata, embedding)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                           ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                               document_id = EXCLUDED.document_id, source = EXCLUDED.source,
                               page = EXCLUDED.page, section = EXCLUDED.section,
                               text = EXCLUDED.text, metadata = EXCLUDED.metadata,
                               embedding = EXCLUDED.embedding""",
                        [(strategy, c.chunk_id, c.document_id, c.source, c.page,
                          c.metadata.get("section"), c.text, Jsonb(c.metadata), _literal(v))
                         for c, v in zip(chunks, vectors)])
        except psycopg.Error as exc:
            raise RuntimeError(f"upsert failed: {exc}") from exc

    def count(self, strategy: str) -> int:
        try:
            with self._connect() as conn:
                return conn.execute("SELECT count(*) FROM chunks WHERE strategy = %s",
                                    (strategy,)).fetchone()[0]
        except psycopg.Error as exc:
            raise RuntimeError(f"count failed: {exc}") from exc

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Top-k by cosine distance; only the `section` filter is allowed, always parameterized."""
        if top_k <= 0:
            raise ValueError("top_k must be > 0")
        self._check_vector(query_vector, "query vector")
        filters = filters or {}
        unknown = set(filters) - _ALLOWED_FILTERS
        if unknown:
            raise ValueError(f"filter not allowed: {sorted(unknown)}")
        sql = ("SELECT chunk_id, text, 1 - (embedding <=> %s::vector) AS score, "
               "document_id, source, page, metadata FROM chunks WHERE strategy = %s")
        params: list[Any] = [_literal(query_vector), strategy]
        if filters.get("section") is not None:
            if not isinstance(filters["section"], str):
                raise ValueError("section filter must be a string")
            sql += " AND section = %s"
            params.append(filters["section"])
        sql += " ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s"
        params += [_literal(query_vector), top_k]
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except psycopg.Error as exc:
            raise RuntimeError(f"search failed: {exc}") from exc
        return [{"chunk_id": r[0], "text": r[1], "score": float(r[2]), "document_id": r[3],
                 "source": r[4], "page": r[5], "metadata": r[6]} for r in rows]
