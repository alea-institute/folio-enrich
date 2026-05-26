---
title: "Fix 'Agreement' → 'License (Agreement)' concept-disambiguation precision error"
type: fix
status: active
date: 2026-05-26
origin: docs/brainstorms/2026-05-26-agreement-disambiguation-brainstorm.md
---

# 🐛 Fix "Agreement" → "License (Agreement)" Concept-Disambiguation Precision Error

## Enhancement Summary

**Deepened on:** 2026-05-26
**Research agents used:** kieran-python-reviewer, architecture-strategist, performance-oracle,
code-simplicity-reviewer, pattern-recognition-specialist, agent-native-reviewer,
best-practices-researcher, framework-docs-researcher.

### Key Improvements
1. **Phase 2 (the new stage) is now a HARD GATE, not a foregone build.** Research strongly
   suggests Part A (lemma reachability + index priority + DUPE filter) alone fixes the anchor.
   The eval set now runs *before* the stage and decides whether the stage is needed.
2. **Cross-tier embedding override DROPPED.** Selection is now deterministic and
   environment-invariant (DEV==PROD); embeddings break *within-tier* ties only and may never
   reverse a higher-tier rule match. (Revises brainstorm decision #2 — see "Decisions Revised".)
3. **Single source of truth for tier logic** (`match_tier` module) shared by Part A's index
   priority and Part B's ranking — prevents index/stage disagreement.
4. **Field-swap fixed at the source:** unify `_attach_backup_candidates` with `_to_resolved_dict`
   via a shared `_concept_to_dict()` helper so backups are shape-complete (fixes a latent
   metadata-loss bug, makes the "complete swap" automatic).
5. **Verified spaCy noun-lemmatization** works and is fast; added a mandatory pipe-presence guard.
6. **Performance contract:** lemmas computed once, disk-cached by `owl_hash+LEMMA_VERSION`,
   zero per-span spaCy calls, document-level embedding batching.

### New Considerations Discovered
- spaCy noun lemmatization silently degrades to lowercasing if `tagger`/`attribute_ruler` are
  ever disabled (W108 warning only) → must assert pipe presence.
- Legal **pluralia tantum / terms of art** ("damages"≠"damage", "proceedings", "minutes",
  "costs", "goods", "securities") must never be lemma-merged — biggest precision-regression risk.
- `contextual_rerank_enabled` defaults to **False** and BranchJudge only touches branch-less
  concepts → neither can undo a swap; invariant: *no post-Disambiguation stage may change `folio_iri`*.
- Lineage/decision rationale is currently serialized by **0 of 13 exporters** and dropped from
  SSE → agent-native observability gap to close if the stage is built.

---

## 🚦 Gate Result (2026-05-26)

**Part A alone fixed the anchor — Phase 3 (DisambiguationStage) was NOT built.**
After implementing Part A (lemma reachability + index priority + DUPE filter), the
eval set passes with embeddings disabled: `"Agreement"` resolves to Agreements
(`R88D8…`, `lemma_preferred`) at the index level **and** end-to-end through the
EntityRuler; `"License (Agreement)"` still maps to License; the DUPE concept is
filtered; legal terms of art stay distinct. Full suite: **723 passing, 0 regressions.**
Per the plan's gate, the in-place-mutation stage and embedding tiebreak are unnecessary
and were skipped. Remaining: **Part D** (upstream FOLIO data cleanup, separate repo).

## Overview

Input string **"Agreement"** is frequently resolved to FOLIO concept **"License (Agreement)"**
([`RKKRGOkIme6pnG2BSePt1Z`](https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z))
instead of the correct **"Agreements / Contracts"**
([`R88D8i8AcSTUig2X3yPbFHg`](https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg)).

Fix in four parts: **(A)** make concepts reachable from inflected surface forms via conservative,
ontology-sanctioned lemma normalization + index priority + DUPE filter; **(C)** an auto-discovered
collision eval set that **gates** **(B)** a new `DisambiguationStage` (built only if the eval shows
residual same-tier cross-primary collisions Part A can't resolve); and **(D)** upstream FOLIO data
cleanup. Decisions originate in the brainstorm
(see brainstorm: `docs/brainstorms/2026-05-26-agreement-disambiguation-brainstorm.md`).

> **Constraint:** DEV (Railway) + standalone PyInstaller builds run with **embeddings DISABLED**
> (`docs/HANDOFF-2026-05-25-demo-exemplars.md`). The rule hierarchy must fully fix "Agreement"
> without embeddings — which the revised design guarantees (selection is rules-only and
> environment-invariant; embeddings affect confidence + within-tier ties only).

---

## Problem Statement

Two compounding bugs (verified against live FOLIO data — 18,326 classes, 68,412 label keys):

1. **Reachability gap.** The label index lowercases but does **no** singular/plural normalization
   (`folio_service.py:222-392`). The correct concept's primary label is the **plural** "Agreements";
   the singular "Agreement" exists **only** as an alternative label on "License (Agreement)". So the
   singular surface form can *only* resolve to License.
2. **Disambiguation gap.** EntityRuler emits its only candidate (License); reconciliation keeps the
   only-present IRI; embedding conflict-triage never fires (needs two differing IRIs); search scoring
   rewards the *exact* alt-label match over the *plural* match.

**Secondary data issues:** the `"DUPE of License"` concept (`RCiAtR0akBA7apMyfjy515B`) also carries
"Agreement" and isn't filtered (class index filters only `owl:deprecated` + excluded branches; the
*property* index already does a `"DEPRECATED"/"ZZZ:"` string filter at `folio_service.py:419`).

**Why this is mostly an index-priority bug (research insight — simplicity + architecture reviewers):**
`get_all_labels` already lets `preferred` overwrite `alternative` for a key (`folio_service.py:246-275`).
Once lemma normalization maps "agreement" → the *primary* label "Agreements" **and** the priority map
ranks lemma-primary above exact-alt, the single-winner index prefers Agreements automatically — and
EntityRuler stops emitting License as the winner. The "locked-in early" symptom is a *consequence* of
the reachability gap, not an independent third bug.

---

## Technical Approach

### Phase 0 — Verification spike (GATE — do first)

- [ ] **Reachability (make-or-break):** with a draft lemma patch, assert against the real ontology
      that `get_all_labels_multi()["agreement"]` contains Agreements/Contracts, and that
      `resolve_multi("Agreement", max_candidates=5)` returns it. **If this fails, stop.** (A4)
- [ ] **spaCy noun-lemma guard (CRITICAL — framework research):** `en_core_web_sm` 3.8 lemmatizes
      nouns correctly with `disable=["ner","parser"]` *only because `tagger`+`attribute_ruler` remain*.
      Verified: `"Agreements"→"agreement"`, `"indices"→"index"`, `"attorneys"→"attorney"`. Add a
      runtime assertion that `{"tagger","attribute_ruler"} ⊆ nlp.pipe_names` OR a probe
      `nlp("Agreements")[0].lemma_ == "agreement"`; disabling the tagger silently degrades to
      lowercasing (only emits warning W108). Watch noun/verb homograph plurals ("leaves","minutes",
      "files") and `data→datum`.
- [ ] **Cost measurement:** lemmatizing the ~21k single-word label keys is **~1.7s @ batch_size=512**
      and yields only **~965 new keys (~1.4% map growth)** — not a doubling. Confirm on target hardware.
- [ ] **DUPE field inspection:** inspect `RCiAtR0akBA7apMyfjy515B` at runtime to find the marker field
      (`preferred_label` / `editorial_note` / `comment` / `deprecated`) so Part A filters the right field.

### Phase 1 — Reachability + index hardening (PART A)

**Files:** `app/services/folio/folio_service.py`; new `app/services/folio/match_tier.py`.

- [ ] **Shared tier module (architecture insight — single source of truth):** create
      `match_tier.py` with a `MatchTier(IntEnum)` and a pure `classify_match_tier(text, primary_label,
      alt_labels, lemma_fn) -> MatchTier`. **Both** Part A's index priority and Part B's ranking import
      it, so the index and the stage can never disagree on what "lemma-primary" means.
      ```python
      class MatchTier(IntEnum):  # higher wins
          LEMMA_ALT = 1; EXACT_ALT = 2; LEMMA_PRIMARY = 3; EXACT_PRIMARY = 4
      ```
- [ ] **Lemma map computed ONCE (performance insight):** lift `_compute_label_lemmas()` memoized on the
      service (`self._lemma_map`), consumed by **both** `get_all_labels` and `get_all_labels_multi` (do
      NOT lemmatize twice). Model on `property_matcher._compute_verb_lemmas` (`property_matcher.py:21-43`):
      `get_spacy_tokenizer()`, `" " not in l and len(l) > 3` input gate, **`len(lemma) > 2` output gate**,
      skip if `lemma == original` or already a key, `nlp.pipe(batch_size=512)`. Add a
      `logger.warning(exc_info=True)` on spaCy failure (don't silently return `{}`).
- [ ] **Disk cache (performance):** pickle the `{lemma: original}` map to
      `~/.folio-enrich/cache/lemmas/labels_{owl_hash}_v{LEMMA_VERSION}.pkl` (reuse
      `owl_cache.get_owl_content_hash()`). Cold start **<200ms** on hit, **<3s** on miss. `LEMMA_VERSION`
      bumps when lemma rules/denylist change (decouples from OWL content hash).
- [ ] **Priority ordering:** use `label_type` string values `"lemma_preferred"` / `"lemma_alternative"`
      (NOT a parallel `is_lemma` bool — pattern-recognition insight) so the single `_type_order` map stays
      authoritative. Extend it: `{preferred:0, lemma_preferred:1, alternative:2, lemma_alternative:3,
      hidden:4, translation:5}`. **Note:** `get_all_labels` does not use `_type_order` today (inline guard
      chains at `:259,270,280,295`) — refactor it to use the shared map (cleaner) and cover in
      `test_label_cache.py`.
- [ ] **Conservative, ontology-sanctioned normalization (best-practices insight):** only add a lemma key
      when it does NOT collide with a *different* concept's primary label. Never let normalization create
      a match the ontology doesn't sanction. Maintain a **legal pluralia-tantum / terms-of-art denylist**
      that is never lemma-merged: `damages, costs, proceedings, goods, arms, premises, savings, findings,
      securities, articles, minutes, holdings, pleadings, data` (extend from Phase 2 discoveries). (E3/A8)
- [ ] **DUPE/ZZZ filter:** mirror the property filter (`folio_service.py:419`) — substring check on the
      marker field (from Phase 0) — applied in **both** `get_all_labels` and `get_all_labels_multi`
      (separate caches). Keep existing `fc.deprecated` + `EXCLUDED_BRANCHES` guards.
- [ ] **Precompute candidate-label lemmas at build time** (perf) — store on `LabelInfo` / a side map
      `iri → {primary_lemma, alt_lemmas}` so Part B does O(1) lookups, **zero per-span spaCy calls**.
- [ ] **Cache + reload (G7):** `_reload()` must null/rebuild `self._lemma_map` and re-key its disk cache
      via recomputed `owl_hash`. Lemma changes must NOT invalidate the `owl_hash`-keyed embedding cache.

**Tests:** `tests/test_label_lemma_index.py` — lemma key present; "agreement"→Agreements; denylist
preserved (Damages≠Damage); DUPE filtered; lemma computed once; `_reload()` rebuilds.

### Phase 2 — Eval set + regression guard (PART C) → DECISION GATE

- [ ] **Auto-discover collisions:** scan the lemma-normalized label space for strings that are a primary
      label of one concept AND an alt/lemma label of a *different* concept; snapshot the set (A13). Mark
      as `@pytest.mark.integration` (live ontology); keep rule-logic tests on `FakeFolioService`.
- [ ] **Gold fixture:** flat `tests/test_disambiguation_eval.py` (no `tests/eval/` dir exists; keep flat
      — pattern insight) of `(input, sentence, expected_iri)` rows; anchor
      `("Agreement", <contract sentence>, R88D8i8AcSTUig2X3yPbFHg)`, negative `("License (Agreement)" → RKKR…)`.
- [ ] **Promote `FakeFolioService` into `tests/helpers.py`** (currently re-declared per file) for the
      overlapping eval/Phase-0/Phase-3 tests.
- [ ] **🚦 DECISION GATE:** run the eval with **embeddings disabled** (the DEV/standalone contract).
  - **If Part A passes the full eval → STOP. Ship Parts A + D.** The new stage is not needed.
  - **If residual same-tier cross-primary collisions remain → build Phase 3** scoped to *only* the
    multi-candidate re-selection path (no-op single-candidate concepts early).

### Phase 3 — `DisambiguationStage` (PART B) — *only if the gate requires it*

**New file:** `app/pipeline/stages/disambiguation_stage.py`. Built only on residual eval failures.

- [ ] **Structure (kieran insight):** thin `async execute`; extract pure, mockless functions:
      `classify_match(text, candidate, lemmatize) -> MatchTier` (reuse `match_tier`),
      `select_winner(candidates, *, tiebreak=None) -> (dict, MatchTier, decided_by)`. Rules path does no
      `await`. `name` is a `@property` (matches base ABC).
- [ ] **Strategy seam (architecture insight):** `RuleHierarchyRanker` (pure, deterministic, no I/O) +
      `EmbeddingTiebreakRanker` (only consulted on same-tier ties, holds embedding service). Makes
      "rules-only on DEV" a structural guarantee, not a runtime branch.
- [ ] **Insertion:** add to `build_pipeline_config.post_parallel` immediately after `ResolutionStage`,
      and mirror in `build_stages` (legacy). **Two authoring sites, not three** — `_run_flat` consumes
      `build_stages` output (architecture/pattern correction). Consider a shared `_build_post_parallel()`
      helper + a drift-alarm test. Place **before** the ContextualRerank block.
- [ ] **Read-only over `_backup_candidates`** (perf) — never re-run `resolve_multi`. Candidate set =
      `[rd] + rd["_backup_candidates"]`; mutate `resolved_concepts` in place.
- [ ] **Field swap via dict-level promotion (kieran/architecture/pattern convergence):** FIRST unify
      `_attach_backup_candidates` with `_to_resolved_dict` via a shared `_concept_to_dict(resolved, state)`
      in `resolution_stage.py` so backups carry the full ~22-field set (fixes a latent metadata-loss bug).
      Then promotion = replace primary dict with the winner dict, re-tag `state`, copy `iri_hash`
      (`iri.rsplit("/",1)[-1]` — reuse, don't recompute), demote old primary into `_backup_candidates`
      (no duplicate), preserve `_lineage_events`. (G1/G3/G4/A5/A6)
- [ ] **Multi-branch preservation (E1/A7):** operate only *within* a single concept's candidate/backup
      set; never collapse genuinely-distinct stacked annotations (different valid IRIs at one span).
      Respect `_dedup_overlapping_same_iri` (`string_match_stage.py:252-307`).
- [ ] **Embedding tiebreak — WITHIN-TIER ONLY (revised; best-practices + architecture):** only when top
      candidates are **same-tier** AND embeddings available (`index_size > 0`). Compare span sentence vs
      each candidate `folio_definition`. **No cross-tier override** — rules decide selection. Require an
      absolute floor (~0.3) AND a runner-up margin (≥0.05); else fall back to deterministic
      `_definition_overlap_score` (`reconciler.py:11-23`) → lowest IRI. all-MiniLM is L2-normalized
      (dot==cosine). **Batch at document level** (collect ties → one `encode()` for sentences; pull
      candidate-definition vectors from the existing cache by `iri_hash`). Reuse the 3-check guard from
      `resolution_stage.py:126-132`; reuse `EMBEDDING_AUTO_RESOLVE_THRESHOLD`; name any new margin
      constant distinctly.
- [ ] **Confidence + idempotency (kieran):** reset confidence to the promoted candidate's own value (no
      stale License-blended carry); guard with a `state`/`_disambiguated` marker so a second run is a true
      no-op (assert lineage-event count stable — A17).
- [ ] **Failure resilience (O7):** orchestrator continues on stage exceptions → narrow `try/except` around
      I/O (lemma/embedding) only + per-concept loop guard; degrade to rules-only/no-op + lineage note;
      never propagate, never a bare top-level catch that hides programming errors.
- [ ] **Lineage (pattern/agent-native):** append dict-form `_lineage_events`
      (`{stage:"disambiguation", action, detail, confidence}`) — NOT `record_lineage` (that's for
      Annotations). Add an `activity_log` summary row. Do NOT mutate `job.status` (follow ContextualRerank).
      Invariant to document: *no post-Disambiguation stage may change `folio_iri`*.
- [ ] **Config (agent-native):** `disambiguation_enabled`, `disambiguation_embedding_floor`,
      `disambiguation_embedding_min_delta`, `disambiguation_collision_max_candidates` on `Settings`
      (`FOLIO_ENRICH_` prefix) — no hardcoded module constants.

### Phase 3.5 — Observability (only if Phase 3 built; agent-native insight)

- [ ] Add structured `data: dict | None` to `StageEvent` (`annotation.py:9-15`) with
      `winning_tier, decision_path, demoted_iri, confidence_delta, candidates_considered, swapped`.
- [ ] Serialize `annotation.lineage` + concept `state` in SSE (`sse.py:54-59`) and in JSON/JSON-LD/JSONL/
      HTML exporters (currently 0/13 emit lineage) so an agent sees *why* a concept won, not just *that*.
- [ ] Per-job `metadata["disambiguation"]` summary (non-underscore → auto-exports); keep `stage`
      string stable for `FeedbackItem` targeting. Optional `GET /folio/collisions` endpoint (future).

### Phase 4 — Upstream FOLIO data cleanup (PART D — `alea-institute/FOLIO` repo)

- [ ] Re-home singular "Agreement" altLabel (remove from License; optionally add to Contracts/Agreements).
- [ ] Remove/deprecate the `"DUPE of License"` concept. Document that PROD picks up changes on
      `_reload()`/restart.

---

## Alternative Approaches Considered

- **Char-ngram fuzzy matching (scispaCy-style) instead of lemmatization.** The biomedical SOTA avoids
  lemmatization (handles plurals via char-3gram overlap, no over-merge risk). Stronger long-term, but a
  larger change to the matching layer; conservative ontology-sanctioned lemma normalization is the
  smaller, sufficient fix here. Noted as a future direction.
- **Full DisambiguationStage as committed v1 scope.** Rejected as *unconditional* — gated on eval
  (simplicity + architecture). The brainstorm's "new dedicated stage" remains the planned general-class
  mechanism; we just don't build the risky in-place-mutation stage until proven necessary.
- **Embeddings-first / cross-tier override.** Rejected (best-practices + architecture): embeddings can't
  pick a concept that isn't a candidate, are disabled on DEV, and cross-tier override risks reversing the
  fix on PROD. Selection stays deterministic.

---

## System-Wide Impact

### Interaction Graph
`DisambiguationStage` (if built) mutates `resolved_concepts` → `ContextualRerank` (**default-disabled**,
`config.py:84`) re-scores by `(text, new_iri)` → `BranchJudge` (only branch-less concepts) → `StringMatch`
**rebuilds** `annotations` from swapped dicts + re-indexes alt-label patterns → cross-linking stages → SSE
(`sse.py:51-66`) + 13 exporters. Neither Rerank nor BranchJudge can undo a swap.

### Error & Failure Propagation
Orchestrator `continue`s on stage exceptions (`orchestrator.py:522-529`) → stage must self-catch + degrade.

### State Lifecycle Risks
Partial swap leaks License metadata (fixed structurally by shape-complete backups). `iri_hash` copied not
recomputed. Demoted primary → backup, not duplicate. `annotation_removed` flicker if winning IRI changes
mid-stream (X2) — verify frontend treats as update.

### Integration Test Scenarios
1. Contract doc: "Agreement" → Agreements; License demoted. 2. SSE shows Agreements IRI+definition (+ why).
3. Exports (JSON/JSON-LD/RDF) show Agreements primary + License backup with `state`. 4. Multi-branch doc
still stacks. 5. Anchor identical with embeddings ON vs OFF (now a near-tautology given deterministic selection).

---

## Acceptance Criteria

### Phase 1 (always) — ✅ DONE
- [x] **A1** "Agreement" → `R88D8i8AcSTUig2X3yPbFHg`. *(test_disambiguation_eval: anchor)*
- [x] **A2** "License (Agreement)" still → `RKKRGOkIme6pnG2BSePt1Z`. *(anchor-negative)*
- [x] **A3** `get_all_labels_multi()["agreement"]` contains Agreements/Contracts, ordered first.
- [x] **A8** Denylist guards: damages/proceedings/minutes/costs not lemma-merged.
- [x] **A16** Lemma map computed once (memoized) + disk-cached; rebuilt on `_reload()`.
- [x] **A18** spaCy pipe-presence (tagger+attribute_ruler) asserted; lemma map disk-cached by owl_hash+version.
- [x] **A-dup** `RCiAtR0akBA7apMyfjy515B` ("DUPE of License") filtered from the label index.
- [x] Full suite green: 723 passing (689 default + 34 slow), 0 regressions.

### Phase 3 (DisambiguationStage) — ⏭️ SKIPPED (gate passed; Part A sufficient)
Not built. A4–A17/A-det only applied if the stage existed; the gate showed it doesn't.

---

## Decisions Revised From Brainstorm

1. **Embedding override scope (CHANGED).** Brainstorm: "embeddings can override low-confidence rule
   decisions (lemma-primary vs exact-alt)." **Revised:** embeddings break *within-tier* ties only and
   may **never** reverse a higher-tier match. Grounded in W3C-SKOS label semantics (prefLabel > altLabel),
   AML lexical-category weighting, and the architecture reviewer's environment-invariance argument. Net:
   selection is deterministic and identical on DEV/PROD; only confidence + genuine ties vary. This is
   *stronger* than the safeguard in the prior draft and removes the anchor-reversal risk entirely.
2. **Stage is gated, not foregone (CHANGED sequencing).** Brainstorm chose a "new dedicated stage." Still
   the planned general-class mechanism, but now built only if the eval shows Part A is insufficient.
3. **Conservative normalization tightened (new).** Ontology-sanctioned-only + legal-terms denylist
   (best-practices) — prevents the fix from *introducing* a new precision regression.

---

## Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Correct concept not reachable / not in top-5 | Phase 0 gate (A3/A4) |
| Lemma over-merge regresses legal terms of art | Ontology-sanctioned-only + denylist (A8) |
| spaCy silently degrades to lowercasing | Pipe-presence assertion / probe lemma (Phase 0) |
| Backup promotion loses metadata | Shape-complete backups via shared `_concept_to_dict` |
| Index vs stage tier disagreement | Shared `match_tier` module |
| DEV/PROD divergence | Deterministic selection; embeddings affect confidence/ties only |
| Stage built unnecessarily | Hard eval gate before Phase 3 |
| Decision invisible to agents | Structured lineage `data` + SSE/export serialization (Phase 3.5) |

---

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-05-26-agreement-disambiguation-brainstorm.md](../brainstorms/2026-05-26-agreement-disambiguation-brainstorm.md)

### Internal (file:line)
- Label index + `_type_order`: `app/services/folio/folio_service.py:222-392, 377, 419`, `_reload :104-130`
- Lemma pattern: `app/services/property/property_matcher.py:21-43` · spaCy: `app/services/nlp/spacy_singleton.py:38-52`
- Backups / context: `app/pipeline/stages/resolution_stage.py:29-97, 117-168`
- Resolver: `app/services/folio/resolver.py:53-57, 108-141` · Search tier signal discarded: `app/services/folio/search.py:210`
- Orchestrator (2 authoring sites): `app/pipeline/orchestrator.py:109-258`; continue-on-error `:522-529`
- Final emitter: `app/pipeline/stages/string_match_stage.py:138-165, 252-307`
- Embedding: `app/services/embedding/service.py:151-238` · Reconciler fallback/threshold: `app/services/reconciliation/reconciler.py:11-25, 149-307`
- Default flags: `config.py:75 (embedding_disabled), :84 (contextual_rerank_enabled=False), :116 (max_candidates=5)`
- SSE drops lineage: `app/services/streaming/sse.py:54-59` · Exporters omit lineage: `app/services/export/json_exporter.py:38-58`
- `StageEvent`: `app/models/annotation.py:9-15` · Tests: `tests/test_resolver.py`, `test_resolution_stage.py`, `test_reconciliation.py`

### External (best-practices / framework research)
- W3C SKOS Reference (prefLabel>altLabel>hiddenLabel): https://www.w3.org/TR/skos-reference/
- scispaCy (char-ngram, no-lemmatization): https://github.com/allenai/scispacy
- AML lexical-category weighting (label>synonym): https://link.springer.com/article/10.1186/s13326-017-0170-9
- spaCy Lemmatizer (rule mode needs tagger+attribute_ruler): https://spacy.io/api/lemmatizer
- all-MiniLM-L6-v2 (L2-normalized → dot==cosine; thresholds empirical): https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

### Deployment Constraints
- Embeddings disabled on DEV/Railway + standalone: `docs/HANDOFF-2026-05-25-demo-exemplars.md`
