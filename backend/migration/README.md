# folio-enrich → folio-resolve migration harness

Golden-baseline discipline for retiring folio-enrich's forked deterministic matcher
(`app/services/folio/search.py`, "ported from folio-mapper") in favor of the pinned
[`folio-resolve`](https://github.com/damienriehl/folio-resolve) library. See
`folio-resolve/docs/migration/SCHEDULE.md` row 2.

## What this is

- **`corpus.json`** — synthetic corpus (NO real matter data). Exercises the deterministic
  matching seams: exact/alias ruler matches, fuzzy + word-order-invariant label resolution,
  homonym traps (short labels: law/justice/state/tax/charge/action/trial), place/agency-prone
  generic terms, compound multi-head strings, and a nonsense proposed-class term.
- **`harness.py`** — runs the corpus through folio-enrich's CURRENT deterministic pipeline
  (`$0` LLM spend, no embeddings) and writes a capture. Three seams:
  1. `label_resolution` → `ConceptResolver.resolve` / `resolve_multi` (the `search.py` fork)
  2. `entity_ruler` → `FOLIOEntityRuler.find_matches`
  3. `reconciler` → `Reconciler.reconcile` (fixed synthetic inputs)
- **`compare.py`** — classified-delta comparator (intended-fix / regression / neutral) with the
  migration canaries. Writes `DELTA-REPORT.md` + `captures/delta.json`.
- **`captures/baseline.json`** — the committed Stage-0 golden baseline (pre-swap).

## Run

```bash
cd backend
# Stage 0 — baseline (pre-swap). Committed as captures/baseline.json.
.venv/bin/python migration/harness.py --out baseline

# Stage 1 — after wiring folio-resolve, recapture and diff:
.venv/bin/python migration/harness.py --out candidate
.venv/bin/python migration/compare.py --baseline baseline --candidate candidate
```

The corpus content hash is pinned into every capture; `compare.py` asserts the two captures
came from the same corpus. `compare.py` exits non-zero if a canary fails (a named recovery
dropped, or a NEW place/agency mis-map was introduced).

## Score-scale note (seam bug watch)

`multi_strategy_search` emits **0–100**; `ConceptResolver` divides by 100, so
`resolve().confidence` is **0–1**. The library's `LabelResolver` bar (`WHOLE_STRING_THRESHOLD =
92.0`) is on the **0–100** scale — normalize explicitly at the boundary when wiring. A `0.6`
threshold against a 0–100 score is a no-op bar (the original Ch02 defect #2).
