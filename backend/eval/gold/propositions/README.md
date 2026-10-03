# Proposition gold records

This directory contains proposition gold JSONL, brat standoff files, the canonical text each opinion was annotated against, and a cycle manifest.
Each manifest entry names its annotator. The Palsgraf cycle-1 record was AI-annotated under delegation and has not yet been human-validated (see `docs/plans/2026-09-30-palsgraf-cycle-1-reconciliation.md`).
Gold is non-circular: exported labels come from explicit annotator outcomes, not from pipeline output alone.
Deleted pre-selected candidates remain as audit records so pre-selection precision is computable.

## Cycle metrics (recorded at export)

- Recall proxy: `1 - hand-added / total exported gold`.
- Precision: `(accepted + edited) / (accepted + edited + deleted)` over pre-selected candidates.
- Density: exported gold propositions per 1,000 words of normalized canonical text. Deleted candidates and learning-only tags are excluded.

## Extractor benchmark

From `backend/`:

```sh
.venv/bin/python -m eval.proposition_benchmark                       # all splits
.venv/bin/python -m eval.proposition_benchmark --split development   # tuning view
.venv/bin/python -m eval.proposition_benchmark --write               # write reports/propositions/<lexicon_version>.json
```

- Gold is `record_type == "annotation"` rows. A candidate matches a gold span at Dice ≥ 0.5, one-to-one. A candidate matching a `candidate-audit` (annotator-deleted) span counts as a false positive.
- `splits` in the manifest assigns character ranges to `development` and `held-out`. Tune only against development. An opinion without `splits` is wholly held-out; `"benchmark": false` excludes a fixture.
- Every opinion's `text_file` must reproduce each gold span's text exactly (`tests/test_proposition_gold_text.py`).
- Reports carry 95% Wilson intervals. The overfit flag is indicative only: the Palsgraf splits differ by author (Cardozo majority vs. Andrews dissent), not only by tuning.
- The Palsgraf held-out split was measured once, for `phase-b-v1`. Studying its errors would turn it into tuning data, so the next honest held-out test is a new ladder opinion.
