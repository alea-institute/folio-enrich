# Task U3 — Gold store: sessions, outcomes, provenance, export gate (folio-enrich)

You are implementing unit U3 of the Proposition System Phase A plan in folio-enrich (branch `feat/proposition-system-phase-a`). U1 (folio-propositions library, installed in `backend/.venv/`) and U2 (`EarlyPropositionStage`, `JobResult.propositions`) are complete and committed.

**Goal:** Annotation sessions persist with full candidate accounting and export gold records that prove completeness, recall, and precision.

## Hard constraints

- **No network. No git commands.** Leave the tree uncommitted.
- Venv: `backend/.venv/`; run tests `cd backend && .venv/bin/python -m pytest tests/<file> -q`.
- Do NOT touch `.planning/`, `AGENTS.md`, `.codex/`, `docs/plans/`, frontend files.
- **Byte-neutrality invariant:** `tests/test_proposition_byte_neutral.py` must stay green — your brat-exporter change must emit nothing when `propositions` is empty, and no other export surface may change.
- **Final report** → `.codex-task/U3-report.md`: summary; changed-file list; verification evidence (red/green sequence, final test tails, plus the scripted-session artifact listing described below); design decisions.

## Design contract

### Session record (the wrapper — enrich-owned, library payloads embedded)

An **annotation session** is attached to a pipeline job (keyed by job id) and persists in the job-store filesystem area following the existing atomic-write conventions (`backend/app/storage/job_store.py` — read it). Structure (Pydantic models in `backend/app/services/gold/store.py` or a sibling `models.py`):

- `session_id`, `job_id`, `document_id`, `created_at`/`updated_at`, `annotator` (default `"damien"`), `wrapper_schema_version` (store-owned integer, start at 1), library `schema_version` (from folio_propositions).
- `pre_selector`: recorded source + configuration for THIS session — `{source: "lexicon-only" | "lexicon+llm", lexicon_version/config, llm_provider, llm_model}` (R16: lexicon-only vs LLM-assisted sessions must be distinguishable from the record).
- `candidates`: every pre-selected candidate, each carrying:
  - the embedded `folio_propositions.Proposition` payload (the current, possibly-edited state),
  - `original` payload snapshot (as pre-selected, for diffing),
  - `outcome`: `accepted` | `edited` | `deleted` | `unreviewed` (initial state `unreviewed`),
  - for `edited`: `edit_kind`: `field` | `boundary` | `both` (R16 — a span-offset change is `boundary`, anything else `field`),
  - deleted candidates REMAIN in the list (`outcome="deleted"`) — the discarded-candidate audit trail.
- `hand_added`: annotator-added annotations (Proposition payloads) with provenance `hand-added`.
- Provenance per gold annotation (KD10): `pre-selected-accepted` | `edited` | `hand-added` — derivable from outcome/origin; store it explicitly on export entries.
- `cycle_learnings`: a collection linking cases to source spans — entries `{kind: "new-type" | "unclassifiable" | "forced-fit" | "structural-misfit", tag: str|None, note: str|None (free-text channel per R19), annotation_id/span ref}`.
- `unresolved` discipline: a disposition of `unresolved` on an accepted/edited/hand-added annotation is only valid when an explicit boolean (e.g. `explicit_unresolved=True` set by the annotator action) accompanies it — the store rejects an unresolved disposition that arrives without the explicit flag (never a default).
- Blind-segment and coverage-pass fields will come in U5 — leave clean extension points, do not build them now.

### Store service (`backend/app/services/gold/store.py`)

- CRUD: create session for a job (seeding candidates from `job.result.propositions`), get, update (autosave semantics: every mutation persists atomically), record candidate outcome, add hand-added annotation, add learning.
- **Export gate (KTD7, enforced HERE, not in any client):** export refuses while any candidate is `unreviewed`, with the offending count in the error. Zero unreviewed → export proceeds.
- Export produces, under `backend/eval/gold/propositions/`:
  - `<slug>.jsonl` — the gold record: one JSON object per exported annotation (accepted/edited/hand-added with their Proposition payloads + provenance + disposition), PLUS the deleted-candidate audit-trail entries (marked so precision is computable), PLUS cycle_learnings entries. Extend the spirit of `backend/eval/gold_schema.py`'s GoldEntry conventions (explicit verification/audit fields, JSONL, manifest) — deliberately parallel, not a forced reuse of the NER dataclass.
  - `<slug>.ann` — brat standoff via the extended `backend/app/services/export/brat_exporter.py` (proposition spans as T entries with type; asserter/validator/disposition as attributes/notes). Empty propositions → zero brat output change.
  - `manifest.json` — cycle index: per-opinion entry with candidate counts by outcome, hand-added count, density, schema versions (wrapper + library), annotator record, pre-selector config, export timestamp.
  - a `README.md` for the directory (what lives here, the non-circular gold convention, how density is defined).
- **Metrics from the record alone:** expose functions computing pre-selection recall proxy (= 1 − hand_added/total_gold) and precision (= accepted/(accepted+deleted) over pre-selected candidates — note the plan words precision as accepted/(accepted+rejected) where "rejected" means discarded candidates; implement over outcomes accepted+edited vs deleted and document the formula in the README).
- **Density (KTD9, canonical, fixed):** exported gold propositions per 1,000 words of normalized document text, EXCLUDING deleted candidates and learnings-only tags; reported per opinion and — where the canonical text carries section boundaries — per section (if no section metadata exists in the job, per-opinion only; check what `canonical_text` offers).
- **Cleanup exemption:** session-bearing jobs must survive `JobStore.cleanup_expired` until their gold record is exported — register the job id via the existing `PROTECTED_JOB_IDS` mechanism (`app/storage/job_store.py` line ~15) or an equivalent store-consulted exemption; un-exempt after export. Persist the exemption across restarts (derive it from stored sessions at startup or check sessions inside cleanup).
- **Migration ownership:** the store owns wrapper-level schema versioning (outcomes/provenance/learnings fields) and exposes `migrate_session(data: dict, target_wrapper_version)` with its own registry (mirror the library's `register_migration` pattern); embedded Proposition payloads are delegated to `folio_propositions.migrate_record`/the library hook. Ship a wrapper v1→v2 stub proving a wrapper-only change migrates while payloads pass through unchanged.

### API routes (`backend/app/api/routes/gold.py`)

Follow an existing router (e.g. `feedback.py` or `enrich.py`) for conventions. Endpoints (JSON bodies mirroring the store API):
- `POST /gold/sessions` (from job_id; seeds candidates) · `GET /gold/sessions/{session_id}` · `GET /gold/sessions?job_id=` · `PATCH /gold/sessions/{session_id}/candidates/{candidate_id}` (outcome/edit) · `POST /gold/sessions/{session_id}/annotations` (hand-added) · `POST /gold/sessions/{session_id}/learnings` · `POST /gold/sessions/{session_id}/export`.
- Register the router in `backend/app/main.py` next to the existing `include_router` calls.

## Test scenarios (`backend/tests/test_gold_store.py`) — author FIRST where practical; observe red, then implement

- Deleted candidate persists in the discarded-candidate trail; precision computable from the record (AE3).
- Export with one `unreviewed` candidate refused with a count; zero unreviewed exports successfully (files exist, manifest entry written).
- `unresolved` disposition requires the explicit annotator flag — store rejects it otherwise.
- Density excludes deleted candidates and learnings-only tags (construct a session where they'd change the number if wrongly included).
- Lexicon-only vs LLM-assisted sessions distinguishable by recorded pre-selector config (R16).
- Gold record round-trips through the library migration hook after a schema version bump (R19).
- A wrapper-only schema change (e.g. provenance-field split) migrates via the store's own entry point while model payloads pass through unchanged (R19).
- `cleanup_expired` skips a session-bearing job until its gold record is exported (build on the job-store test patterns; after export, cleanup applies again).
- Edited candidate: field edit vs boundary edit recorded distinctly (R16).
- Hand-added annotation carries provenance `hand-added`; fraction computable (AE3 recall measure).
- Route-level happy path: create session → patch outcomes → export via the API (use the app test client conventions from existing route tests).

## Verification before writing your report

1. `pytest tests/test_gold_store.py tests/test_proposition_byte_neutral.py tests/test_proposition_stage.py -q` green.
2. Run the test files for things you touched: brat exporter tests, main/app startup tests, job-store/cleanup tests (find them by grep; run those files).
3. **Scripted session demo:** a short script (temp, or a test marked appropriately) that: enables the flag, runs a small judicial text through the deterministic pipeline (reuse the byte-neutral harness's run helper if convenient), creates a session, resolves every candidate (mix of accept/edit/delete), adds one hand-added annotation + one new-type learning, exports, and prints the produced file paths + manifest content + computed precision/recall/density. Write the produced gold files under `backend/eval/gold/propositions/` with a demo slug (e.g. `demo-smoke`), and list them in your report (they are proof artifacts; the orchestrator will decide whether they stay committed).
