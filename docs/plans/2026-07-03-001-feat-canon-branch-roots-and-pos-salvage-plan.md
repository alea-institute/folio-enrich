---
title: "Canon branch-root fix + POS/search salvage — implicit roots, search substring penalty, NER cross-validation"
type: feat
status: completed
date: 2026-07-03
outcome: "Shipped WS-A #25 (implicit roots → Canon 3→7 roots, Place), WS-B #26 (search substring penalty), WS-C #27 (NER cross-val, default-off), WS-D #28 (branch-label unify), re-bake #29 (7-root demos). Deployed PROD (1fdbf8e). RESIDUAL: Normative root still splits full/stripped from the LLM branch-guess fallback (resolver.py:78) → WS-E follow-up: snap LLM branch strings to canonical root labels. NER pending eval-set validation before enabling. Christian Concepts = external (D'Orazio must publish OWL)."
origin: docs/plans/2026-07-02-001-feat-canon-loose-ends-plan.md
---

# Canon branch-root fix + PR-#4 salvage

## Overview

Three workstreams, discovered while triaging the WS-4 PR-#4 salvage (`project_pr4_pos_triage`) and surfaced by a user correction on Canon's real branch structure:

- **WS-A (bug fix, linchpin):** Canon's LLM branch prompts (WS-2, PR #22) and concept-branch assignments only expose **3 of Canon's 7 published roots**. Root cause: `concept_detail._init_branch_roots` discovers roots via `sub_class_of == [owl#Thing]` only, silently dropping the **6 implicit roots** (classes with *no* `subClassOf`). Canon's real published roots are Actor, **Authority (Source and Scope)**, Document / Artifact, Event, **Normative Concepts**, **Operational Concepts**, **Place** (+ `ZZZ - Licensing` / `ZZZZ - Deprecated`, which must be excluded). This is why "Bethlehem" mis-bucketed to Document/Artifact instead of Place.
- **WS-B (salvage):** search substring scoring returns a flat `85.0` regardless of coverage (`search.py:164`), so `"Amended Complaint"` scores 85 against `"Motion to File Amended Complaint"`. Port the coverage-ratio + word-count penalty from PR-#4 commit `faa8dcc`.
- **WS-C (salvage):** no NER cross-validation exists on `main`. Port spaCy-NER cross-check from PR-#4 commit `50beecc`, with **per-ontology affinity maps** (FOLIO + Canon), default-off, eval-validated.

**Then:** re-bake the 4 Canon demos **once, after all code lands** (so branches reflect the fixed 7-root taxonomy + any NER effect).

**Decisions locked (2026-07-03):**
- **OWL version:** *fix detection only.* Our pin `add8b2b1` is already the latest published OWL (Feb-04-2026, `b4691501b`). "Christian Concepts" (screenshot's 8th root) exists **only in maintainer John D'Orazio's unpublished WebProtégé working copy** — not in any committed OWL — so a pin bump can't fetch it. Treat the published Feb-2026 OWL (7 substantive roots) as canonical; Christian Concepts is a separate, maintainer-gated follow-up.
- **Demo re-bake:** once, after all code merges.
- **NER scope:** FOLIO + Canon affinity maps.
- **Skip** PR-#4 `378adc0` (multi-word POS) — it reverses `main`'s deliberate single-word design; not a salvage.

**Priority / sequencing:** WS-A (unblocks Canon roots for WS-C's Canon affinity + the re-bake) → WS-B (independent, parallel-safe) → WS-C (Canon affinity needs WS-A's real roots) → re-bake (after all merge). **FOLIO byte-neutrality is a hard constraint for all three.** Execution: **one PR per workstream via ce-work subagents**, merged in order.

---

## WS-A — Canon implicit-root detection fix

### Problem
`backend/app/services/folio/concept_detail.py:110-134` `_init_branch_roots` seeds FOLIO branch IRIs from a hardcoded constant, then discovers *additional* roots via `owl_class.sub_class_of == [owl_thing]` (line 130). Canon has **3 explicit** `[owl:Thing]` roots (Actor, Document / Artifact, Event) and **6 implicit** roots with *no* `subClassOf` (Authority, Normative Concepts, Operational Concepts, Place, ZZZ - Licensing, ZZZZ - Deprecated). The implicit ones are dropped, so:
- WS-2 branch prompts (`templates._derive_branch_detail`, which reuses `_init_branch_roots`) show 3 branches, not 7.
- Concept `branches` / `hierarchy_path` (via `_get_branch_for_class`, `_build_hierarchy_path`) mis-assign concepts under Place/Authority/etc. into the 3 visible roots.

### Approach
In `_init_branch_roots`, broaden discovery to include **implicit roots** (classes whose `sub_class_of` is empty/absent) in addition to `== [owl:Thing]`, while:
- **Excluding `owl:Thing` itself** (the empty-label root node) and any empty/None-label class.
- **Applying the ontology's exclusion convention** — `spec.behavior.concept_exclude_prefixes` (Canon: `('ZZZ',)` → catches both `ZZZ - Licensing` and `ZZZZ - Deprecated`) + `concept_exclude_substrings` (`('DUPE',)`). Reuse the same exclusion helper WS-2 added (`templates._branch_label_excluded`) or factor a shared one.
- **Preserving FOLIO byte-neutrality:** FOLIO has exactly **2 implicit roots** — `"DEPRECATED Activities"` and a null-label `"None"`. Both must be filtered (empty-label skip + FOLIO's own DEPRECATED/exclusion convention) so FOLIO's discovered root set is unchanged. **If FOLIO's exclusion config does not already drop `"DEPRECATED Activities"`, gate implicit-root discovery to non-default ontologies** (`ontology_id != registry.default_id`) as the safe fallback. Verify empirically: FOLIO branch-detail string + concept-detail branch assignments byte-identical.

This one fix repairs BOTH the WS-2 branch prompts AND concept-branch/hierarchy assignment (both flow through `_init_branch_roots`/`branch_root_iris`).

### File anchors
- `backend/app/services/folio/concept_detail.py:110-134` — `_init_branch_roots` (the fix); `:68-107` `_get_branch_for_class`; `:137-` `_build_hierarchy_path` (consumers of `branch_root_iris`).
- `backend/app/services/llm/prompts/templates.py` — `_derive_branch_detail`, `_branch_label_excluded` (WS-2; reuses `_init_branch_roots`), `_BRANCH_DETAIL_CACHE`.
- `backend/app/services/ontology/spec.py` — `CANON_SPEC.behavior.concept_exclude_prefixes=('ZZZ',)`, `concept_exclude_substrings=('DUPE',)`; FOLIO_SPEC.behavior exclusion config (verify it drops "DEPRECATED Activities"/null).
- Tests: `backend/tests/test_branch_detail.py` (`TestFolioByteNeutral` = the guard; `TestCanonDerivation`), plus concept-detail hierarchy tests.

### Acceptance criteria
- [ ] Canon `_init_branch_roots` returns its **7 substantive roots** (Actor, Authority (Source and Scope), Document / Artifact, Event, Normative Concepts, Operational Concepts, Place); `ZZZ - Licensing` + `ZZZZ - Deprecated` excluded; `owl:Thing`/empty excluded.
- [ ] Canon branch-detail prompt (WS-2) now presents all 7 roots; a place concept (e.g. "Bethlehem") maps to **Place**, not Document/Artifact.
- [ ] FOLIO byte-neutral: `TestFolioByteNeutral` + concept-detail branch/hierarchy tests pass UNMODIFIED; FOLIO branch set unchanged (2 implicit roots stay filtered).
- [ ] New tests: Canon 7-root derivation; ZZZ/ZZZZ excluded; FOLIO implicit-root filtering (DEPRECATED Activities/null not introduced).
- [ ] Full suite green.

### Risks / notes
- The only real risk is FOLIO byte-neutrality via the 2 FOLIO implicit roots — the gate-to-non-default fallback removes it entirely if exclusion is insufficient.
- Does NOT re-bake demos (that's the final step). Live Canon jobs benefit immediately.

**Effort:** S–M.

---

## WS-B — Search substring coverage penalty (salvage `faa8dcc`)

### Problem
`backend/app/services/folio/search.py:164` scores any substring match a flat `label_score = 85.0` (and `:183` `pref_score = 84.0`), so a short query inside a long label nearly ties an exact match — e.g. `"Amended Complaint"` → `"Motion to File Amended Complaint"` at 85. `main` added exact-match graduation (`:152-157`) and a reverse word-overlap (`:172-174`) but the substring branch is untouched.

### Approach
Port `faa8dcc`'s two penalties onto the current substring path:
- **Coverage ratio:** `label_score = 85.0 * (len(query_lower) / len(label_lower))`; same for `pref_score` at `:183`.
- **Word-count gate:** when the query is a substring covering `< _WORD_RATIO_THRESHOLD` (0.5) of the label's words, scale by `word_ratio / 0.5`.
- **Reconcile with `main`'s `max(label_score, overlap*88)`** (`:172-174`): because of the `max()`, the penalty only dominates when the substring signal is primary — verify the final score stays sensible when both apply (add a test where both paths fire).

### File anchors
- `backend/app/services/folio/search.py:135-210` `_compute_relevance_score` (label `:163-174`, pref `:177-188`); add `_WORD_RATIO_THRESHOLD = 0.5`.
- Tests: `backend/tests/test_search.py` (port `faa8dcc`'s 47-line test addition, adapted to current graduation).

### Acceptance criteria
- [ ] `"Amended Complaint"` vs `"Motion to File Amended Complaint"` scores materially below an exact match (target ~70 vs ≥92), no longer flat 85.
- [ ] Test matrix: short-in-long, half-coverage, exact, and both-paths-fire — no regression vs `main`'s exact-match graduation.
- [ ] Ontology-neutral (pure string math — helps FOLIO + Canon). Full suite green.

**Effort:** S.

---

## WS-C — NER cross-validation (salvage `50beecc`, FOLIO + Canon)

### Problem
`main` has no NER cross-check. A concept can resolve to a branch that a spaCy named-entity signal would flag as wrong (e.g. a `PERSON` span landing on an `Industry`/`Document` concept). PR-#4 `50beecc` added it for FOLIO only, using a FOLIO-branch-name affinity map — which is stale now that Canon is live (and had different branch names).

### Approach
Re-create `50beecc` against the **current** pipeline (its parser/triple architecture changed since March 2026):
- **Parser:** extract NER entities from the existing spaCy parse (zero overhead) and thread them through today's parser/triple stages into `job.result.metadata["spacy_ner_entities"]`. NB: the old `extract_triples_and_pos` 2→3-tuple change must be re-applied to the **current** `parser.py` + EarlyTriple/TripleEnrichment stages, not the old `triple_stage.py`.
- **Reconciliation:** `_apply_ner_adjustments` — for each annotation, find an overlapping NER entity; look up a **per-ontology** NER→branch affinity map; branch ∈ affinity → `+ner_agreement_boost` (0.04); NER present but incompatible → `− ner_contradiction_penalty` (0.08); no NER overlap → no change (preserves recall).
- **Per-ontology affinity maps:**
  - FOLIO: the 9-label map from `50beecc` (`ORG → {Actor / Player, Legal Entity, Governmental Body, Industry}`, `PERSON → {Actor / Player}`, `GPE → {Location, Governmental Body}`, `DATE → {Event, Status}`, …).
  - Canon (uses WS-A's real roots): `PERSON/ORG → {Actor}`, `GPE/LOC → {Place}`, `DATE → {Event}`, etc. Key on Canon's 7 roots (Actor / Authority / Document / Artifact / Event / Normative / Operational / Place).
  - Select the map by `job.ontology`; unknown ontology → no-op (safe).
- **Config:** `ner_cross_validation_enabled` (**default `False`**), `ner_agreement_boost=0.04`, `ner_contradiction_penalty=0.08`.
- **Validate before enabling:** measure on the disambiguation eval set (the ±0.04/0.08 deltas move confidence scores). Ship off; flip on only if net-positive.

### File anchors
- `backend/app/services/dependency/parser.py` — `extract_triples_and_pos` (+ NER entities); current triple stages (`EarlyTripleStage`/`TripleEnrichmentStage`) that consume it.
- `backend/app/pipeline/stages/reconciliation_stage.py` — add `_apply_ner_adjustments` + `_NER_BRANCH_AFFINITY_BY_ONTOLOGY` + `_find_overlapping_ner`; sequence AFTER the existing POS pass (`_apply_pos_penalties`).
- `backend/app/config.py` — `ner_*` settings.
- Tests: port `50beecc`'s `test_pos_confidence.py`/`test_dependency_parsing.py` NER additions; add a Canon-affinity test (GPE→Place) and a FOLIO test; assert default-off is a no-op.

### Acceptance criteria
- [ ] NER entities extracted (zero extra spaCy passes) into metadata; parser change threaded through current triple stages.
- [ ] FOLIO + Canon affinity maps; correct map selected by `job.ontology`; unknown ontology = no-op.
- [ ] Default-off = byte-neutral no-op; enabling applies bounded ±0.04/0.08 with no-NER = no change (recall preserved).
- [ ] Eval-set measurement recorded before any decision to enable.
- [ ] Full suite green; FOLIO byte-neutral with the flag off.

**Effort:** M.

---

## Final step — Re-bake 4 Canon demos (once, after WS-A/B/C merge)

- `cd backend && .venv/bin/python scripts/generate_demos.py --ontology canon --api-key "$GOOGLE_API_KEY"` (env has unprefixed `GOOGLE_API_KEY`; pass `--api-key` explicitly — `settings` wants `FOLIO_ENRICH_GOOGLE_API_KEY`). Gemini 3 Flash, ~8 min, slimmed on write.
- Verify: all 7 Canon roots now appear across demos; a place concept branches to **Place**; zero FOLIO-legal leaks; Eucharist → Event.
- Ship as its own PR; DEV auto-deploys from `main`; PROD picks up on next deploy.

---

## Cross-cutting

- **FOLIO byte-neutrality** required for WS-A/B/C — assert via `TestFolioByteNeutral`, `test_search.py`, concept-detail + embedding/gating tests.
- **One PR per workstream via ce-work subagents**, merged in order (WS-A → WS-B → WS-C → re-bake). WS-B is independent and may proceed in parallel with WS-A.
- **Follow-up (external):** Christian Concepts (8th root) needs John D'Orazio to publish his WebProtégé working copy to `sources/ontology-semantic-canon.owl`; then bump the pin + re-derive. Tracked, not blocking.

## Sources & References
- Origin: `docs/plans/2026-07-02-001-feat-canon-loose-ends-plan.md` (WS-2 branch prompts, WS-4 triage). Memory: `project_pr4_pos_triage`, `project_multi_ontology_canon`.
- Salvage commits (local objects, deleted branch): `faa8dcc` (search), `50beecc` (NER), `378adc0` (multi-word POS — skipped).
- Canon OWL: pin `add8b2b140273b19` = `github.com/CatholicOS/ontology-semantic-canon@b4691501b` (Feb-04-2026, latest). Roots verified: 3 explicit + 6 implicit under `owl:Thing`.
