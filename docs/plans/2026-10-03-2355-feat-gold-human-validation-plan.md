---
title: Human validation of committed proposition gold - Plan
type: feat
date: 2026-10-03
status: completed
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Human validation of committed proposition gold - Plan

## Goal Capsule

- **Objective:** Damien can walk the AI-annotated Palsgraf gold one proposition at a time, approve each (the default, one keystroke) or edit it, add any the AI missed, and produce a human-validated gold record that lands back in the repo.
- **Product authority:** Damien Riehl. Decision record `folio-enrich-2026-10-03-2214-phase-b-next-cycle`, question `cycle2-annotator`: "review the AI-annotated Palsgraf session first … approve (default) or edit the AI annotations."
- **Open blockers:** none for the build. Where the review is served is a separate decision (`folio-enrich-2026-10-03-2348-palsgraf-review-host`); this feature is host-agnostic.
- **Execution profile:** one branch (`feat/gold-human-validation`), agent-implemented and verified, merged under standing authorization. Proposition extraction stays flag-off by default.

## Product Contract

### Summary

Add a validation session that loads a committed gold record into the existing review workspace. Every AI annotation arrives pre-filled and ready to approve. Edits, discards and missed propositions are recorded. The export is a separate human-validated record that names the record it validates, and it can be retrieved from whichever host served the review.

### Requirements

**Creating a validation session**

- R1. An annotation-authorized request creates a validation session from a committed gold record named by its slug (for example `palsgraf-248-ny-339`).
- R2. The session's items are that record's exported gold annotations, each pre-filled with the AI's final classification. Audit, learning and blind-segment rows are not items.
- R3. If the record's job is missing on the host, it is recreated from the committed canonical text under the record's job id, as a completed job the review workspace can open.
- R4. Creating again while an unexported validation session for the same record exists returns that session rather than a duplicate.

**Reviewing**

- R5. Approve is the primary, default action on every item, and the existing A-key shortcut performs it. Approving keeps the AI's classification unchanged.
- R6. The reviewer can edit any field, discard an item, or hand-add a proposition the AI missed, all using the existing workspace controls.
- R7. The workspace clearly labels a validation session as validating a named record and its annotator, so it isn't mistaken for a fresh annotation cycle.

**Exporting and retrieval**

- R8. Export writes a new record (`<slug>-validated`) that leaves the original untouched. Its manifest entry names the validated record, the original annotator and the human validator, and counts approved, edited, discarded and hand-added items.
- R9. An exported validation record can be retrieved as data (JSONL, brat standoff and manifest entry) through a read endpoint, so it can be committed to the repo from any host.
- R10. A local repo script imports a retrieved record into `backend/eval/gold/propositions/` and the manifest. It copies the original's `text_file` and `splits`, then reruns the gold-text integrity test.

### Acceptance Examples

- AE1. Covers R2, R5. A validation session for Palsgraf has 104 items. Approving all of them unchanged exports 104 approved, 0 edited, 0 discarded and 0 hand-added.
- AE2. Covers R4. Calling create twice before export returns the same session id.
- AE3. Covers R8. After export, the original `palsgraf-248-ny-339.jsonl` is byte-identical, and the manifest gains a `palsgraf-248-ny-339-validated` entry with `validation_of: palsgraf-248-ny-339`.

### Scope Boundaries

- Not in scope: choosing or provisioning the review host, bulk "approve all remaining" (each item gets a deliberate keystroke so the record honestly claims human validation), and changing the benchmark's choice of which record to score (decided once a validated record exists).

## Planning Contract

### Key Technical Decisions

- KTD1. **Reuse `AnnotationSession` with a `validation_of` field rather than adding a new session type.** Items are `CandidateRecord`s whose `original` equals the AI's final `proposition`, so the existing outcome, edit-detection and export paths apply unchanged. `PreSelector.source` gains the literal `"gold-validation"`. Governs R1, R2, R6.
- KTD2. **Committed gold is read from the repo's gold directory on the host.** The Docker image already ships `backend/`. The record list comes from `manifest.json` entries that have a `text_file`. Governs R1, R3.
- KTD3. **The job is recreated through `JobStore.save` with status completed and only `canonical_text` populated.** Unexported sessions already exempt their job from `cleanup_expired` (`app/storage/job_store.py`). Governs R3.
- KTD4. **Validation export reuses `GoldStore.export` with a slug suffix and extra manifest fields.** Precision and recall-proxy fields stay as computed. Additional fields: `validation_of`, `validated_annotator`, and `validation_counts`. Governs R8.
- KTD5. **The bundle endpoint is read-only and unauthenticated, like `GET /gold/sessions/{id}`.** Gold content is destined for the public repo. Governs R9.

## Implementation Units

### U1. Backend validation sessions

- **Files:** `backend/app/services/gold/store.py`, `backend/app/api/routes/gold.py`, `backend/tests/test_gold_validation.py` (new).
- **Approach:** per KTD1–KTD5. Add `POST /gold/validation-sessions` (annotation auth) taking `{slug}`; `GET /gold/records` listing validatable records; and `GET /gold/sessions/{id}/bundle` returning the exported files as JSON after export (409 before). Wrapper schema migration only if the session wrapper shape requires it; follow the store's existing migration registry.
- **Test scenarios:** AE1, AE2, AE3; an unknown slug gives 404; creating without annotation auth when a token is configured is rejected; job recreation when absent and reuse when present; non-annotation rows excluded; an edited item exports as `edited` with `edit_kind`; a hand-added item counts as missed; bundle before export gives 409 and after export returns files matching what was written to disk.

### U2. Workspace entry point and labelling

- **Files:** `frontend/index.html`.
- **Approach:** under Session tools, add "Validate committed gold…", which lists `GET /gold/records`, creates the session, then opens `?job=<job_id>` with the session loaded. Show a validation banner (R7). Keep Approve as the primary action (R5). Follow the existing proposition workspace code and styles.
- **Verification:** a browser smoke run against a local server: create a validation session for Palsgraf, approve one item, edit one, export, fetch the bundle.

### U3. Import script

- **Files:** `scripts/import_validated_gold.py` (new), `backend/tests/test_gold_validation.py`.
- **Approach:** per R10. It takes a bundle JSON file or URL plus session id, writes the JSONL, `.ann` and manifest entry, and copies `text_file` and `splits` from the validated record.
- **Test scenarios:** importing a synthetic bundle produces files that pass the gold-text integrity check; re-import is idempotent.

## Verification Contract

- `cd backend && .venv/bin/python -m pytest tests/ -q` passes.
- `tests/test_proposition_byte_neutral.py` passes unchanged.
- A browser smoke run per U2.

## Definition of Done

- U1–U3 are complete with tests passing, and the browser smoke run is recorded in the PR.
- The original Palsgraf gold record is unchanged.
- Abandoned code is removed.
