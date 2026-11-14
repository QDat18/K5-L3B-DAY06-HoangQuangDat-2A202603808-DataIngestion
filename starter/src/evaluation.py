"""Evaluate retrieved evidence and preserve per-query traces."""
from typing import Any

from .ingestion import normalize_text

TOP_K = 3


def _gold_pages(question: dict[str, Any]) -> set[int]:
    gp = question["gold_page"]
    return set(gp) if isinstance(gp, list) else {gp}


def _is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """Right document, a gold page, and the WHOLE evidence quote inside this one chunk."""
    return (hit.get("document_id") == question["gold_source_id"]
            and hit.get("page") in _gold_pages(question)
            and normalize_text(question["evidence_quote"]) in normalize_text(hit.get("text", "")))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Automatic Hit@1 / Evidence Hit@3 trace for one question.

    Evidence split across chunks counts as a miss (a chunking failure, to be reported).
    This is a proxy only: grounding and coherence labels stay manual.
    """
    top = hits[:TOP_K]
    rank = next((i for i, h in enumerate(top, 1) if _is_hit(question, h)), None)
    return {"id": question["id"], "split": question["split"], "hit1": rank == 1,
            "hit3": rank is not None, "rank": rank, "hits": top}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """strategy -> split ('dev', 'test', plus 'all') -> {'hit1': [n, N], 'hit3': [n, N]}."""
    out: dict[str, dict[str, dict[str, list[int]]]] = {}
    for t in traces:
        if "strategy" not in t:
            raise ValueError("trace without 'strategy'; the caller must add it")
        for split in (t["split"], "all"):
            cell = out.setdefault(t["strategy"], {}).setdefault(split, {"hit1": [0, 0], "hit3": [0, 0]})
            for key in ("hit1", "hit3"):
                cell[key][0] += bool(t[key])
                cell[key][1] += 1
    return out
