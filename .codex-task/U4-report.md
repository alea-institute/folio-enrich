# U4 — Minimal annotation mode report

## Summary

Implemented the cycle-one proposition annotation workflow in the existing single-file frontend. The new **Propositions** tab sits between Properties and Export and provides a tooltip-isolated canonical-text view, highlighted proposition spans, editable candidate cards, immediate gold-session autosave, hand-added spans, new-type learnings, outcome tracking, keyboard shortcuts, and gated gold export.

Added the runtime settings sliver for `proposition_extraction_enabled` (default remains `False`) and exposed the proposition task LLM override in the existing settings payload so the frontend can accurately label sessions `lexicon-only` or `lexicon+llm`.

No graph/thread/bulk annotation UI was added. No JS framework or frontend dependency was added. Backend enrichment/result models and byte-neutral output were not changed.

## Changed files

- `backend/app/api/routes/settings.py`
  - GET includes `proposition_extraction_enabled`.
  - PUT accepts/applies `proposition_extraction_enabled`.
  - Settings task-override plumbing includes `proposition`, allowing the annotation UI to report and persist pre-selector provenance.
- `backend/tests/test_settings_propositions.py`
  - Covers GET default/current value, PUT mutation, and subsequent GET.
- `frontend/index.html`
  - Adds Propositions tab, scoped styling, runtime state, SSE `proposition_added` accumulation, completion/session plumbing, candidate editing/actions, selection-based add mode, learnings, export state, and A/E/D shortcuts.
- `.codex-task/U4-report.md`
  - This report.

## Verification performed

I could not run a browser in this environment, so I did **not** visually or interactively verify the UI. The browser smoke below remains for the orchestrator.

### Backend tests

Command:

```text
cd backend && .venv/bin/python -m pytest tests/test_settings_propositions.py -q
```

Output (the environment emits harmless stream-fd warnings before pytest):

```text
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
.                                                                        [100%]
1 passed in 0.05s
```

Required byte-neutral and gold-store command:

```text
cd backend && .venv/bin/python -m pytest tests/test_proposition_byte_neutral.py tests/test_gold_store.py -q
```

Output:

```text
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
..........                                                               [100%]
10 passed in 0.12s
```

An earlier combined run of all three files also passed: `11 passed in 0.13s`.

### Static frontend sanity

- Extracted every inline `<script>` body independently and ran each through `node --check`: all four script blocks reported `OK`.
- Parsed literal HTML IDs and counted duplicates: `literal duplicate ids: []`.
- Confirmed the U4 IDs are individually present: `propositionModeToggle`, `propositionModeStatus`, `startPropositionSessionBtn`, `addPropositionSpanBtn`, `exportGoldBtn`, `propositionRemainingChip`, `propositionAddBanner`, `propositionDocument`, `propositionCandidates`, and `propositionExportResult`.
- Inspected the installed `folio-propositions` Pydantic schemas locally to ensure actor roles, validator modes, dispositions, nullable actor fields, citation edges, and required Proposition fields match the generated frontend payload.

### HTTP smoke

Uvicorn reached `Application startup complete` and reported listening on `127.0.0.1:8731`. Startup also logged expected no-network ontology warnings and read-only-home demo-seed warnings. The sandbox then rejected curl's local socket operation:

```text
curl: (7) failed to open socket: Operation not permitted
```

Therefore the requested live PUT/GET curl exchange could not be completed. The equivalent ASGI-route behavior is covered by `test_settings_propositions.py` and passed. Uvicorn was stopped after the attempt.

## Design decisions

- The proposition document is a separate, plain rendered surface. It contains only proposition `<mark>` elements, so existing concept/individual/property tooltip listeners have no targets there.
- Annotation mode is intentionally runtime-only in browser state. Toggling it always updates the server flag; turning it off retains the persisted server session but hides/disables annotation actions.
- Session creation first looks up an existing session for the current job, preventing duplicate sessions after final-job refreshes. Its pre-selector records configured proposition provider/model only when both are present.
- Cards retain the complete server Proposition payload, modifying only editable ledger fields. Citation edges and triple IDs survive edits; citation edges remain read-only.
- Null asserter/validator are explicit dropdown choices. Validator mode remains visible but is only serialized when a validator role is selected.
- `unresolved` exposes an inline checkbox and never uses `window.confirm`. The server remains authoritative and rejects unresolved saves when the explicit flag is absent.
- Add-mode uses DOM Range text offsets against the isolated document's text content, disarms after one selection, and suppresses proposition span focus while armed. Esc cancels the armed state.
- Export stays clickable with outstanding candidates and receives warning styling; the server's 422 detail is surfaced through the existing toast style.
- Candidate cards are keyboard-focusable. A/E/D are ignored in inputs, selects, textareas, buttons, and editable elements.

## Browser smoke walkthrough

1. Start the backend normally and open the enrich frontend. Open an opinion or paste one, then open **Propositions** (between **Properties** and **Export**).
2. Turn on **Annotation mode**. Confirm the status says either `lexicon only` or `lexicon + provider/model`. If the opinion was already complete and no session starts automatically, click **Start annotation session**.
3. Enrich the opinion if needed and wait for completion. Confirm a pre-selected proposition is tinted/underlined inside the Propositions document zone. Click it and verify its candidate card receives focus and scrolls into view.
4. On that card, verify the quoted span, proposition taxonomy (including `+ new type…`), nullable asserter and validator role controls, assumed checkbox, validator mode, disposition, citation-edge list, and `unreviewed` badge. Choose `unresolved` and confirm the inline **Mark unresolved deliberately** control appears.
5. Change at least one field (or the numeric span boundary), then click **Save edit**. Reload/reopen the same job and session; confirm the changed value persists and the badge is `edited`. After export, inspect the JSONL record and confirm provenance/outcome is `edited` and the server classified the edit kind.
6. Focus another candidate and click **Discard** (the UI must not label this action Reject). Confirm its badge becomes `deleted`/card is subdued. Reload and confirm the deletion remains recorded.
7. Click **+ Add span**. Confirm the selection banner appears and the cursor changes. Select text inside the proposition document. Verify no concept/property/individual tooltip fires, add-mode disarms, and a draft card opens with `party proposition of law`, null asserter/validator, `unresolved`, and the explicit-unresolved control pre-checked. Click **Save hand-added** and confirm a `hand-added` card/span appears and persists after reload.
8. Optionally choose `+ new type…`, enter a tag, save the edit, then click **Record as new-type learning**. Confirm the success toast.
9. With at least one pre-selected card still `unreviewed`, confirm the counter chip is nonzero and the export button has warning styling. Click **Export gold record**; confirm the server's 422 unreviewed-count detail appears in the toast.
10. Review every remaining candidate using **Accept**, **Save edit**, or **Discard**. Confirm the chip reaches `0 unreviewed remaining`. Exercise keyboard shortcuts on a focused card: `A` accepts, `E` focuses the first editable field, and `D` discards; confirm typing in a field does not trigger them.
11. Click **Export gold record** again. Confirm success and that the UI prints the JSONL, BRAT, and manifest paths plus precision/recall summary. Inspect the exported files/manifest and verify accepted, edited, deleted audit, and hand-added records match the UI actions.
12. Turn **Annotation mode** off. Confirm annotation actions are disabled/hidden while the server-side session remains retrievable, and GET `/settings` reports `proposition_extraction_enabled: false`.
