"""Manual-audit sample files (labels are left EMPTY for the author) and a label summariser.

    python -m src.audit            # writes results/audit_{coherence,metadata,grounding}.csv
"""
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import Chunk, DocumentPage

STRATEGIES = ("A", "B", "C")
N_COHERENCE_POSITIONS = 10
VALID_LABELS = {"0", "1", "2"}


def _write(path: Path, header: list[str], rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def _coherence_rows(units, chunks_by_strategy) -> list[dict]:
    """Same 10 positions for every strategy: the first 10 unit_ids in sorted order.

    The chunk labelled for a position is the first chunk that starts in that unit.
    """
    unit_ids = sorted(u.metadata["unit_id"] for u in units)[:N_COHERENCE_POSITIONS]
    rows = []
    for s in STRATEGIES:
        by_unit: dict[str, Chunk] = {}
        for c in chunks_by_strategy[s]:
            by_unit.setdefault(c.metadata["unit_id"], c)
        for uid in unit_ids:
            if uid not in by_unit:
                raise ValueError(f"strategy {s} has no chunk in {uid}")
            c = by_unit[uid]
            rows.append({"strategy": s, "unit_id": uid, "section": c.metadata["section"],
                         "chunk_id": c.chunk_id, "chunk_chars": len(c.text), "text": c.text,
                         "label": "", "reason": ""})
    return rows


def _metadata_rows(units, test_traces) -> list[dict]:
    """Every top-3 record of every test question, next to the values it must match."""
    truth = {u.page: u for u in units}
    rows = []
    for s in STRATEGIES:
        for t in (t for t in test_traces if t["strategy"] == s):
            for rank, h in enumerate(t["hits"], 1):
                unit = truth.get(h["page"])
                rows.append({
                    "strategy": s, "question_id": t["id"], "rank": rank, "chunk_id": h["chunk_id"],
                    "document_id": h["document_id"], "source": h["source"], "page": h["page"],
                    "section": h["metadata"].get("section"), "unit_id": h["metadata"].get("unit_id"),
                    "expected_source": unit.source if unit else "",
                    "expected_section": unit.metadata["section"] if unit else "",
                    "filter_requested": (t["filter"] or {}).get("section", ""),
                    "label": "", "reason": ""})
    return rows


def _grounding_rows(test_traces, questions) -> list[dict]:
    answers = {q["id"]: q["expected_answer"] for q in questions or []}
    rows = []
    for s in STRATEGIES:
        for t in (t for t in test_traces if t["strategy"] == s):
            row = {"strategy": s, "question_id": t["id"], "question": t["question"],
                   "expected_answer": answers.get(t["id"], ""), "evidence_quote": t["evidence_quote"],
                   "gold_page": json.dumps(t["gold_page"])}
            for r in range(3):
                h = t["hits"][r] if r < len(t["hits"]) else None
                row[f"top{r + 1}_chunk_id"] = h["chunk_id"] if h else ""
                row[f"top{r + 1}_page"] = h["page"] if h else ""
                row[f"top{r + 1}_text"] = h["text"] if h else ""
            row.update({"label": "", "reason": ""})
            rows.append(row)
    return rows


def make_audit_samples(units: list[DocumentPage], chunks_by_strategy: dict[str, list[Chunk]],
                       test_traces: list[dict], out_dir: Path, questions: list[dict] | None = None) -> None:
    """Write the three audit CSVs. All `label` and `reason` cells are empty: the author fills them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _write(out_dir / "audit_coherence.csv",
           ["strategy", "unit_id", "section", "chunk_id", "chunk_chars", "text", "label", "reason"],
           _coherence_rows(units, chunks_by_strategy))
    _write(out_dir / "audit_metadata.csv",
           ["strategy", "question_id", "rank", "chunk_id", "document_id", "source", "page", "section",
            "unit_id", "expected_source", "expected_section", "filter_requested", "label", "reason"],
           _metadata_rows(units, test_traces))
    _write(out_dir / "audit_grounding.csv",
           ["strategy", "question_id", "question", "expected_answer", "evidence_quote", "gold_page",
            "top1_chunk_id", "top1_page", "top1_text", "top2_chunk_id", "top2_page", "top2_text",
            "top3_chunk_id", "top3_page", "top3_text", "label", "reason"],
           _grounding_rows(test_traces, questions))


def summarize_labels(csv_path: Path) -> dict[str, dict[str, Any]]:
    """Per strategy: rows, labelled/unlabelled, count of each label 0/1/2 and mean label.

    For the metadata file the label is 1 = record complete and correct, 0 = not (mean = share correct).
    """
    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "labeled": 0, "unlabeled": 0, "counts": {"0": 0, "1": 0, "2": 0}, "mean": None})
    values: dict[str, list[int]] = defaultdict(list)
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cell = out[row["strategy"]]
            cell["n"] += 1
            label = (row["label"] or "").strip()
            if not label:
                cell["unlabeled"] += 1
                continue
            if label not in VALID_LABELS:
                raise ValueError(f"invalid label {label!r} for {row['strategy']} in {csv_path}")
            cell["labeled"] += 1
            cell["counts"][label] += 1
            values[row["strategy"]].append(int(label))
    for s, cell in out.items():
        cell["mean"] = sum(values[s]) / len(values[s]) if values[s] else None
    return dict(out)


def main() -> None:
    from .benchmark import load_questions
    from .cleaning import clean
    from .ingestion import load_docx
    from .run import DOCX, QUESTIONS, RESULTS, build_chunks
    from .units import build_units

    units = build_units(clean(load_docx(DOCX)))
    chunks = build_chunks(units)
    chunks_by_strategy = {"A": chunks["A"], "B": chunks["B"], "C": chunks["B"]}     # C reuses B's chunks
    traces = []
    for s in STRATEGIES:
        path = RESULTS / f"traces_{s}_test.jsonl"
        traces += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    make_audit_samples(units, chunks_by_strategy, traces, RESULTS, load_questions(QUESTIONS))
    print(f"wrote audit samples to {RESULTS}")


if __name__ == "__main__":
    main()
