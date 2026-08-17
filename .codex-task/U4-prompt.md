# Task U4 — Minimal annotation mode (frontend) (folio-enrich)

You are implementing unit U4 of the Proposition System Phase A plan in folio-enrich (branch `feat/proposition-system-phase-a`). U1–U3 are committed: the pipeline pre-selects proposition candidates when `proposition_extraction_enabled` (default off), SSE emits `proposition_added`, and the `/gold` API persists annotation sessions with outcomes/provenance and a gated export.

**Goal:** Damien can run annotation cycle 1 entirely in the enrich frontend: load an opinion, review pre-selected proposition spans, edit/delete/add, and export the gold record.

## Hard constraints

- **No network. No git commands.** Leave the tree uncommitted.
- Frontend is the single-file `frontend/index.html` (vanilla JS, no build step, ~12,300 lines). **No JS test framework may be added** (KTD8). Match the file's existing conventions exactly: tab pattern (~line 3723), `switchTab` (~11872), SSE listeners (~6593-6613), existing render functions (`renderPropertiesTab`, `renderTriples`) as style guides, CSS custom-property palette, existing button/modal/chip classes.
- **Minimal-tool boundary (KTD1):** NO graph overlays, NO thread rendering, NO bulk operations. Those come later.
- Backend byte-neutral surface must stay untouched; run `cd backend && .venv/bin/python -m pytest tests/test_proposition_byte_neutral.py tests/test_gold_store.py -q` at the end and include the output.
- **Final report** → `.codex-task/U4-report.md`: summary; changed files; what you verified and HOW (you cannot run a browser — say so plainly; list what static/HTTP checks you did run); design decisions; a walkthrough of the smoke checklist the orchestrator will drive in a real browser.

## Backend sliver (runtime flag toggle)

Add `proposition_extraction_enabled: bool | None = None` to `SettingsUpdate` in `backend/app/api/routes/settings.py`, apply it in the PUT handler the same way neighboring fields are applied, and include the current value in the GET `/settings` response payload. This lets the frontend annotation-mode toggle flip pre-selection at runtime without env edits. Update/extend the settings route tests accordingly (`grep` for the existing settings-route test file). The default stays `False`.

## Frontend implementation (`frontend/index.html`)

### Propositions tab

Add a `Propositions` tab to the tab bar (between `Properties` and `Export`) following the existing pattern. Tab content, two zones:

1. **Document zone:** render the job's `canonical_text.full_text` in a scrollable container **inside this tab** (deliberately separate from the Annotated Text tab so existing concept/individual/property tooltips can never fire during annotation). Highlight each proposition span (`start_char`/`end_char` into `full_text`) with a distinct style (suggestion: soft background tint + underline; pick a hue distinct from concepts/properties/triples, consistent in both light/dark if the app has theming — follow whatever the file does). Clicking a highlighted span scrolls to / focuses its candidate card.
2. **Candidate zone:** one card per proposition (pre-selected candidates + hand-added), showing every R4 ledger field:
   - span text (quoted excerpt),
   - `proposition_type` — a `<select>` of the working taxonomy (`party proposition of law`, `party proposition of fact`, `judicial proposition of law`, `judicial proposition of fact`, `stipulation`, `arguendo assumption`, `judicial notice`) **plus** a `+ new type…` option that reveals a free-text input (the KD11 tag; sets `is_new_type: true` and also offers a one-click "record as new-type learning" that POSTs to the learnings endpoint),
   - asserter (role select incl. a `— none —` option for first-class null; `assumed` checkbox),
   - validator (role select with `— none —` null option; mode select ruled/pro_forma/declined),
   - disposition select: `accepted`, `rejected`, `revised`, `unresolved`, `assumed-arguendo` — **selecting `unresolved` requires an explicit confirm** (the store rejects it without `explicit_unresolved: true`; surface a small "mark unresolved deliberately" confirm inline, no browser `confirm()` dialogs — build an inline control),
   - citation edges (read-only list in this minimal mode),
   - outcome state badge: `unreviewed` / `accepted` / `edited` / `deleted` / `hand-added`.

### Annotation mode + session lifecycle

- An **"Annotation mode"** toggle at the top of the tab. Turning it ON: (1) PUT `/settings` with `proposition_extraction_enabled: true` (and show the LLM-vs-lexicon state from current settings); (2) after the CURRENT job completes (or if one is already complete), POST `/gold/sessions` with `{job_id, document_id, annotator: "damien", pre_selector: {source: "lexicon-only" | "lexicon+llm", ...}}` — choose the source value from whether a `proposition` LLM is configured; (3) store `session_id` and render candidates from the session response (session candidates carry ids + outcome state). Toggling OFF PUTs the flag back to false and exits annotation UI (session stays persisted server-side).
- If the tab is opened on a completed job while annotation mode is on but no session exists yet, offer "Start annotation session".
- Every annotator action calls the API immediately (autosave is server-side):
  - **Accept** → PATCH `/gold/sessions/{sid}/candidates/{cid}` `{outcome: "accepted", proposition: <current payload>, explicit_unresolved: <bool>}`
  - **Edit** (any field or span change then save) → same PATCH with `{outcome: "edited", proposition: <edited payload>}` (the store classifies field vs boundary itself)
  - **Discard** → PATCH `{outcome: "deleted"}`. **The button label is exactly `Discard`** — never `Reject` (Reject is a disposition value only).
  - **Hand-add** → POST `/gold/sessions/{sid}/annotations` with a full Proposition payload (generate an id like `hand-<crypto.randomUUID()>`).
  - **Learnings** → POST `/gold/sessions/{sid}/learnings`.
- Errors (404/422) surface in the app's existing toast/notice style with the server's `detail` string.

### Add-mode (gated selection state, R3)

A **"+ Add span"** toggle button distinct from all click-to-inspect interactions: when armed, the document zone enters selection mode (cursor + subtle banner "select text to create a proposition span; Esc to cancel"); a mouseup text selection inside the document container computes `start_char`/`end_char` via the rendered offsets, opens a new candidate card pre-filled (type default `party proposition of law`, asserter/validator null, disposition `unresolved` pre-armed with the explicit flag UI), and on save POSTs the hand-added annotation. Disarm after one add and on Esc. While armed, span-click-to-focus is suppressed.

### Export

An **Export gold record** button + a live counter chip "N unreviewed remaining". Clicking calls POST `/gold/sessions/{sid}/export` `{}`; a 422 (gate) shows the server count message; success shows the returned file paths/manifest summary. Keep the button enabled but visually warning-state while unreviewed > 0 (the server is the gate; the UI mirrors it).

### Keyboard shortcuts (minimal set)

With a candidate card focused: `A` accept, `E` focus first editable field (edit), `D` discard. Ignore keystrokes while typing in inputs. Document the shortcuts in a small hint line in the tab.

### SSE + data plumbing

- `accumulatedPropositions` array + `proposition_added` listener following the property listener pattern (~6593-6613); re-render the tab when it's active.
- On job completion (existing complete handling), if annotation mode is on, refresh/create the session so candidates are seeded from the final job state.

## Verification (you cannot run a browser — do these instead)

1. Backend: run the settings-route tests you touched + `tests/test_proposition_byte_neutral.py tests/test_gold_store.py` — include output.
2. Static sanity: extract the `<script>` body and run it through `node --check` (write it to a temp `.js` file with function wrappers if needed) or at minimum `python3 -c` a brace/paren balance check; confirm no duplicate `id=` attributes among the ones you added (grep).
3. HTTP smoke without a browser: start the backend (`.venv/bin/uvicorn app.main:app --port 8731` briefly), curl PUT/GET `/settings` for the new flag, then stop it. If sandboxing prevents binding a port, say so in the report.
4. Write the report's **smoke walkthrough** section: the exact click-path for the orchestrator's browser smoke (per the plan's checklist: pre-selected span renders with fields; edit persists with provenance `edited`; Discard records `deleted`; add-mode creates a span without triggering tooltips; export blocked while unreviewed remains; export succeeds after full review).
