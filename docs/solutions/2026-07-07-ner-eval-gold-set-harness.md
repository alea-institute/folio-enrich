---
title: Measuring a post-LLM confidence-adjustment flag without paid API calls
date: 2026-07-07
repo: folio-enrich
tags: [eval, ner, gold-set, precision-recall-f1, deterministic, gestalt, ci]
component: backend/eval
---

# Problem

`ner_cross_validation_enabled` (default False) needed a flip decision gated on
"F1 improves without recall regression," but no precision/recall/F1 gold-set harness
existed. `test_disambiguation_eval.py` is an IRI-assertion regression, and the baked
`frontend/demos/*.json` are pipeline outputs (silver), not gold. The naive read was
that measuring the flag requires expensive full-pipeline LLM runs on both settings.

# Key insight

NER cross-validation is a **fully deterministic, post-LLM confidence-adjustment pass**
(`reconciliation_stage.py::_apply_ner_adjustments`): it reads locally-computed spaCy NER
entities + a static per-ontology branch affinity map and applies bounded ±confidence math,
rejecting spans below 0.20. It never adds spans (recall-preserving by design). The only
*paid* pipeline stages are the upstream candidate generators. Therefore:

- Running `PipelineOrchestrator(JobStore()).run(job)` with **`llm=None`** yields a fully
  deterministic ruler→NER→reconcile→resolve→string-match pipeline that still emits real
  FOLIO-IRI annotations *and still fires the NER flag*. The flag OFF-vs-ON comparison on
  this subset costs **$0** and is reproducible (spaCy + FOLIO are deterministic; canonical
  text is stable run-to-run, so gold char-offsets stay valid).
- The NER flag does **not** change LLM calls (it's post-LLM), so the authoritative
  full-pipeline comparison is **1 LLM pass per doc + a free reconciliation replay OFF/ON**,
  not 2× — a ~50% cost saving baked into the spend estimate.

This is the portfolio "gestalt" pattern (II.0.2): deterministic candidate generation →
(here) deterministic adjustment, measured deterministically; the probabilistic upstream is
only needed for the higher-fidelity tier, which is spend-gated and queued.

# Solution shape (reusable for any LLM-touching tool — II.0.4 "gold-data & eval culture")

`backend/eval/`:
- `gold_schema.py` — dataclass gold model, JSONL, `verification ∈ {deterministic|human|needs_review}`;
  only deterministic+human are scored.
- `metrics.py` — **span-restricted** P/R/F1 (correct for a *sampled* gold: score only over
  labelled spans, don't treat every unlabelled prediction as FP). Match = span overlap +
  IRI hash-suffix equality.
- `curate.py` — seed gold **non-circularly**: spans from demos, but the correct label comes
  from an independent oracle (`FolioService.get_all_labels_multi` — the FOLIO label
  dictionary), not the pipeline's ranking. Ambiguous surfaces → `needs_review` borderline
  with competing candidates. Idempotent; **never overwrites `verification:"human"`**.
- `runner.py` — flag OFF then ON, delta + flip recommendation; deterministic-only, with a
  spend-gated `--mode full` that redirects to the estimator.
- `estimate_spend.py` — token-grounded cost, appended to `briefs/qa/pending-questions.jsonl`.
- Pytest `eval` marker (excluded from the default suite; run `-m eval`) + `.github/workflows/eval.yml`.

# Gotchas

- **Pytest `timeout = 30`** (pyproject) kills pipeline-driving tests — mark them `@pytest.mark.eval`
  **and** `@pytest.mark.timeout(600)`, and exclude `eval` from default `addopts`.
- **`DocumentInput.format`** is an enum: use `"plain_text"`, not `"txt"`.
- **Circularity risk:** seeding scored gold from the pipeline's own confirmed output makes
  the OFF run trivially perfect. Mitigated by (a) validating each label against the ontology
  oracle and (b) the fact that the recall-safety finding (ON never rejected a true span) is
  itself non-circular. Full non-circularity needs human-verified borderline promotion.

# Result

52 scored + 94 borderline gold across 6 demo docs. Free deterministic eval: NER OFF and ON
both P=R=F1=1.000 → recommendation **HOLD_no_f1_gain** (recall-safe, but no F1 gain on the
unambiguous set). The discriminating signal lives in the borderline + LLM-sourced concepts
→ full-mode run queued (~$0.03–$0.14). Default stays False (recall-safe). 915-test suite green.
