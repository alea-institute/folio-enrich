# Frontend annotation mode review-fix report

## Findings

- **#15 — applied.** Confirmed the draft card still passed `explicit_unresolved: true`, while hand-added drafts still defaulted to the `unresolved` disposition and the backend still rejected unresolved records without explicit confirmation. The draft card now passes `explicit_unresolved: false`, leaving the existing inline confirmation control unchecked until the annotator acts.
- **#13 — applied.** Confirmed autosave and related proposition requests still assigned awaited responses directly to global session state, and `hydrateFromDemo()` / `clearResultsOnly()` changed `currentJobId` without resetting proposition state. All requested session fetch handlers now capture the active job and session identities, discard stale successes and failures before state assignment/render/toasts, and guard completeness refreshes. Demo hydration and result clearing now call `resetPropositionSessionState()` before switching the job id.
- **#1 — applied.** Confirmed session provenance still considered only `task_llm_overrides.proposition`, even though backend task resolution can use the request/global fallback. Session creation now resolves the effective proposition LLM from a complete proposition override or the global `llm_provider`/`llm_model`, and writes those effective values to `pre_selector`. Added the requested Phase B caveat for request-scoped BYOK assist that cannot be detected from stored settings.

No findings were skipped.

## Files changed

- `frontend/index.html`
- `.codex-task/fix-frontend-report.md`

No backend production or test files were changed by this batch. The proposition extraction flag-off path was not touched, preserving the byte-neutral exports/SSE contract.

## Verification

### Inline script syntax

Command: extract each inline `<script>` body from `frontend/index.html` and pass it independently to `node --check`.

```text
inline script 1: PASS
inline script 2: PASS
inline script 3: PASS
inline script 4: PASS
checked 4 inline script block(s)
```

### Duplicate IDs

The edited proposition elements introduce no `id` attributes. The full static HTML markup was also checked after excluding script-generated template markup.

```text
duplicate static markup id check: PASS (182 ids, 0 duplicates)
edited proposition elements introduce no id attributes: PASS
```

### Named backend tests

Command: `cd backend && .venv/bin/python -m pytest tests/test_gold_store.py tests/test_gold_validity.py -q`

```text
.....................                                                    [100%]
21 passed in 0.32s
```
