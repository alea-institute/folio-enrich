# NER Cross-Validation Gold-Set Eval Harness — Plan (CE)

- **Date:** 2026-07-07
- **Repo:** folio-enrich · branch `feat/ner-eval-harness` (off `origin/main`)
- **Driver:** Master Plan C4 / STATUS-lane-5 L5.5 follow-up — the flip precondition for
  `ner_cross_validation_enabled` ("F1 improves without recall regression") was
  *unmeasurable* because no precision/recall/F1 gold-set harness existed.
- **Triage:** [CE] — new eval subsystem, gold-data curation, CI wiring. Damien-approved
  (QA round-2 q4) to build now.

## Problem

`ner_cross_validation_enabled` (config.py:149, default **False**) modulates annotation
confidence inside `ReconciliationStage._apply_ner_adjustments`: for each annotation whose
span overlaps a spaCy NER entity, a per-ontology NER-label→branch affinity map either
**boosts** (+0.04) or **penalizes** (−0.08) confidence; a penalized annotation that drops
below 0.20 is **rejected**. It never adds spans (recall-preserving by design). To decide
the flip we must measure precision/recall/F1 with the flag ON vs OFF against a
human-verifiable gold set — which did not exist. `test_disambiguation_eval.py` is an
IRI-assertion regression, and the baked `frontend/demos/*.json` are *pipeline outputs
(silver), not gold*.

## Key architectural finding (enables a FREE eval)

The NER cross-validation pass is **fully deterministic**: it reads locally-computed spaCy
NER entities (`EarlyTripleStage`, CPU model `en_core_web_sm`) and a static affinity map,
and applies bounded confidence math. The only *paid* pipeline stages are the upstream
candidate generators (LLMConcept, DocumentType, ContextualRerank[off by default],
BranchJudge, LLMIndividual/Property, Metadata). Running the orchestrator with `llm=None`
yields a **fully deterministic** ruler→NER→reconcile→resolve→string-match pipeline that
still emits real `Annotation`s with FOLIO IRIs — and the NER flag still fires on it.

→ We can measure the NER flag's effect on the **deterministic annotation set for $0**,
reproducibly, in CI. The **full-pipeline** measurement (LLM-sourced concepts included) is
the authoritative flip signal but needs paid calls → we compute a token-grounded spend
estimate and QUEUE it rather than run it.

## Deliverables

1. **Gold-set format + curation tooling** (`backend/eval/gold_schema.py`, `curate.py`,
   `gold/folio_ner_gold.jsonl`, `gold/README.md`).
   - Gold entry = `(doc_id, span{start,end,text}, expected_iri, expected_label, branch,
     polarity[positive|negative], verification[deterministic|human|needs_review],
     difficulty[clear|borderline], candidates[], rationale)`.
   - Seeded independently of the enrich ranking logic: exact FOLIO-label matches in the
     demo source text (the FOLIO label dictionary is the oracle) → `positive/deterministic`;
     baked-demo annotations that are ambiguous (multi-candidate / alt-label) →
     `needs_review/borderline` with competing candidates (the evidence-pack borderline
     pattern). Non-circular: gold labels come from the ontology, not from reconciliation.
   - Curation is idempotent and **never overwrites `verification: "human"`** entries, so
     Damien/lanes extend it by hand and re-runs preserve their work.

2. **Eval runner** (`backend/eval/metrics.py`, `runner.py`).
   - Span-restricted precision/recall/F1 over the curated gold judgment set (correct for a
     *sampled* gold): TP = positive gold matched by a confirmed prediction (span overlap +
     IRI); FN = positive gold missed / wrong-IRI; FP = wrong-IRI or negative-gold predicted.
   - Runs the real `PipelineOrchestrator` flag OFF then ON, evaluates each, reports the
     delta + a flip recommendation (recall non-regression + F1 improvement).
   - Deterministic + reproducible (`llm=None`, sorted output, no randomness).
   - CLI `--mode deterministic|full`, `--gold`, `--out report.json`.

3. **CI-invokable marker** — register `eval` marker; `test_ner_eval_harness.py`
   (`@pytest.mark.eval`) runs the deterministic eval and asserts the harness contract +
   reproducibility; a new `.github/workflows/eval.yml` runs `-m eval`.

4. **Spend estimate, queued** (`backend/eval/estimate_spend.py`) — token-grounded full-mode
   cost estimate appended to `briefs/qa/pending-questions.jsonl` (NOT run).

5. **Evidence pack** of borderline cases; README delta; `/ce:review`; `/ce:compound`.

## Non-goals / honest limits

- The deterministic eval omits LLM-sourced concepts (~40% of production annotations); it is
  a free *lower-fidelity proxy*. The authoritative flip decision uses the spend-gated
  full-mode run.
- Gold is a curated sample; precision/recall are span-restricted (documented). Expanding
  gold coverage tightens the estimate.
- Default stays **False** (recall-safe) until the full-mode numbers justify the flip; the
  prod flip rides the ask-gated deploy.
