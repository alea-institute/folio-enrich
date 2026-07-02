---
title: "Canon multi-ontology loose ends — embedding index, native branch prompts, infra hardening, PR triage"
type: feat
status: active
date: 2026-07-02
origin: docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md
---

# Canon multi-ontology loose ends

## Overview

The multi-ontology (Catholic Semantic Canon) feature shipped end-to-end (PRs #11–#20: registry → threading/security → switcher → demos → exports → polish/ACs, plus the git history rewrite, both PR-#17 follow-ups, and PROD deploy). All plan Definition-of-Done boxes are `[x]` and 841 tests are green. This plan captures the **four remaining, intentionally-deferred loose ends** so they can be picked up deliberately. None is a bug or a broken path — Canon is fully functional today; these raise *live* Canon quality and internal robustness.

Written from first-hand context (the same session that built the feature), so file anchors are current as of `main@7d150da`. **FOLIO byte-neutrality is a hard constraint for every item** (the guarantee that has held across all 20 PRs).

**Priority order (recommended):** WS-1 (biggest live-quality win) → WS-2 (visible prompt quality) → WS-4 (quick triage) → WS-3 (internal hardening, lowest urgency).

---

## WS-1 — Canon per-ontology embedding index

### Problem
Startup builds only **FOLIO's** embedding index (`backend/app/main.py:_index_folio_embeddings`, ~lines 27–49, called at lifespan). `EmbeddingService` is a single-index singleton tagged `_ontology_id="folio"`. A live `?ontology=canon` job therefore has `EmbeddingService.matches_ontology("canon") == False`, so the semantic stages **skip embeddings and degrade gracefully**:
- `resolution_stage._apply_embedding_context_scores` (backup semantic filter + 60/40 blend) — skipped.
- `reconciliation_stage` embedding triage — skipped (falls back to plain `reconcile`).
- `entity_ruler_stage` `SemanticEntityRuler` — skipped.

Result: live Canon resolution relies on EntityRuler (Aho-Corasick) + LLM + string-match only — good, but not at FOLIO parity. **Baked demos are unaffected** (they were baked and are served as-is).

### Approach
Build/seed a **Canon embedding index** so live Canon jobs score against Canon vectors. The bake pipeline already proved the mechanism (`backend/scripts/generate_demos.py:init_services(ontology)` → `FolioService.get_instance("canon")` + `embedding_service.index_folio_labels(canon_svc, ontology_id="canon")` + `build_embedding_index(canon_svc, ontology_id="canon")`).

The blocker is architectural: `EmbeddingService` holds **one** index. Two options:
- **(A) Registry-keyed embedding services (preferred, matches plan intent).** Move the embedding index/service under the per-ontology aggregate (plan line 133 "embedding-index registry keying") — `dict[ontology_id -> EmbeddingService]`, each tagged + cached on disk keyed by that ontology's OWL sha. `get_embedding_service(ontology_id)` returns the right one; the 3 gated stages request by `job.ontology` instead of checking `matches_ontology` on a global.
- **(B) Lazy per-ontology build behind the existing gate (smaller).** Keep the singleton pattern but make it a small `dict` and lazily build Canon's index on first Canon request (behind a per-key lock, like the registry). `matches_ontology` stays but consults the dict.

Prefer (A) — it also unblocks WS-3's shared-MiniLM ownership. Cache Canon vectors on disk under `~/.folio-enrich/cache/embeddings/all-MiniLM-L6-v2_labels_{canon_owl_sha}.pkl` + the FAISS `..._{sha}.pkl`, keyed by `CANON_SPEC.coords.owl_sha256` (pinned) so PROD startup loads from cache (no ~5-min rebuild outage; mirrors the FOLIO cache gotcha in `reference_prod_server`).

**Startup vs lazy:** do NOT eagerly build Canon's index at startup (it would add the Canon OWL download + a MiniLM pass to every boot, incl. FOLIO-only deploys). Build lazily on first Canon request (accepting a one-time first-request latency) OR seed the cache at deploy time (scp the `.pkl` like FOLIO). Document the choice.

### File anchors
- `backend/app/main.py:27-49,~146` — `_index_folio_embeddings` (FOLIO-only today).
- `backend/app/services/embedding/service.py` — `EmbeddingService` (`_ontology_id`, `matches_ontology`, `index_folio_labels(ontology_id)`), module `_embedding_index` + `build_embedding_index(ontology_id)`, `get_embedding_index`, disk cache `_load/_save_label_cache` keyed by owl_hash.
- `backend/app/services/ontology/registry.py` — per-key lock pattern to mirror; the natural home for `get_embedding_service(ontology_id)`.
- Gated consumers: `resolution_stage.py` (`_apply_embedding_context_scores`, gate on `matches_ontology`), `reconciliation_stage.py:~40`, `entity_ruler_stage.py:~181`.
- Bake reference: `backend/scripts/generate_demos.py:init_services` (working per-ontology build+tag).

### Acceptance criteria
- [ ] A live `?ontology=canon` job uses Canon embeddings (backup semantic filter + reconciliation triage + semantic ruler run against Canon vectors); FOLIO jobs use FOLIO's index unchanged.
- [ ] No cross-contamination: a Canon job never scores against FOLIO vectors and vice-versa (extend the existing `matches_ontology`/gating tests to the two-index world).
- [ ] Canon vectors cached on disk keyed by Canon OWL sha; a warm cache means no rebuild on restart.
- [ ] FOLIO-only deploys don't pay any Canon cost at startup.
- [ ] 841+ tests green; FOLIO embedding behavior byte-identical.

### Risks / notes
- Memory: two resident MiniLM indices (~18k FOLIO + ~15k Canon labels). Confirm RSS ceiling (plan line 250). Shared MiniLM model (one `SentenceTransformer`, two label matrices) keeps it bounded — ties to WS-3.
- PROD outage risk if the Canon index builds synchronously in lifespan → keep it lazy/off-startup.
- `sentence-transformers` must be present (now satisfied via `folio-python[search]`? no — that's search; embeddings need `sentence-transformers`, installed on PROD manually + still absent from `pyproject` — see WS-3 / the latent packaging gap in `reference_prod_server`).

**Effort:** M–L (the one architecturally-substantive item). **Deferred rationale:** graceful degradation already ships; needed only for live-Canon parity, and the flagship demos are pre-baked.

---

## WS-2 — Canon-native LLM branch prompts

### Problem
`backend/app/services/llm/prompts/templates.py:build_branch_detail(ontology_id)` looks up the right service but drives its loop from the module-global `FOLIO_BRANCHES` and falls back to `BRANCH_LIST` / `BRANCH_EXAMPLES`, which are **FOLIO's legal taxonomy**. So a Canon concept-identification prompt (`concept_identification.py:build_concept_identification_prompt`) and every `branch_judge` prompt (`branch_judge.py`) instruct the LLM to classify Catholic text into FOLIO legal branches (Actor/Player, Legal Authorities, Forums and Venues…). Documented + accepted in PR #14; the user chose "keep the FOLIO fallback per handoff." This is a *quality nicety*, not a correctness bug (Canon is a FOLIO-derived re-skin, so its real roots are literally named Event/Actor/Document — see `concept_detail` branch derivation — which is why it half-works).

### Approach
Give non-FOLIO ontologies their own branch examples so the LLM classifies with Canon-appropriate categories:
- **Derive from the Canon OWL** (preferred, self-maintaining): reuse the branch-root discovery already proven in `concept_detail._init_branch_roots` (roots via `sub_class_of == [owl#Thing]`; Canon → Event / Actor / Document + their notable children like Religious Events → Sacraments) to build a per-ontology branch-detail string, keyed/cached per ontology in `_BRANCH_DETAIL_CACHE` (already ontology-keyed).
- **Or author a static Canon `BRANCH_EXAMPLES`** (Scripture / Doctrine / Liturgy / Sacraments / Councils / Persons) as a spec-carried table — simpler, but hand-maintained.
- For non-FOLIO ontologies with no derivable branches, return a **neutral** scaffold (NOT FOLIO's `BRANCH_LIST`) so no cross-ontology taxonomy leaks — fixes the honesty gap flagged in the PR #14 review.

### File anchors
- `backend/app/services/llm/prompts/templates.py` — `build_branch_detail`, `get_branch_detail(ontology_id)` (cache already keyed by ontology), `FOLIO_BRANCHES`/`BRANCH_LIST`/`BRANCH_EXAMPLES`.
- Consumers: `concept_identification.py:build_concept_identification_prompt(text, ontology_id)`, `branch_judge.py:_build_folio_context/judge/judge_batch` (both already thread `ontology_id`).
- Root-derivation to reuse: `backend/app/services/folio/concept_detail.py` `_init_branch_roots` / `_get_branch_for_class`.
- `OntologySpec` (`spec.py`) — candidate home for a static `branch_examples` if not deriving.

### Acceptance criteria
- [ ] A Canon concept/branch-judge prompt presents Canon-appropriate branches (Event/Actor/Document + themes), NOT FOLIO legal branches.
- [ ] FOLIO prompts byte-identical (same `BRANCH_LIST`/detail).
- [ ] Non-FOLIO ontology with no branch data → neutral scaffold, never FOLIO's taxonomy.
- [ ] `templates.py` docstring updated to reflect reality (the current one now says the fallback is FOLIO — keep honest).
- [ ] A re-baked or live Canon job shows improved branch assignments (spot-check: "Eucharist" → a sacramental/liturgical branch, not "Actor / Player").

### Risks / notes
- If derived from OWL, needs the Canon service loaded (lazy — fine; `get_branch_detail` is already lazy + cached).
- Re-baking the 4 Canon demos to reflect better branches is OPTIONAL (costs a Gemini bake); live jobs benefit immediately. Note the trade-off.

**Effort:** S–M. **Deferred rationale:** explicitly accepted by the user; Canon's FOLIO-derived roots make the current output tolerable.

---

## WS-3 — Phase-1-deferred internal infra hardening

### Problem
`docs/plans/2026-07-01-002-...plan.md:133` deferred several non-user-facing infra items "to Phase 2 (need a live 2nd ontology to exercise/test)". With Canon now live, revisit:
- **shared-MiniLM singleton ownership** — ensure exactly one `SentenceTransformer` model instance is shared across ontologies' indices (memory ceiling, plan line 250). Ties to WS-1's two-index design.
- **build-then-swap OWL reload** — the OWL auto-updater (`owl_updater.py`) should build the new graph/index off to the side and atomically swap, so a reload never serves a half-built ontology. Also invalidate the ontology's own branch-detail cache on reload (the plan noted `_BRANCH_DETAIL_CACHE` staleness — now ontology-keyed, so clear the reloaded key).
- **lazy-Canon eviction** — bound resident ontologies (≤2 per plan line 250); evict the LRU non-default ontology's service+index under memory pressure.
- **per-ontology `owl_cache` parameterization** — `owl_cache.py` hardcodes the FOLIO cache file/URL; Canon loads via the hardened http path separately. Unify so each ontology has its own cache entry + freshness (the github-vs-http path mismatch was a Phase-0 phantom-rollback risk).
- **`app.state`/lifespan ownership** — move the registry/embedding services onto `app.state` rather than module globals for clean lifecycle + testability.

### File anchors
- `backend/app/services/embedding/service.py` (singleton), `backend/app/services/ontology/registry.py` (per-key lock, aggregate home), `backend/app/services/folio/owl_updater.py` + `owl_cache.py` (FOLIO-hardcoded), `backend/app/main.py` (lifespan).

### Acceptance criteria
- [ ] One shared `SentenceTransformer` across ontologies; measured RSS within ceiling with FOLIO+Canon resident.
- [ ] An OWL reload never serves a partially-built ontology; the reloaded ontology's branch-detail cache is invalidated.
- [ ] `owl_cache` is per-ontology (no FOLIO/Canon cache-key collision; no phantom rollback).
- [ ] Registry/embedding lifecycle owned by `app.state`; tests can construct/inject cleanly.
- [ ] FOLIO byte-neutral; 841+ tests green.

### Risks / notes
- Mostly refactors with subtle concurrency (locks, swap atomicity) — small, well-scoped diffs; verify with the existing IT-1 no-leakage test + a reload test.
- Lowest user urgency; do after WS-1/WS-2. WS-1 (registry-keyed embeddings) naturally absorbs the shared-MiniLM + app.state pieces.

**Effort:** M (spread across small PRs). **Deferred rationale:** internal robustness; no user-facing impact today.

---

## WS-4 — Triage open PR #4 (feat/pos-confidence-boost)

### Problem
PR #4 (`feat/pos-confidence-boost` → `main`, opened 2026-06-29: "POS-agreement confidence boosts, NER cross-validation & search precision") is unrelated to the ontology work and stale. Its base `main` was **rewritten** by the git history rewrite, so `mergeStateStatus` is `UNKNOWN` and a normal merge/rebase will conflict on history.

### Approach (decision, then execute)
1. **Assess relevance/quality** — does POS-agreement confidence + NER cross-validation still fit the current pipeline (POS confidence knobs already exist: `pos_confidence_enabled`, `pos_branch_affinity_boost`, `pos_property_mismatch_penalty`)? Is it superseded or complementary?
2. **If keep:** the branch predates the history rewrite, so **re-create it on current `main`** — cherry-pick its commits onto a fresh branch off `main@HEAD` (its old commits reference rewritten ancestors), resolve conflicts, re-open a clean PR. Do NOT try to merge the old branch directly.
3. **If obsolete/superseded:** close PR #4 with a note (and delete the branch) — record why in the memory.
4. Verify against current tests either way.

### File anchors
- Existing POS machinery to reconcile against: `branch_judge_stage.py` (`_apply_pos_branch_affinity`), `reconciliation_stage._apply_pos_penalties`, `property_stage._apply_pos_penalties`, `app/services/nlp/pos_lookup.py`, config `pos_*` settings.

### Acceptance criteria
- [ ] A decision is recorded (rebase-and-merge vs close) with rationale.
- [ ] If kept: a clean PR off current `main`, tests green, no history-rewrite conflicts.
- [ ] If closed: PR #4 closed + branch deleted + one-line memory note.

### Risks / notes
- The history rewrite means the old branch's commits sit on orphaned ancestry — cherry-pick, don't merge. Low effort either way.

**Effort:** S (triage) + S–M (if rebasing).

---

## Cross-cutting

- **FOLIO byte-neutrality** is required for WS-1/2/3 (the invariant across all 20 prior PRs) — assert via the existing FOLIO demo/export/branch-color/embedding tests.
- **Testing:** each WS extends existing suites; WS-1 adds a two-index no-leakage test, WS-2 a Canon-branch-prompt assertion, WS-3 a reload/atomicity test.
- **Deploy:** DEV auto-deploys from `main`; PROD now current (`7d150da`) — after each WS, PROD picks it up on its next deploy. Watch the embedding cache gotcha (`reference_prod_server`) for WS-1.
- **Packaging gap (adjacent):** `sentence-transformers` is used by default local embeddings but still absent from `backend/pyproject.toml` (installed manually on PROD). Worth folding into WS-1 (add it, gate `faiss`/torch weight consciously) — but it's a real dependency-footprint decision (torch), so surface before adding.

## Sources & References

- **Origin plan:** [docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md](2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md) — deferred items at line 133; DoD (all `[x]`) at 236–256.
- Shipped: PRs #11–#20 (registry, threading, security, enable, switcher, demo-slim, Canon demos, hierarchy fix, search extra, polish). Memory: `project_multi_ontology_canon.md`.
- Reference: `reference_prod_server.md` (embedding-cache gotcha, uv-managed venv, sentence-transformers gap).
- Related: PR #4 `feat/pos-confidence-boost`.
