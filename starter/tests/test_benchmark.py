from pathlib import Path

import pytest
from src.benchmark import SECTIONS, load_questions, verify_questions
from src.cleaning import clean
from src.ingestion import load_docx
from src.models import DocumentPage
from src.units import build_units

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "benchmark" / "questions.json"
DOCX = ROOT / "data" / "raw" / "5481_QD-BYT_460925.docx"


# ---------- verify_questions on synthetic data (logic) ----------
def U(page, text, section="PHAN_4"):
    return DocumentPage("5481", "5481.docx", page, text,
                        {"section": section, "unit_id": f"5481-U{page:03d}"})


UNITS = [U(1, "Chẩn đoán khi glucose lúc đói ≥ 7,0 mmol/L.", "PHAN_4"),
         U(2, "Metformin là thuốc đầu tay.\nTránh dùng khi eGFR < 30.", "PHAN_5")]


def Q(i, split="dev", **kw):
    base = {"id": f"q{i:02d}", "split": split, "question": "Câu hỏi?", "expected_answer": "Đáp án",
            "gold_source_id": "5481", "gold_page": 1,
            "evidence_quote": "glucose lúc đói ≥ 7,0 mmol/L", "filter": None, "type": "truc_tiep"}
    base.update(kw)
    return base


def errors(qs, units=UNITS, **kw):
    return verify_questions(qs, units, min_total=1, min_dev=0, min_test=0, min_filter=0,
                            min_filter_test=0, **kw)


def test_valid_question_has_no_errors():
    assert errors([Q(1)]) == []


def test_evidence_matches_after_normalization():
    nfd = "glucose lúc đói"      # decomposed accents must still match NFC text
    assert errors([Q(1, evidence_quote="glucose lúc đói")]) == []
    assert errors([Q(1, evidence_quote=nfd)]) == []


def test_evidence_missing_from_gold_unit_is_error():
    assert errors([Q(1, evidence_quote="Metformin là thuốc đầu tay")])    # lives in unit 2, gold is 1


def test_gold_page_list_accepts_any_listed_unit():
    assert errors([Q(1, gold_page=[1, 2], evidence_quote="Metformin là thuốc đầu tay")]) == []


def test_unknown_gold_page_or_source_is_error():
    assert errors([Q(1, gold_page=99)])
    assert errors([Q(1, gold_source_id="khac")])


def test_duplicate_ids_and_bad_split_are_errors():
    assert errors([Q(1), Q(1)])
    assert errors([Q(1, split="val")])


def test_missing_or_empty_fields_are_errors():
    q = Q(1)
    del q["expected_answer"]
    assert errors([q])
    assert errors([Q(1, question="  ")])


def test_filter_must_be_valid_section_and_contain_gold():
    assert errors([Q(1, filter={"section": "PHAN_4"})]) == []
    assert errors([Q(1, filter={"section": "PHAN_99"})])               # not a section
    assert errors([Q(1, filter={"section": "PHAN_5"})])                # would exclude the gold unit
    assert errors([Q(1, filter={"page": 1})])                          # only `section` is allowed
    assert errors([Q(1, filter={"section": "PHAN_4", "gold_page": 1})])


def test_count_rules_are_enforced():
    qs = [Q(i, "dev") for i in range(1, 4)]
    assert verify_questions(qs, UNITS, min_total=4, min_dev=0, min_test=0, min_filter=0, min_filter_test=0)
    assert verify_questions(qs, UNITS, min_total=1, min_dev=0, min_test=1, min_filter=0, min_filter_test=0)
    assert verify_questions(qs, UNITS, min_total=1, min_dev=0, min_test=0, min_filter=1, min_filter_test=0)
    qs = [Q(1, "dev", filter={"section": "PHAN_4"}), Q(2, "test")]
    assert verify_questions(qs, UNITS, min_total=1, min_dev=0, min_test=0, min_filter=1, min_filter_test=1)


def test_sections_are_the_13_values():
    assert len(SECTIONS) == 13 and "PHAN_10" in SECTIONS and "PHU_LUC_03" in SECTIONS


# ---------- the real benchmark file (needs benchmark/questions.json) ----------
@pytest.fixture(scope="module")
def real_units():
    return build_units(clean(load_docx(DOCX)))


@pytest.fixture(scope="module")
def real_questions():
    return load_questions(QUESTIONS)


def test_counts_20_15_5_and_3_filters_one_in_test(real_questions):
    qs = real_questions
    assert len(qs) >= 20
    assert sum(q["split"] == "dev" for q in qs) >= 15
    assert sum(q["split"] == "test" for q in qs) >= 5
    filtered = [q for q in qs if q["filter"]]
    assert len(filtered) >= 3
    assert any(q["split"] == "test" for q in filtered)


def test_evidence_found_in_gold_unit(real_questions, real_units):
    assert verify_questions(real_questions, real_units) == []


def test_filter_value_is_valid_section(real_questions):
    for q in real_questions:
        if q["filter"]:
            assert set(q["filter"]) == {"section"} and q["filter"]["section"] in SECTIONS


def test_filter_not_derived_from_gold(real_questions):
    for q in real_questions:
        if q["filter"]:
            assert "gold_page" not in q["filter"] and "gold_source_id" not in q["filter"]


def test_unique_ids(real_questions):
    ids = [q["id"] for q in real_questions]
    assert len(ids) == len(set(ids))


# ---------- test2: held-out set written after the first test run ----------
QUESTIONS_TEST2 = ROOT / "benchmark" / "questions_test2.json"


def test_verify_accepts_test2_only_when_allowed():
    q = Q(1, "test2")
    assert errors([q])                                                  # default: dev/test only
    assert verify_questions([q], UNITS, allowed_splits=("test2",), min_total=1, min_dev=0, min_test=0,
                            min_filter=0, min_filter_test=0) == []


def test_test2_file_is_valid_and_disjoint_from_first_benchmark(real_units, real_questions):
    t2 = load_questions(QUESTIONS_TEST2)
    assert len(t2) >= 10 and {q["split"] for q in t2} == {"test2"}
    assert sum(bool(q["filter"]) for q in t2) >= 3
    assert verify_questions(t2, real_units, allowed_splits=("test2",), min_total=10, min_dev=0, min_test=0,
                            min_filter=3, min_filter_test=0) == []
    first_ids = {q["id"] for q in real_questions}
    assert not first_ids & {q["id"] for q in t2}
    assert not {q["question"] for q in real_questions} & {q["question"] for q in t2}
