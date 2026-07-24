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

---

# Stage 2 (2026-07-24) — the `search.py` retirement question

Stage 1 (2026-07-16) retired the *forked scorer*: `SEARCH_STOPWORDS`, `LEGAL_TERM_EXPANSIONS`,
`compute_relevance_score`, `generate_search_terms`, `tokenize` / `content_words`, plus the
`PlaceNameGate` + `AliasBlocklist` precision gates and `LabelResolver` as the primary resolution
path, all now come from the pinned library. What is left in `app/services/folio/search.py` is
**not a fork of library code** — it is folio-python recall orchestration, the category
folio-mapper's migration explicitly classified as "ontology-shaped code stays".

## Stage-0 discipline for this stage (committed BEFORE any swap)

- `harness.py` now **re-executes itself under `PYTHONHASHSEED=0`** (folio-mapper's fix for
  `generate_search_terms`' set-iteration order). Verified: two seeded runs of unchanged code
  produce byte-identical captures.
- Two new seams isolate the question:
  - **`search_fork`** — `multi_strategy_search` called directly (0-100 scores), so a change to
    the fork's internals is visible even when the library primary masks it at the resolver.
  - **`library_only`** — the same corpus resolved with `ConceptResolver._fork_resolve_all`
    stubbed out. **Seam 1 minus seam 5 is exactly what deleting `search.py` would cost.**
- Two new canaries in `compare.py`: **candidate recall** (no term's ranked set may shrink) and
  **fork parity** (`search_fork` top-1 may not move without `--expect-changes`).
- Baseline: `captures/stage2-baseline.json` (Stage 1's `baseline.json` / `candidate.json` are
  left untouched as that stage's signed-off evidence).

## Measured verdict: the fork cannot be deleted, and it cannot be swapped yet

| Question | Evidence from `captures/stage2-baseline.json` |
|---|---|
| Does the library primary still need the fork to be *correct*? | **No.** `LabelResolver` + gates resolve the right primary on **24/24** corpus rows; the library-only primary is identical on every row. |
| Does the fork still carry *recall*? | **Yes, overwhelmingly.** The ranked candidate set (`resolve_multi`, what the UI, the reconciler and every multi-candidate consumer read) collapses **120 → 15 (−87.5%)** without it, and **24/24** terms shrink. |
| Would the canaries catch a naive deletion? | **Yes** — replaying a simulated "fork deleted" capture fails both new canaries and exits non-zero (`terms_shrunk: 24`, `top1_moved: 24/24`). |

So `search.py` is retired **when the library can gather candidates**, not before. Its remaining
284 lines break down as:

| Part | Lines | Status |
|---|---|---|
| Docstring, imports, `PlaceNameGate` / `AliasBlocklist` wiring, `candidate_vetoed` | ~80 | **already the library** |
| Phase 1 — 7-strategy candidate gathering (`search_by_label`, `search_by_prefix`, stem prefix, `search_by_definition`) | ~78 | folio-python; **no library equivalent** |
| Phase 2 — re-score every raw candidate | ~15 | calls the library scorer; the loop is local |
| Phase 2.1 — expansion re-scoring (`LEGAL_TERM_EXPANSIONS` compounds re-scored against every candidate) | ~35 | generic, **liftable**, not yet in the library |
| Phase 2.5 — ancestor surfacing (walk `sub_class_of` up to depth 3, decay 0.85^depth) | ~22 | needs a parent-lookup seam the library's `OntologyProvider` does not have |
| Phase 3 — branch filter (`EXCLUDED_BRANCHES`), gates, branch colors, result dicts | ~42 | enrich-specific presentation + the library gates |

## What a real retirement needs (library work, not consumer work)

`folio_resolve.OntologyProvider` exposes only `all_labels` / `search_by_label` / `get_concept`.
A recall engine needs more. Concretely, the library would grow:

1. **A `RecallOntology` protocol** — `search_by_prefix`, `search_by_definition`, and
   `parents_of(iri)` alongside today's `search_by_label`, with `FolioPythonProvider` implementing
   it and `InMemoryOntology` backing the tests.
2. **A `MultiStrategyRecall` engine** — Phase 1 gathering + Phase 2/2.1 re-scoring + Phase 2.5
   ancestor surfacing, returning scored candidates. This is the generic half of `search.py` and
   folio-mapper's `search_candidates` at once, so it retires **two** forks, not one.
3. **A release.** PyPI still only has `folio-resolve 0.1.0`; 0.2.0, 0.2.1 and 0.3.0 are all
   committed-but-unpublished. Everything above would ride the same release.

Until then, wiring the swap would mean vendoring the engine back into enrich — the opposite of a
retirement — so Stage 2 stops at the baseline and the scope note. The Stage-2 canaries are live
and will gate the swap the day the library can take it.

## Second fork found (not swapped, deliberately)

`app/services/matching/aho_corasick.py` **is** a true duplicate: the library's
`folio_resolve.matching.AhoCorasickMatcher` is a same-contract reimplementation of it
(`MatchResult`, word-boundary checks, containment-aware overlap resolution). Swapping it is
blocked on the same release for a different reason: enrich's copy is backed by the compiled
`pyahocorasick` C extension, the library's is pure Python, and the pure-Python
`_resolve_overlaps` in the published **0.1.0** is the O(m²) version the ruler shootout flagged
(throughput decays 531K → 79K chars/s at ×7 corpus size). The O(m log m) active-interval sweep
landed in the library *after* 0.1.0. The swap is worth doing on ≥ 0.2.0 with a throughput
measurement on `string_match_stage`'s real 69K-pattern index — it is a decision about a speed
trade, so it wants Damien, not a lane.
