# Task U5 — Instrument-validity controls (folio-enrich)

You are implementing unit U5 of the Proposition System Phase A plan in folio-enrich (branch `feat/proposition-system-phase-a`). U1–U4 are committed: pipeline pre-selection, `/gold` session store with outcomes/provenance and gated export, and the frontend Propositions annotation tab (study `frontend/index.html`'s new proposition section — `renderPropositionsTab`, `renderPropositionCard`, `propositionFetch`, add-mode — and `backend/app/services/gold/store.py` + `backend/app/api/routes/gold.py` before writing anything).

**Goal:** the gold instrument's anchoring, coverage, and source-separation controls are operational (plan R15, R16).

## Hard constraints

- **No network. No git.** Leave the tree uncommitted.
- Venv `backend/.venv/`; tests via `cd backend && .venv/bin/python -m pytest tests/<file> -q`.
- Do NOT touch `.planning/`, `AGENTS.md`, `.codex/`, `docs/plans/`.
- **Do not break existing contracts:** the U3 export gate (zero-unreviewed) and all existing tests in `tests/test_gold_store.py` must stay green unchanged in meaning; `tests/test_proposition_byte_neutral.py` must stay green.
- **Final report** → `.codex-task/U5-report.md`: summary; changed files; red/green evidence; final test tails; design decisions; and a browser-smoke walkthrough for the orchestrator (it will drive chrome-devtools itself).

## What to build

### 1. Blind segment (R15 — anchoring-loss estimation)

Store (`backend/app/services/gold/store.py` + routes):
- Session fields: `blind_segment: {start_char, end_char} | None`, `blind_revealed_at: datetime | None`.
- `set_blind_segment(session_id, start, end)` — only before any candidate inside the range has a non-`unreviewed` outcome (reject otherwise: the segment must be annotated unassisted).
- While a blind segment is set and not revealed, the session GET payload masks pre-selected candidates whose span intersects the range: they are omitted from `candidates` in the response (server-side masking so no client can peek), but retained in storage. A `blind_pending: <count>` field says how many are hidden (count only, no spans).
- `reveal_blind_segment(session_id)` — sets `blind_revealed_at`, unmasks, and returns the **anchoring diff report**: for the segment — the tool's hidden candidates vs. the annotator's hand-added annotations in the same range; matched pairs (span overlap), tool-only spans (annotator missed or declined what the tool would have suggested), annotator-only spans (tool missed), and an anchoring-loss summary (counts + fractions). Persist the report on the session.
- Export includes the blind-segment record + diff report when present; the manifest entry notes `blind_segment: true/false`.

Frontend:
- A "Designate blind segment" control in annotation mode (selection-based, reusing the add-mode selection mechanics but as a separate armed state); while unrevealed, the document zone shows the segment with a subtle hatched/neutral background and **no proposition marks inside it**, and candidate cards for that range are absent (server already masks). A chip shows "blind segment: N hidden".
- Hand-adding spans inside the blind segment works normally.
- A "Reveal & diff" button; on reveal, show the anchoring report (matched / tool-only / annotator-only counts) in a small summary block, and the masked candidates appear as normal unreviewed cards.

### 2. Coverage pass (R15 — exhaustive full-text review)

Store: session fields `coverage_pass_completed_at: datetime | None` recorded only via an explicit `record_coverage_pass(session_id)` action; a `completeness(session_id)` check/endpoint returning `{complete: bool, reasons: [...]}` — false until (a) zero unreviewed candidates AND (b) the coverage pass is recorded AND (c) any blind segment has been revealed. **Do not change the export gate itself** (export still gates only on unreviewed); completeness is the separate first-opinion instrument (U6 consumes it). Include `completeness` in the export's manifest entry.

Frontend: a coverage-pass indicator row: an explicit "Record full-text coverage pass" button (with a one-line description of what the annotator is attesting: every sentence read against the candidate list) + a completeness status line driven by the endpoint.

### 3. Lexicon-only baseline mode (R16)

- Session creation already records `pre_selector.source`. Add a `baseline: bool` field on the session + a frontend checkbox at session start ("Lexicon-only baseline session") that (a) forces `pre_selector.source = "lexicon-only"` regardless of LLM config and (b) tells the backend to seed candidates from a lexicon-only extraction — implement by having session creation accept `baseline: true` and, when the job's propositions may include LLM-assisted candidates, re-run the deterministic `PropositionExtractor` on the job's canonical text server-side to seed candidates instead of using `job.result.propositions`. (When no LLM is configured the two are identical; assert that in a test.)
- Manifest entry records `baseline`.

## Test scenarios (`tests/test_gold_store.py` — extend, or a new `tests/test_gold_validity.py`; author FIRST, observe red)

- Blind segment masks intersecting pre-selected candidates from the session payload (count exposed, spans absent); storage retains them (Covers R15).
- Setting a blind segment over a range containing an already-reviewed candidate is rejected.
- Reveal returns a diff report: construct a session where the tool had 2 candidates in-range and the annotator hand-added 1 overlapping + 1 novel → report shows 1 matched, 1 tool-only, 1 annotator-only; anchoring numbers correct (Covers R15).
- Completeness is false with reasons until: all candidates reviewed, coverage pass recorded, blind segment revealed; true after all three (Covers R15).
- `record_coverage_pass` is explicit — creating/exporting a session never sets it implicitly.
- Baseline session records lexicon-only config and seeds deterministic candidates (equality with job propositions in the keyless case) (Covers R16).
- Existing export gate behavior unchanged (run the whole gold test file).

## Verification before the report

1. `pytest tests/test_gold_store.py tests/test_gold_validity.py tests/test_proposition_byte_neutral.py tests/test_proposition_stage.py -q` (adjust to your file layout) — green.
2. Script-check the frontend edits: extract each inline `<script>` block to a temp file and `node --check` it; grep for duplicate element ids among those you added.
3. Report the browser-smoke walkthrough steps for: designate blind segment → hidden marks visible as hatched region + hidden-count chip → hand-add inside it → reveal & diff shows the report → coverage-pass button flips completeness.
