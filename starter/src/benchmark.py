"""Load and verify the benchmark questions (gold source, evidence, filter, split)."""
import json
from pathlib import Path

from .ingestion import normalize_text
from .models import DocumentPage

SECTIONS = frozenset([f"PHAN_{i}" for i in range(1, 11)] + [f"PHU_LUC_0{i}" for i in range(1, 4)])
REQUIRED = ("id", "split", "question", "expected_answer", "gold_source_id",
            "gold_page", "evidence_quote", "filter", "type")


def load_questions(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("questions file must contain a JSON list")
    return data


def _pages(q: dict) -> list[int]:
    gp = q.get("gold_page")
    pages = gp if isinstance(gp, list) else [gp]
    return pages if pages and all(isinstance(p, int) and not isinstance(p, bool) for p in pages) else []


def _check_question(q: dict, by_page: dict[int, DocumentPage],
                    allowed_splits: tuple[str, ...] = ("dev", "test")) -> list[str]:
    qid = q.get("id", "?")
    errs = [f"{qid}: missing field '{k}'" for k in REQUIRED if k not in q]
    if errs:
        return errs
    for k in ("id", "question", "expected_answer", "evidence_quote", "gold_source_id", "type"):
        if not isinstance(q[k], str) or not q[k].strip():
            errs.append(f"{qid}: '{k}' must be a non-empty string")
    if q["split"] not in allowed_splits:
        errs.append(f"{qid}: split must be one of {list(allowed_splits)}, got {q['split']!r}")
    pages = _pages(q)
    if not pages:
        return errs + [f"{qid}: gold_page must be an int or a non-empty list of ints"]
    gold = [by_page[p] for p in pages if p in by_page]
    if len(gold) != len(pages):
        return errs + [f"{qid}: gold_page {pages} not all found among the units"]
    if any(u.document_id != q["gold_source_id"] for u in gold):
        errs.append(f"{qid}: gold_source_id {q['gold_source_id']!r} does not match the gold unit")
    evidence = normalize_text(q["evidence_quote"]) if isinstance(q["evidence_quote"], str) else ""
    if evidence and not any(evidence in normalize_text(u.text) for u in gold):
        errs.append(f"{qid}: evidence_quote not found in gold unit(s) {pages}")
    flt = q["filter"]
    if flt is not None:
        if not isinstance(flt, dict) or set(flt) != {"section"}:
            errs.append(f"{qid}: filter must be null or {{'section': ...}} only")
        elif flt["section"] not in SECTIONS:
            errs.append(f"{qid}: filter section {flt['section']!r} is not a valid section")
        elif flt["section"] not in {u.metadata.get("section") for u in gold}:
            errs.append(f"{qid}: filter section {flt['section']!r} excludes the gold unit")
    return errs


def verify_questions(questions: list[dict], units: list[DocumentPage], *, min_total: int = 20,
                     min_dev: int = 15, min_test: int = 5, min_filter: int = 3,
                     min_filter_test: int = 1,
                     allowed_splits: tuple[str, ...] = ("dev", "test")) -> list[str]:
    """Return a list of problems; an empty list means the benchmark is valid.

    `allowed_splits` lets the held-out `test2` file be verified on its own (with the count minimums relaxed).
    """
    by_page = {u.page: u for u in units}
    errs: list[str] = []
    ids = [q.get("id") for q in questions]
    errs += [f"duplicate id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    for q in questions:
        errs += _check_question(q, by_page, allowed_splits)
    dev = sum(q.get("split") == "dev" for q in questions)
    test = sum(q.get("split") == "test" for q in questions)
    filtered = [q for q in questions if q.get("filter")]
    filtered_test = sum(q.get("split") == "test" for q in filtered)
    for ok, msg in [(len(questions) >= min_total, f"need >= {min_total} questions, have {len(questions)}"),
                    (dev >= min_dev, f"need >= {min_dev} dev questions, have {dev}"),
                    (test >= min_test, f"need >= {min_test} test questions, have {test}"),
                    (len(filtered) >= min_filter, f"need >= {min_filter} filter questions, have {len(filtered)}"),
                    (filtered_test >= min_filter_test,
                     f"need >= {min_filter_test} filter question(s) in test, have {filtered_test}")]:
        if not ok:
            errs.append(msg)
    return errs
