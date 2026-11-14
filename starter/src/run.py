"""End-to-end pipeline: docx -> clean -> units -> chunks A/B -> embed -> pgvector -> A/B/C traces.

    python -m src.run --split dev     # tune on dev first
    python -m src.run --split test    # once, after the configuration is frozen
"""
import argparse
import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from .benchmark import load_questions
from .chunking import by_paragraph, fixed_size_corpus
from .cleaning import clean
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_docx, skipped_empty_blocks
from .manifest import validate_corpus, write_manifest
from .models import Chunk, DocumentPage
from .store import PgVectorStore
from .units import build_units

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "data" / "raw" / "5481_QD-BYT_460925.docx"
QUESTIONS = ROOT / "benchmark" / "questions.json"
QUESTIONS_TEST2 = ROOT / "benchmark" / "questions_test2.json"   # held-out set written after the first test run
MANIFEST = ROOT / "data" / "manifest.json"
RESULTS = ROOT / "results"
DEFAULT_DB = "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab"   # local Docker only
STRATEGIES = ("A", "B", "C")
SOURCE_URL = ("https://thuvienphapluat.vn/van-ban/The-thao-Y-te/Quyet-dinh-5481-QD-BYT-2020-tai-lieu-"
              "chuyen-mon-Huong-dan-chan-doan-dieu-tri-dai-thao-duong-tip-2-460925.aspx")


# ---------- building blocks ----------
def build_chunks(units: list[DocumentPage], max_size: int = 800) -> dict[str, list[Chunk]]:
    """A = fixed 500/50 over the joined corpus; B = paragraph chunks per unit (C reuses B)."""
    return {"A": fixed_size_corpus(units),
            "B": [c for u in units for c in by_paragraph(u, max_size)]}


def _length_stats(chunks: list[Chunk]) -> dict[str, Any]:
    lens = sorted(len(c.text) for c in chunks)
    p95 = lens[min(len(lens) - 1, int(0.95 * len(lens)))]
    return {"chunks": len(lens), "total_chars": sum(lens), "min": lens[0],
            "mean": round(statistics.fmean(lens), 1), "p50": statistics.median(lens),
            "p95": p95, "max": lens[-1]}


def ingest(store, embedder, chunks_by_strategy: dict[str, list[Chunk]],
           reingest_check: bool = False) -> dict[str, Any]:
    """Embed each chunk set once and replace the strategy's rows. Returns ingest stats."""
    stats: dict[str, Any] = {"model": embedder.model_name, "dimensions": embedder.dimensions,
                             "cost_usd": 0}
    for strategy, chunks in chunks_by_strategy.items():
        start = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in chunks])
        store.upsert(strategy, chunks, vectors)
        seconds = round(time.perf_counter() - start, 2)
        stats[strategy] = {**_length_stats(chunks), "ingest_seconds": seconds,
                           "rows_in_db": store.count(strategy)}
        if reingest_check:
            store.upsert(strategy, chunks, vectors)
            stats[strategy]["rows_after_reingest"] = store.count(strategy)
    return stats


def retrieve(store, strategy: str, question: dict, query_vector: list[float], top_k: int = 3):
    """A -> rows 'A'; B -> rows 'B'; C -> rows 'B' filtered by section ONLY when the question has one."""
    if strategy == "A":
        return store.search("A", query_vector, top_k)
    if strategy == "B":
        return store.search("B", query_vector, top_k)
    flt = question.get("filter")
    return store.search("B", query_vector, top_k, filters=dict(flt) if flt else None)


def _trace(strategy: str, question: dict, result: dict) -> dict:
    hits = [{k: h[k] for k in ("chunk_id", "text", "score", "document_id", "source", "page", "metadata")}
            for h in result["hits"]]
    return {"strategy": strategy, "id": question["id"], "split": question["split"],
            "type": question["type"], "question": question["question"], "filter": question["filter"],
            "gold_source_id": question["gold_source_id"], "gold_page": question["gold_page"],
            "evidence_quote": question["evidence_quote"],
            "hit1": result["hit1"], "hit3": result["hit3"], "rank": result["rank"], "hits": hits}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _read_traces(out_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for p in sorted(out_dir.glob("traces_*_*.jsonl")):
        rows += [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]
    return rows


def _compute_metrics(traces: list[dict]) -> dict[str, Any]:
    """Summary over every trace file on disk, plus the B-vs-C view on filter questions."""
    filt = [t for t in traces if t["filter"]]
    subset = summarize([t for t in filt if t["strategy"] in ("B", "C")])
    compliance: dict[str, list[int]] = {}
    for t in filt:
        want = t["filter"]["section"]
        ok = bool(t["hits"]) and all(h["metadata"].get("section") == want for h in t["hits"])
        cell = compliance.setdefault(t["strategy"], [0, 0])
        cell[0] += ok
        cell[1] += 1
    # held-out = the first test set plus test2, pooled (both were run once, never used to tune)
    pooled = [dict(t, split="held_out") for t in traces if t["split"] in ("test", "test2")]
    held_out = {s: v["held_out"] for s, v in summarize(pooled).items()} if pooled else {}
    return {"summary": summarize(traces), "held_out": held_out, "filter_questions": subset,
            "filter_compliance_top3": compliance}


# ---------- orchestration ----------
def run_pipeline(split: str, *, embedder, store, units: list[DocumentPage], questions: list[dict],
                 out_dir: Path, max_size: int = 800, force_test: bool = False,
                 reingest_check: bool = False) -> dict[str, Any]:
    """Ingest A/B, then run the chosen split(s) for A, B and C. Any backend error aborts."""
    if split not in ("dev", "test", "test2", "all"):
        raise ValueError("split must be dev, test, test2 or all")
    out_dir.mkdir(parents=True, exist_ok=True)
    splits = ["dev", "test"] if split == "all" else [split]       # 'all' never includes test2
    for s in splits:
        if s in ("test", "test2") and not force_test and list(out_dir.glob(f"traces_*_{s}.jsonl")):
            raise RuntimeError(f"{s} split was already run; each held-out set is run ONCE. "
                               "Re-run only with --force-test and document it in the report.")
    store.create_schema()                              # fails here, loudly, if the DB is down
    stats = ingest(store, embedder, build_chunks(units, max_size), reingest_check)
    stats.update({"units": len(units), "b_max_size": max_size})

    traces: list[dict] = []
    for q in (q for q in questions if q["split"] in splits):
        qvec = embedder.embed_query(q["question"])
        for strategy in STRATEGIES:
            result = evaluate_query(q, retrieve(store, strategy, q, qvec))
            traces.append(_trace(strategy, q, result))

    for strategy in STRATEGIES:                         # write only after everything succeeded
        for s in splits:
            _write_jsonl(out_dir / f"traces_{strategy}_{s}.jsonl",
                         [t for t in traces if t["strategy"] == strategy and t["split"] == s])
    (out_dir / "ingest_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")
    metrics = _compute_metrics(_read_traces(out_dir))
    metrics["config"] = {"model": embedder.model_name, "b_max_size": max_size, "a_size": 500,
                         "a_overlap": 50, "top_k": 3}
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), "utf-8")
    (out_dir / "errors.log").touch()                    # corpus issues are written by write_corpus_log
    if reingest_check:
        lines = [f"{s}: rows after first upsert = {stats[s]['rows_in_db']}, "
                 f"after second upsert = {stats[s]['rows_after_reingest']}" for s in ("A", "B")]
        (out_dir / "reingest_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return metrics


def write_corpus_log(result, skipped: list[tuple[int, str]], units: list[DocumentPage], path: Path) -> None:
    """results/errors.log: everything dropped or flagged while reading and cleaning the corpus."""
    lines = [f"[reader] skipped {len(skipped)} empty body blocks: "
             f"{sum(k == 'p' for _, k in skipped)} paragraphs, {sum(k == 'table' for _, k in skipped)} tables "
             f"(table body positions: {[p for p, k in skipped if k == 'table']})"]
    lines += [f"[cleaner] dropped blocks {d.start}-{d.end} ({d.chars} chars): {d.reason}" for d in result.dropped]
    lines += [f"[units] {u.metadata['unit_id']} ({u.metadata['section']}) is short: {u.metadata['chars']} chars "
              f"< 1500, not counted toward the 30-unit minimum" for u in units if u.metadata["short"]]
    lines.append("[reader] 3 flowcharts (PHAN_2 and PHAN_4) are images: not extractable as text, excluded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prepare_units() -> list[DocumentPage]:
    result = clean(load_docx(DOCX))
    units = build_units(result)
    validate_corpus(units)
    write_corpus_log(result, skipped_empty_blocks(DOCX), units, RESULTS / "errors.log")
    write_manifest(
        units, result.dropped, MANIFEST,
        accessed_at=_existing_accessed_at(),
        license_note=("Văn bản hành chính công khai của Bộ Y tế (QĐ 5481/QĐ-BYT ngày 30/12/2020); "
                      "chưa xác minh quyền tái phân phối file gốc nên file docx không đưa vào repo."),
        title="Hướng dẫn chẩn đoán và điều trị đái tháo đường típ 2 (ban hành kèm QĐ 5481/QĐ-BYT ngày 30/12/2020)",
        source_path_or_url=f"{SOURCE_URL} (file local: data/raw/{DOCX.name})",
        sha256=hashlib.sha256(DOCX.read_bytes()).hexdigest(),
        notes=["3 lưu đồ trong file (PHẦN 2 và PHẦN 4) bị loại vì nội dung nằm trong ảnh, không phải text.",
               "Số trang Word trong metadata là 48 nhưng .docx không có trang thật; không dùng để đếm.",
               "Giữ nguyên văn, kể cả lỗi chữ trong file gốc."])
    return units


def _existing_accessed_at() -> str:
    """Keep the original access date of the source when the manifest is regenerated."""
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"][0]["accessed_at"]
    except (OSError, KeyError, ValueError):
        return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--split", choices=["dev", "test", "test2", "all"], required=True,
                    help="'all' = dev + test (test2 must be requested explicitly)")
    ap.add_argument("--max-size", type=int, default=800, help="max chars of a B chunk")
    ap.add_argument("--force-test", action="store_true", help="allow re-running the test split")
    ap.add_argument("--reingest-check", action="store_true", help="upsert twice and record row counts")
    args = ap.parse_args()

    units = _prepare_units()
    questions = load_questions(QUESTIONS) + load_questions(QUESTIONS_TEST2)
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("question ids are not unique across the benchmark files")
    embedder = MyEmbedder("BAAI/bge-m3")
    store = PgVectorStore(os.environ.get("DATABASE_URL", DEFAULT_DB), embedder.dimensions)
    metrics = run_pipeline(args.split, embedder=embedder, store=store, units=units, questions=questions,
                           out_dir=RESULTS, max_size=args.max_size, force_test=args.force_test,
                           reingest_check=args.reingest_check)
    print(json.dumps(metrics["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
