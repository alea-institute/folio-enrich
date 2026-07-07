# NER cross-validation — full-mode eval closure (2026-07-07)

**Verdict: HOLD. `ner_cross_validation_enabled` default stays `False`.**
The authoritative full-pipeline eval (LLM candidate stages ON) shows **zero F1 gain** from the flag, on both the original and the expanded gold set. The flip precondition ("F1 improves without recall regression") is **not met** on the F1 side; recall is safe. The question opened in `pack.html` EP-ENRICH-NER-EVAL-013 ("authoritative full-mode run — queued") is now **closed**.

## Runs (both authoritative full mode)

- Model: `gemini-3-flash-preview`; pipeline: full `PipelineOrchestrator` with all paid LLM candidate stages ON.
- Runner: `backend/eval/full_runner.py` via `python -m eval.runner --mode full` — one paid LLM pass per doc (flag OFF), then a cached replay for flag ON (`CachingLLM`), with actual token counts captured from Gemini `usageMetadata`.
- Damien-approved under the q8 spend cap (<$5).

| Run | Gold (total / scored) | OFF P/R/F1 | ON P/R/F1 | Delta | Changed outcomes | Recommendation | Actual-token cost est |
|---|---|---|---|---|---|---|---|
| Baseline (`reports/full_mode_baseline.json`) | 146 / 52 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0 / 0 / 0 | none | `HOLD_no_f1_gain` | $0.11–$0.50 |
| Expanded (`reports/full_mode_expanded.json`) | 159 / 62 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0 / 0 / 0 | none | `HOLD_no_f1_gain` | $0.12–$0.53 |

Gold expansion: 146→159 entries (52→62 scored), curated via `backend/eval/gold/expansion_candidates.jsonl` + `expansion_manifest.json` (curation cost ~$0.01). Total spend well under the $5 cap.

## Reading

- The flag is **recall-safe** even against the full LLM-sourced annotation stream: with the flag ON it was free to penalize/reject any of the 52 (then 62) scored spans and rejected none (`changed_outcomes: []` in both reports).
- But it produced **no F1 gain** — no false positive was suppressed, no ranking improved — so there is no measured benefit to buy with the added spaCy-affinity coupling.
- Report JSONs carry `raw_predictions` per doc/flag, so future gold-set growth can be re-scored offline (`eval.metrics.score_set`) **without another paid pass**.

## Flip precondition status

| Criterion | Result |
|---|---|
| RUB-NER-01 — recall non-regression (OFF→ON) | PASS (recall +0.000, both runs) |
| RUB-NER-02 — F1 improvement | **NOT MET** (F1 +0.000, both runs — full mode, expanded gold) |

Revisit only if the gold set grows to include cases where reconciliation-stage confidence actually discriminates (e.g. human-verified borderline promotions that the pipeline currently gets wrong); re-score `raw_predictions` first — it is free.
