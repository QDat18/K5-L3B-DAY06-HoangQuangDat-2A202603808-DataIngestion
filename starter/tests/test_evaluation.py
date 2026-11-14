from src.evaluation import evaluate_query, summarize

EVIDENCE = "glucose lúc đói ≥ 7,0 mmol/L"


def question(gold_page=1, evidence=EVIDENCE, qid="q01", split="dev"):
    return {"id": qid, "split": split, "gold_source_id": "5481", "gold_page": gold_page,
            "evidence_quote": evidence}


def hit(text, page=1, document_id="5481", cid="c"):
    return {"chunk_id": cid, "text": text, "score": 0.5, "document_id": document_id,
            "source": "5481.docx", "page": page, "metadata": {}}


GOOD = f"Chẩn đoán khi {EVIDENCE}."
BAD = "Nội dung không liên quan."


def test_hit1_when_top1_has_evidence():
    r = evaluate_query(question(), [hit(GOOD), hit(BAD), hit(BAD)])
    assert (r["hit1"], r["hit3"], r["rank"]) == (True, True, 1)


def test_hit3_only_when_evidence_in_rank_2_or_3():
    r = evaluate_query(question(), [hit(BAD), hit(BAD), hit(GOOD)])
    assert (r["hit1"], r["hit3"], r["rank"]) == (False, True, 3)
    r = evaluate_query(question(), [hit(BAD), hit(BAD), hit(BAD)])
    assert (r["hit1"], r["hit3"], r["rank"]) == (False, False, None)


def test_page_match_but_evidence_split_is_miss():
    half = "Chẩn đoán khi glucose lúc đói"                 # evidence cut in two chunks
    r = evaluate_query(question(), [hit(half), hit("≥ 7,0 mmol/L")])
    assert r["hit3"] is False


def test_evidence_on_wrong_page_or_source_is_miss():
    assert evaluate_query(question(), [hit(GOOD, page=2)])["hit3"] is False
    assert evaluate_query(question(), [hit(GOOD, document_id="khac")])["hit3"] is False


def test_nfd_evidence_still_matches():
    nfd = "glucose lúc đối".replace("ố", "ó")      # decomposed accents
    r = evaluate_query(question(evidence=nfd), [hit("Khi glucose lúc đói tăng cao")])
    assert r["hit1"] is True
    r = evaluate_query(question(), [hit("Chẩn đoán khi glucose lúc đói ≥ 7,0 mmol/L.")])
    assert r["hit1"] is True


def test_whitespace_differences_do_not_hide_evidence():
    r = evaluate_query(question(), [hit("glucose  lúc đói ≥ 7,0   mmol/L")])
    assert r["hit1"] is True


def test_multiple_gold_pages_any_accepted():
    q = question(gold_page=[1, 2])
    assert evaluate_query(q, [hit(GOOD, page=2)])["hit1"] is True
    assert evaluate_query(q, [hit(GOOD, page=3)])["hit3"] is False


def test_only_top3_are_considered_and_hits_preserved():
    hits = [hit(BAD), hit(BAD), hit(BAD), hit(GOOD)]
    r = evaluate_query(question(), hits)
    assert r["hit3"] is False and r["hits"] == hits[:3]


def test_no_hits_is_a_miss():
    r = evaluate_query(question(), [])
    assert (r["hit1"], r["hit3"], r["rank"], r["hits"]) == (False, False, None, [])


def test_summarize_reports_n_over_N_per_split():
    def trace(strategy, split, h1, h3):
        return {"strategy": strategy, "split": split, "hit1": h1, "hit3": h3}
    traces = [trace("A", "dev", True, True), trace("A", "dev", False, True), trace("A", "dev", False, False),
              trace("A", "test", True, True), trace("B", "dev", True, True)]
    s = summarize(traces)
    assert s["A"]["dev"] == {"hit1": [1, 3], "hit3": [2, 3]}
    assert s["A"]["test"] == {"hit1": [1, 1], "hit3": [1, 1]}
    assert s["A"]["all"] == {"hit1": [2, 4], "hit3": [3, 4]}
    assert s["B"]["dev"] == {"hit1": [1, 1], "hit3": [1, 1]}
    assert "test" not in s["B"]
