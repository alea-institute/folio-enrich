---
title: "PR #14: Enable Canon — finish threading + per-ontology embeddings"
type: feat
status: completed
date: 2026-07-02
branch: feat/multi-ontology-enable-canon
origin: docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md
---

# Handoff — PR #14: Enable Canon (finish threading + per-ontology embeddings)

**Date:** 2026-07-02
**Branch:** `feat/multi-ontology-enable-canon` (off `main`, 1 commit pushed)
**Plan:** `docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md`
**Context:** Phases 1, 2a, 2b-security-core are MERGED to `main` (PRs #11, #12, #13) and deployed to DEV. This is the final piece to make Canon a correct, selectable ontology.

## Goal
Make a `?ontology=canon` job resolve/judge/extract against **Canon** everywhere (not FOLIO), then add `canon` to `enabled_ontologies`. Today Canon is *loadable* (hardened ingestion, PR #13) but **not enabled**, because several pipeline paths still resolve against the default (FOLIO) service — enabling now would resolve Canon docs against FOLIO. Keep FOLIO byte-neutral throughout (`job.ontology == "folio"` for all current jobs).

## Key facts (verified)
- Every stage gets `job` in `execute(job)`; `job.ontology` is a None-safe property (defaults `"folio"`). Resolve ontology services via `FolioService.get_instance(job.ontology)` (registry-keyed; one cached instance per ontology).
- Canon loads via the hardened path (`FolioService._load_http_via_hardened_ingestion`); `CANON_SPEC` has `owl_sha256` pinned. `enabled_ontologies=["folio"]` in `app/config.py` (add `"canon"` LAST, after the below).
- Registry: `get_registry().enabled_ids()/.get_spec()/.get_service()/.has()`.

## DONE (committed on branch)
- **ResolutionStage** — `resolution_stage.py execute()` rebinds `self.resolver.folio = FolioService.get_instance(job.ontology)`. This is the dominant resolution path (multi_strategy_search over `self.folio`).

## REMAINING — do these, keeping FOLIO green (786 tests)

### 1. Thread `job.ontology` through the remaining service call sites
All safe today (folio-only) but wrong once Canon is enabled:
- **branch_judge** — `app/services/concept/branch_judge.py:10` `_build_folio_context()` calls `FolioService.get_instance()` (no arg). Thread an `ontology_id`:
  - `_build_folio_context(concept_text, candidate_branches, ontology_id="folio")` → `get_instance(ontology_id)`.
  - `BranchJudge.judge(...)` (line 20) and `judge_batch(...)` call `_build_folio_context` — add `ontology_id` param, plumb through.
  - `branch_judge_stage.py:56` `self.judge.judge_batch(judge_items, document_type=...)` → pass `ontology_id=job.ontology`.
- **llm_property** — `app/services/property/llm_property_identifier.py:68,120` call `FolioService.get_instance()`. Add `ontology_id` to `LLMPropertyIdentifier.__init__(self, llm)` (line 28) → store `self._ontology_id`; use `get_instance(self._ontology_id)` at both sites. Construct with it in `property_stage.py:121` `LLMPropertyIdentifier(self.llm, ontology_id=job.ontology)`.
- **templates** — `app/services/llm/prompts/templates.py:57` `get_branch_detail()` uses `FolioService.get_instance()` + `get_folio_branches()` (FOLIO-branch-specific) and caches in the global `_BRANCH_DETAIL_CACHE`. Thread `ontology_id`, key the cache by ontology. For Canon, `get_folio_branches()` returns empty → it already falls back to `BRANCH_LIST`/`BRANCH_EXAMPLES` (FOLIO legal examples). Authoring **Canon `BRANCH_EXAMPLES`** (Scripture/Doctrine/Liturgy/Persons/Councils/Sacraments) is a quality nicety — can be minimal; graceful fallback works. Consumers: `concept_identification.py` passes it into the LLMConcept prompt.

### 2. Gate the embedding index by ontology (CRITICAL correctness)
The global `_embedding_index` (FAISS) + `EmbeddingService._instance` are **FOLIO's** (built from FOLIO at startup, `main.py _index_folio_embeddings`). A Canon job must NOT score Canon candidates against FOLIO vectors.
- Where used: `app/services/folio/search.py multi_strategy_search` (semantic search) and the **backup semantic filter** in `resolution_stage` (`backup_semantic_filter_enabled`, threshold 0.45) + branch-coherence bonus. Also `EmbeddingService.search_batch`.
- **Approach (simplest, safe):** tag the embedding index/service with the ontology id it was built for (e.g. `EmbeddingService._instance._ontology_id`, and a module attr on `_embedding_index`). In the resolver/backup-filter/multi_strategy_search, only use embeddings when `index_ontology == job.ontology`; otherwise skip (graceful degradation — identical to the DEV embeddings-disabled path, which already works). Per-ontology *building* of Canon's index is Phase 6 (PROD seeding); PR #14 just needs Canon to degrade gracefully, not use FOLIO's index.
- Verify: `get_embedding_index()` / `EmbeddingService.get_instance()` are the access points; thread `job.ontology` into `multi_strategy_search` (it currently takes `folio_raw`; add an `ontology_id` or an `embedding_service_or_none` that's None for non-matching ontology).

### 3. Enable Canon + config
- `app/config.py`: `enabled_ontologies: list[str] = ["folio", "canon"]`.
- Note: on first `?ontology=canon` request, Canon lazy-loads via the hardened path (~14 MB download + validate, one-time). Consider a warm note; not blocking.

### 4. Tests
- **IT-1 (concurrency / no leakage)** — the plan's exit gate: submit a FOLIO and a Canon resolution concurrently (or exercise both services) and assert no cross-contamination (Canon concepts have Canon IRIs `ontology.catholicos.catholic`/`webprotege.stanford.edu`; FOLIO has `folio.openlegalstandard.org`). Registry gives distinct cached services → should hold structurally.
- **Canon-resolves-against-Canon** — a Canon job's resolved concepts carry Canon IRIs, not FOLIO.
- **Embedding gating** — a Canon job with FOLIO's index loaded does NOT use it (mock/assert the backup filter is skipped for Canon).
- Keep the full suite green (786) + the slow Canon-load test.

### 5. Review + ship (per standing instruction: autonomous)
Run kieran-python + architecture (+ a quick perf pass on the embedding gating) on the diff; fix findings; merge; sync dev. Then Canon is API-selectable end-to-end. Phase 3 (frontend switcher) and Phase 4 (Canon demos + demo-slim + history rewrite) follow.

## Pointers
- Threading pattern reference: PR #12 (`git show` the entity_ruler/string_match/individual/property_matcher edits) — same `get_instance(job.ontology)` shape.
- Memory: `project_multi_ontology_canon.md` has the running status.
- Deploy: folio-enrich auto-deploys DEV from `main`; branch off `main` → PR → merge → `git checkout dev && git merge --ff-only main && git push`. Use the `damienriehl` gh account.
