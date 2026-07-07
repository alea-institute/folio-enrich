"""Tests for the NER cross-validation eval harness (``eval/``).

Two tiers:
  * Fast unit tests (default suite): pure metric logic + gold well-formedness — no
    pipeline, no ontology load.
  * ``@pytest.mark.eval`` tests: drive the real deterministic pipeline. Excluded from
    the default run (see pyproject ``addopts``); invoke with ``-m eval``. They carry a
    generous per-test timeout because they load FOLIO + run the pipeline several times.

Run the eval tier:  cd backend && .venv/bin/python -m pytest tests/test_ner_eval_harness.py -m eval -v
"""

from __future__ import annotations

import asyncio

import pytest

from eval.gold_schema import GoldCandidate, GoldEntry, GoldSpan, load_gold
from eval.metrics import PredSpan, iri_key, score_entry, score_set
from eval.runner import DEFAULT_GOLD, run_eval


# ── fast: metric primitives ──────────────────────────────────────────────── #
def _entry(gid, start, end, iri, polarity="positive", verification="deterministic"):
    return GoldEntry(
        gold_id=gid, doc_id="d", doc_source="frontend/demos/contract.json",
        span=GoldSpan(start=start, end=end, text="x"),
        expected_iri=iri, expected_label="X", polarity=polarity,
        verification=verification,
    )


def test_iri_key_normalizes_host():
    assert iri_key("https://folio.openlegalstandard.org/RABC") == "RABC"
    assert iri_key("https://ontology.catholicos.catholic/RABC") == "RABC"
    assert iri_key("") == ""
    assert iri_key(None) == ""


def test_predspan_overlap():
    p = PredSpan(0, 17, "iri")           # "This Agreement is"
    assert p.overlaps(5, 14)             # covers "Agreement"
    assert not p.overlaps(20, 30)


def test_positive_true_positive():
    g = _entry("g1", 5, 14, "https://x/RA")
    preds = [PredSpan(0, 17, "https://x/RA")]   # overlap + right IRI
    outcome, tp, fp, fn, tn, _ = score_entry(g, preds)
    assert (outcome, tp, fp, fn) == ("TP", 1, 0, 0)


def test_positive_wrong_iri_is_fn_and_fp():
    g = _entry("g1", 5, 14, "https://x/RA")
    preds = [PredSpan(0, 17, "https://x/RWRONG")]
    outcome, tp, fp, fn, tn, _ = score_entry(g, preds)
    assert (outcome, tp, fp, fn) == ("FN+FP", 0, 1, 1)


def test_positive_miss_is_fn():
    g = _entry("g1", 5, 14, "https://x/RA")
    outcome, tp, fp, fn, tn, _ = score_entry(g, [])
    assert (outcome, tp, fp, fn) == ("FN", 0, 0, 1)


def test_negative_gold_flags_wrong_concept():
    g = _entry("g1", 5, 14, "https://x/RLICENSE", polarity="negative")
    # pipeline asserts the concept the negative case warns against → FP
    o1, *_ = score_entry(g, [PredSpan(0, 17, "https://x/RLICENSE")])
    assert o1 == "FP"
    # pipeline avoids it → TN
    o2, *_ = score_entry(g, [PredSpan(0, 17, "https://x/ROTHER")])
    assert o2 == "TN"


def test_needs_review_entries_are_not_scored():
    scored = _entry("g1", 5, 14, "https://x/RA", verification="deterministic")
    unscored = _entry("g2", 5, 14, "https://x/RB", verification="needs_review")
    prf, outcomes = score_set([scored, unscored], [PredSpan(0, 17, "https://x/RA")])
    assert prf.tp == 1 and len(outcomes) == 1   # only the deterministic entry counted


def test_harness_detects_recall_regression():
    """The metric MUST catch a recall drop when NER wrongly rejects a gold span."""
    g = _entry("g1", 5, 14, "https://x/RA")
    off_prf, _ = score_set([g], [PredSpan(0, 17, "https://x/RA")])   # found
    on_prf, _ = score_set([g], [])                                   # NER rejected it
    assert off_prf.recall == 1.0 and on_prf.recall == 0.0            # regression visible


# ── fast: committed gold well-formedness ─────────────────────────────────── #
def test_committed_gold_is_wellformed():
    gold = load_gold(DEFAULT_GOLD)
    assert gold, "gold set is empty — run eval.curate"
    for e in gold:
        e.validate()   # raises on any schema violation
    scored = [e for e in gold if e.is_scored]
    assert len(scored) >= 10, "need a meaningful scored subset"
    # every scored entry has an expected IRI + label
    assert all(e.expected_iri and e.expected_label for e in scored)


# ── eval tier: drives the real deterministic pipeline ────────────────────── #
@pytest.fixture(scope="module")
def contract_gold():
    gold = [e for e in load_gold(DEFAULT_GOLD) if e.doc_id == "contract"]
    assert gold, "no contract gold — run eval.curate"
    return gold


@pytest.mark.eval
@pytest.mark.timeout(600)
def test_deterministic_eval_runs_and_is_recall_safe(contract_gold):
    rep = asyncio.run(run_eval(contract_gold))
    assert rep["mode"] == "deterministic"
    assert rep["gold_entries_scored"] >= 1
    for key in ("ner_off", "ner_on", "delta", "recommendation"):
        assert key in rep
    # The core design guarantee: NER cross-validation must not regress recall.
    assert rep["ner_on"]["recall"] >= rep["ner_off"]["recall"] - 1e-9
    assert rep["recommendation"] in (
        "FLIP_SUPPORTED", "HOLD_recall_regression", "HOLD_no_f1_gain", "INSUFFICIENT_GOLD",
    )


@pytest.mark.eval
@pytest.mark.timeout(600)
def test_deterministic_eval_is_reproducible(contract_gold):
    a = asyncio.run(run_eval(contract_gold))
    b = asyncio.run(run_eval(contract_gold))
    assert a["ner_off"] == b["ner_off"]
    assert a["ner_on"] == b["ner_on"]
    assert a["canonical_hash"] == b["canonical_hash"]   # canonical text is stable
