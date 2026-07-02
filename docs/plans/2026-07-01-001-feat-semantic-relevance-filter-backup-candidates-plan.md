---
title: Semantic-relevance filtering of backup (runner-up) candidates
type: feat
status: completed
date: 2026-07-01
---

# ✨ Semantic-relevance filtering of backup candidates

> **Handoff plan — written to be implemented in a fresh context window.** It is self-contained:
> all needed file paths, function names, prior measurements, decisions, and gotchas are inline.
> `NEVER-CODE` was in effect when writing this; nothing here has been implemented yet.

## Overview

The resolution stage attaches **backup (runner-up) candidates** to each concept — alternative
FOLIO concepts shown behind an "Alternatives" toggle in the span tooltip / detail panel. Real
output shows these are **mostly noise**: FOLIO labels that merely share a word with the query
(e.g. `Court` → "Court Costs", "Missouri Circuit Court - Dade County"; `Non` → "Non-Human
Authorship"). This plan adds an **embedding-based semantic-relevance filter** that keeps only
backups actually related to the mention's context, and drops the noise — the one thing the
existing search score cannot do.

This is a **quality** improvement (better alternatives), not primarily a perf one — the expensive
backup *search* was already addressed. It adds negligible latency (one batched embedding pass).

## Problem Statement

- Backups come from `ConceptResolver.resolve_multi()` → `_multi_strategy_resolve_all()` →
  `multi_strategy_search()`. Their `confidence` is the raw search score / 100.
- **The search score does not separate signal from noise.** A substring/token match like
  "Non-Human Authorship" for the query "Non" scores ~0.95 — the same as a genuinely relevant
  match. So a *score* threshold cannot filter the junk. (Verified this session.)
- Genuinely useful alternatives DO occur but are buried: `Court` → **"Court Forum"** (a better
  branch than the mis-branched primary "Courts [Industry]"); `plaintiff` → **"Counter-Claimant"**.
- **What CAN separate them:** embedding similarity between the mention's *context* and each
  backup's *definition/label* — the same signal the primary already uses in
  `_apply_embedding_context_scores` (sentence-vs-definition, blended 60/40).

## Prior work this builds on (already merged & deployed — `main` at `71b8dd0`)

- **PR #7** — resolution search-cache + batched embedding-context.
- **PR #8** — (A) skip backup search for concepts with a definitive exact FOLIO IRI
  (`settings.skip_backups_for_exact_matches`, default `true`); (B) cap each backup's confidence at
  the primary's (`min(alt.confidence, primary_conf)`).
- **Net effect: backups now only exist for genuinely ambiguous, fuzzy-resolved concepts (no exact
  IRI).** That is exactly the population where good alternatives matter — and the set this filter
  operates on is now small.
- Prior handoff with full measurements: `docs/HANDOFF-2026-07-01-backup-candidates-optimize.md`.

## Proposed Solution

Add a **post-pass** over all resolved concepts that, using the EmbeddingService, scores each
backup candidate's semantic relevance to its mention's sentence context and drops backups below a
threshold. Batch every (context, backup-text) pair into **one** `similarity_batch()` call so cost
stays negligible. **No-op** when embeddings are unavailable (never drop backups you can't score).

Recommended: fold this into the existing `_apply_embedding_context_scores` pass so the primary
blend and the backup filtering share one sentence-context computation and one embedding batch.

## Technical Approach

### Key files & anchors (grep by function name — line numbers drift)

- `backend/app/pipeline/stages/resolution_stage.py`
  - `_attach_backup_candidates()` (~L61) — builds each backup dict:
    `{concept_text, folio_iri, folio_label, folio_definition, branches, branch_color, confidence, source, state:"backup", iri_hash, folio_alt_labels}`. Backups land on `rd["_backup_candidates"]`.
  - `_apply_embedding_context_scores(resolved_concepts, full_text)` (~L126) — **the pattern to mirror**:
    early-returns if `self._embedding_service is None` or `index_size == 0`; extracts the mention's
    sentence context via `full_text.lower().find(concept_text)` then nearest periods; builds
    `(sentence, definition)` pairs; calls `self._embedding_service.similarity_batch(pairs)`; wraps in
    try/except (returns on failure). **Reuse the sentence-context extraction verbatim.**
  - `execute()` calls `self._apply_embedding_context_scores(resolved_concepts, full_text)` (~L264),
    right before `job.result.metadata["resolved_concepts"] = resolved_concepts`. New logic goes here.
- `backend/app/services/embedding/service.py`
  - `similarity_batch(pairs: list[tuple[str,str]]) -> list[float]` (~L229) — one forward pass for all pairs.
  - `_top_k_indices`, `search_batch`, `similarity` also available.
- `backend/app/services/folio/resolver.py`
  - `_multi_strategy_resolve_all()` (~L143) builds backup FOLIOConcepts; `definition` may be `""`.
- `backend/app/pipeline/stages/string_match_stage.py` (~L166) — consumes `_backup_candidates` into
  `ConceptMatch(state="backup")` on annotations (→ UI "Alternatives"). **No change needed** if we
  only prune/re-score the list in `_backup_candidates`; verify the shape stays identical.
- `backend/app/config.py` — `max_candidates: int = 5` (~L124); `skip_backups_for_exact_matches` (added PR #8).

### Config (add near `max_candidates`)
```python
backup_semantic_filter_enabled: bool = True
backup_semantic_relevance_threshold: float = 0.45   # TUNE — see tuning harness below
```

### Algorithm (recommended: unified with the primary embedding pass)
Rewrite `_apply_embedding_context_scores` (or add a sibling that runs adjacent) so it, in one pass:
1. Early-return no-op if embedding service missing / `index_size == 0` (existing guard). **Critical:
   when embeddings are unavailable, backups pass through UNCHANGED — do not drop them.**
2. For each resolved concept `rd`:
   - Compute the mention's sentence context once (existing logic).
   - Queue the **primary** pair `(sentence, rd["folio_definition"])` (for the existing 60/40 blend).
   - For each backup in `rd.get("_backup_candidates", [])`: queue `(sentence, backup_text)` where
     `backup_text = backup["folio_definition"] or backup["folio_label"]`. Track which pairs belong
     to which backup.
3. One `similarity_batch(all_pairs)` → sims (wrap in try/except → return/no-op on failure).
4. Apply primary blend exactly as today (unchanged).
5. For each concept, filter `_backup_candidates` to those with `sim >= threshold`. **Decision (see
   Open Questions):** for survivors, set `confidence = min(sim, primary_conf)` and sort by `sim`
   desc, so the Alternatives list is ordered by genuine relevance and honestly scored (still ≤
   primary, preserving PR #8's cap). If `_backup_candidates` becomes empty, remove the key.

### Pseudocode sketch (illustrative — implementer refines)
```python
# resolution_stage.py — inside/after the existing embedding-context pass
def _apply_embedding_context_scores(self, resolved_concepts, full_text):
    if self._embedding_service is None: return
    try:
        if self._embedding_service.index_size == 0: return
    except Exception:
        return

    pairs = []                      # flat list for one batch
    plan = []                       # (rd, kind, backup_ref_or_None, sentence)
    for rd in resolved_concepts:
        sentence = self._sentence_context(full_text, rd.get("concept_text",""))  # extract to helper
        definition = rd.get("folio_definition") or ""
        if definition:
            plan.append((rd, "primary", None)); pairs.append((sentence, definition))
        if settings.backup_semantic_filter_enabled:
            for bc in rd.get("_backup_candidates", []) or []:
                text_b = bc.get("folio_definition") or bc.get("folio_label") or ""
                if text_b:
                    plan.append((rd, "backup", bc)); pairs.append((sentence, text_b))

    if not pairs: return
    try:
        sims = self._embedding_service.similarity_batch(pairs)
    except Exception:
        return

    kept = {}   # id(rd) -> surviving backups (with new conf)
    for (rd, kind, bc), sim in zip(plan, sims):
        sim = max(0.0, min(1.0, sim))
        if kind == "primary":
            # existing 60/40 blend + lineage (unchanged)
            ...
        else:  # backup
            if sim >= settings.backup_semantic_relevance_threshold:
                bc = dict(bc); bc["confidence"] = min(sim, rd.get("confidence", 1.0))
                kept.setdefault(id(rd), []).append((sim, bc))

    if settings.backup_semantic_filter_enabled:
        for rd in resolved_concepts:
            survivors = kept.get(id(rd))
            if survivors is None:
                # only clear if the concept HAD backups and none survived AND embeddings ran
                if rd.get("_backup_candidates"):
                    rd.pop("_backup_candidates", None)
            else:
                survivors.sort(key=lambda t: t[0], reverse=True)
                rd["_backup_candidates"] = [bc for _, bc in survivors]
```
> Watch the empty-vs-missing distinction: a concept with backups where *none* survive should end
> with `_backup_candidates` removed; a concept that never had backups is untouched.

## Alternative Approaches Considered

1. **Embedding similarity of context-vs-definition (CHOSEN)** — reuses existing infra, batched,
   negligible cost, and is the only signal that separates the noise. ✅
2. **Threshold on the multi_strategy search score** — REJECTED: verified this session the score
   does not separate signal from noise (junk scores ~0.95 like real matches).
3. **LLM re-rank of backups** — REJECTED: adds latency + an LLM dependency for an on-demand
   alternatives list; overkill. (Could be a future "explain alternatives" feature, not this.)
4. **Structural heuristics** (drop backups that merely contain the query as a substring, or whose
   label is far longer than the mention) — cheap and could complement the semantic filter as a
   pre-pass, but brittle alone. Optional add-on; not required.
5. **Just lower `max_candidates` / drop backups entirely** — REJECTED: the goal is to KEEP the
   useful alternatives (Court Forum, Counter-Claimant), not remove them.

## System-Wide Impact

- **Interaction graph:** `ResolutionStage.execute` → embedding pass (now also filters
  `_backup_candidates`) → `metadata["resolved_concepts"]` → `StringMatchStage` (~L166) materializes
  survivors as `ConceptMatch(state="backup")` → SSE `annotation` events → frontend "Alternatives".
  Only `_backup_candidates` content changes; the dict shape and downstream code are untouched.
- **Error propagation:** any embedding failure → no-op (backups unchanged), same as the primary
  blend today. Never raises into the pipeline.
- **State lifecycle:** pure in-memory transform of `resolved_concepts` before persistence; no
  partial-state risk.
- **API surface parity:** backups also flow to exporters via annotations — pruning is transparent
  (fewer/renumbered alternatives). Confirm no exporter assumes a fixed backup count.
- **Precision/recall of PRIMARY annotations: unchanged** — this only prunes/re-scores the
  alternatives list. Validate the primary annotation count + IRIs are identical before/after.

## Acceptance Criteria

### Functional
- [x] Noise backups are dropped: below-threshold backups (unit-tested via `test_drops_below_threshold_keeps_above`, `test_all_below_threshold_removes_key`) are removed. *(Validate real "Court Costs"/circuit-court examples via the harness on PROD.)*
- [x] Relevant alternatives are retained: above-threshold backups survive (`test_drops_below_threshold_keeps_above`). *(Validate "Court Forum"/"Counter-Claimant" via the harness on PROD.)*
- [x] Surviving backups are ordered by semantic relevance and each has `confidence ≤ primary`
      (preserves PR #8's cap) — `test_survivors_sorted_by_sim_and_capped_at_primary`.
- [x] Concepts whose backups all fall below threshold end with **no** `_backup_candidates` — `test_all_below_threshold_removes_key`.
- [x] **No-op when embeddings unavailable** (service `None` or `index_size == 0`): all backups pass
      through unchanged — `test_noop_when_no_embedding_service`, `test_noop_when_index_empty`, `test_noop_on_similarity_exception`.
- [x] Toggle off via `FOLIO_ENRICH_BACKUP_SEMANTIC_FILTER_ENABLED=false` restores prior behavior — `test_disabled_leaves_backups_unchanged`.

### Non-Functional
- [x] Resolution latency delta negligible — folded into the existing single `similarity_batch()` pass (no extra forward pass; the batch is just larger). *(Measure warm & cold on PROD.)*
- [x] Primary annotation count + IRIs identical before/after — filter only touches `_backup_candidates`; the primary 60/40 blend is byte-for-byte unchanged (`test_concept_without_backups_untouched` + existing `TestApplyEmbeddingContextScores`).

### Quality Gates
- [x] New unit tests pass; full suite green (741 passed, 38 deselected — was 732).
- [ ] Threshold tuned against real captured examples — harness `backend/scripts/tune_backup_semantic_filter.py` added; **run on PROD** (needs `sentence-transformers`). Shipping the documented default `0.45` (runtime-tunable via `FOLIO_ENRICH_BACKUP_SEMANTIC_RELEVANCE_THRESHOLD`).

## Testing (`backend/tests/test_resolution_stage.py`)

Add `TestSemanticBackupFilter` (mirror `TestApplyEmbeddingContextScores` — mock the embedding
service, no FOLIO load):
- Mock `embedding_service.similarity_batch.side_effect` to return per-pair sims by looking at the
  pair contents (e.g. return 0.8 for the "relevant" definition, 0.2 for "noise") so you can assert
  filtering deterministically.
- Tests:
  - drops backups below threshold, keeps those above;
  - survivors sorted by sim desc, `confidence ≤ primary`;
  - all-below-threshold → `_backup_candidates` removed;
  - **no-op when `embedding_service is None` and when `index_size == 0`** (backups unchanged);
  - `backup_semantic_filter_enabled=false` → backups unchanged;
  - primary 60/40 blend still applied (don't regress the existing behavior — keep/adapt the
    current `TestApplyEmbeddingContextScores` mocks, which now mock `similarity_batch`).
- Note: `test_resolution_stage.py` tests are NOT `@pytest.mark.slow` and run by default; keep it
  that way (mock, don't load embeddings).

## Tuning & measurement harness (do BEFORE finalizing the threshold)

1. **Force backups on any doc for tuning:** temporarily run PROD/local with
   `FOLIO_ENRICH_SKIP_BACKUPS_FOR_EXACT_MATCHES=false` so exact-match concepts also get the noisy
   backups (the very examples we want to filter). Restore to `true` after tuning.
2. **Capture sims:** run the NDA test doc (below) and print, per backup, the
   `similarity(sentence, backup_definition_or_label)` — see where "Court Forum" vs "Court Costs"
   land. Pick a threshold that keeps the good ones and drops the junk (start ~0.45; adjust).
3. **Measure latency** before/after via the SSE activity-log `resolution` delta (see prior
   handoffs for the exact `curl … /stream` + python timing snippet). Expect negligible change.
4. **To exercise the REAL path** (backups only on ambiguous concepts) use text with near-miss /
   paraphrased terms that won't exactly match FOLIO labels, forcing fuzzy resolution (no exact
   IRI). Confirm those concepts get backups and that filtering behaves.

### Test doc (exact-match heavy — use with skip=false for tuning)
"This Non-Disclosure Agreement is entered into between Acme Corporation and John Smith. The parties
agree that confidential information shall not be disclosed. The Court shall have jurisdiction over
any dispute arising under this contract. The plaintiff filed a motion to dismiss. Damages may be
awarded for breach."

## Dependencies & Risks

- **No new dependencies.** Uses the existing EmbeddingService (`sentence-transformers` on PROD;
  absent on DEV/Railway → filter no-ops there, which is fine).
- **Risk: threshold too high → drops useful alternatives (recall of alternatives).** Mitigate via
  the tuning harness + validating the known-good examples (Court Forum, Counter-Claimant).
- **Risk: definitions missing** for some backups → fall back to label; verify similarity on labels
  is still meaningful (labels are short; consider comparing mention-vs-label as a fallback).
- **Risk: exporter assumes fixed backup shape/count** — low; shape unchanged, only list length. Grep
  exporters for `_backup_candidates` / `state == "backup"` to confirm.

## Rollout

Branch off `main` → PR → merge → deploy to PROD (`git pull` + `sudo -n systemctl restart
folio-enrich`; home IP allowlisted; see `docs/HANDOFF-2026-07-01-backup-candidates-optimize.md` for
the exact SSH one-liner) → measure → sync `dev` (`git checkout dev && git merge --ff-only main &&
git push origin dev`) → delete branch. Instant rollback: set
`FOLIO_ENRICH_BACKUP_SEMANTIC_FILTER_ENABLED=false` (no deploy).

## Sources & References

### Internal
- `backend/app/pipeline/stages/resolution_stage.py` — `_attach_backup_candidates`,
  `_apply_embedding_context_scores`, `execute` (call site).
- `backend/app/services/embedding/service.py` — `similarity_batch`.
- `backend/app/services/folio/resolver.py` — `_multi_strategy_resolve_all` (backup source).
- `backend/app/pipeline/stages/string_match_stage.py:~166` — backup → annotation.
- `backend/app/config.py` — `max_candidates`, `skip_backups_for_exact_matches`.

### Related work (this project, this cycle)
- PR #5 (stream deterministic tags), #6 (semantic-ruler perf), #7 (resolution search-cache +
  batched embedding-context), #8 (skip backups for exact matches + cap confidence).
- `docs/HANDOFF-2026-07-01-backup-candidates-optimize.md` — contains the real backup-quality data
  (noise examples + the useful outliers) and PROD measurement snippets.

### Real backup data motivating this (from the prior handoff / this session)
```
Court  -> Courts [Industry]  |  backups: Family Court, Missouri Circuit Court - Dade County,
                                Indiana Circuit Court - Jennings County, Court Forum, Court Costs
plaintiff -> Plaintiff       |  backups: Counter-Claimant (useful), Plaintiff Case-in-Chief,
                                Plaintiff's Felonious Conduct, Comparative Fault of Plaintiff
Non -> Non-binary            |  backups: Non-Billable, Non Waiver Clause, Non-Human Authorship, ...
```
Target: keep **Court Forum** and **Counter-Claimant**; drop the rest.

## Open Questions (RESOLVED during implementation)

1. **Threshold value** — shipped the documented default `0.45`, runtime-tunable via
   `FOLIO_ENRICH_BACKUP_SEMANTIC_RELEVANCE_THRESHOLD`. Local venv lacks `sentence-transformers`, so
   the real-sim harness (`backend/scripts/tune_backup_semantic_filter.py`) must run on PROD; capture
   its output there and adjust the env override without a redeploy.
2. **context-vs-definition** — chosen; falls back to `folio_label` when a backup has no definition
   (`text_b = bc["folio_definition"] or bc["folio_label"]`), consistent with the primary blend.
3. **Re-score + re-sort by sim** — chosen; survivors get `confidence = min(sim, primary_conf)` and
   are sorted by sim desc, so the Alternatives list is honestly scored (≤ primary) and ordered.
4. **Folded into `_apply_embedding_context_scores`** — chosen; primary blend and backup filtering
   share one sentence-context computation and one `similarity_batch()` call. Sentence-context
   extraction pulled into a `_sentence_context()` static helper reused by both.
