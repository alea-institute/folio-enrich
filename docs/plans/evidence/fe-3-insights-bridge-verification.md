# Fe-3 Insights bridge verification

Date: 2026-10-26. Item: `fe-3` (planned). Branch: `drawdown/fe-3`.
Plan: `docs/plans/2026-10-26-1123-fix-fe-3-insights-bridge-plan.md`.

## Starting state and scope

The clean build starting point was `aff1d51`, the committed plan on top of the supplied `26e5c61` main snapshot. The original bridge merge `d424876` is already present. The worker verified the frontend cache defect and existing sender tests instead of reapplying that bridge. No remote is configured; publication and merge remain with the controller.

The chief campaign plan, common mandate file, and unified proposition brainstorm handoff remain unavailable in this clone. This build followed the explicit build dispatch and supplied standing rules; it cannot certify an independent read of the missing chief Goal Capsule or handoff. The controller retains that source reconciliation. Phase A scope and the Palsgraf reconciliation were read; human gold validation and deferred proposition fields are untouched.

## Change and regression evidence

Implementation commit: `ca926a2`. Application changes affect only the corpus cache and accepted post-job payload handoff in `frontend/index.html`.

A successful push attempt marks its job's corpus facts stale. Repeated observations of that attempt reuse the cache. An in-flight read finishes before one follow-up begins; its obsolete result is discarded. Navigating away retains invalidation until that job is visited again. Accepted status responses use the existing safe rendering path, preserving active review edits and drafts. Corpus membership comes only from the status API, including skipped/refused records.

The new core browser regression failed against the unchanged starting frontend: after completing review and receiving a successful push, it timed out waiting for the corpus banner to change from zero to two of three propositions. After the fix, the same regression passes.

The extended real-page Playwright harness covers:

- Successful review/push, retained dirty disposition, original card identity and field focus.
- Deduplication across polls, renders and revisits; a later successful attempt without an observed pending phase.
- Success during a held status read, with exactly one follow-up and no overlapping request.
- First historical success and later cached success while the Propositions tab is hidden.
- Held reads across navigation, return-visit refresh, stale response sequences and wrong-job payload rejection.
- Failed/unconfigured pushes, terminal status errors and user-triggered manual retry.
- Actual returned absence despite a successful push report.
- Hand-added draft identity, edited value and focus; narrow-screen push with an unsaved edit.

All original browser assertions remain. The synthetic origin uses HTTPS so hand-added IDs exercise the browser's normal Web Crypto API. No production API or test-only production hook was added.

## Verification levels

Dependencies were prepared using the existing CI recipe: `uv sync --frozen --extra dev` and the pinned `en_core_web_sm` 3.8.0 release wheel. Dependency and lock files are unchanged. Python 3.13.11; Playwright 1.64.1 with cached Chromium. The existing `FOLIO_ENRICH_PLAYWRIGHT_MODULE` override selected the installed test toolchain.

Commands below run from `backend/` with that override set.

| Evidence level | Check | Result |
| --- | --- | --- |
| Local sender/identity/export/status/access/recovery | `uv run --no-sync python -m pytest tests/test_proposition_content_identity.py tests/test_propositions_export.py tests/test_proposition_byte_neutral.py tests/test_insights_client.py tests/test_insights_route.py tests/test_insights_frontend.py tests/test_post_job_flow.py tests/test_post_job_access_and_recovery.py tests/test_post_job_frontend.py -q -ra -p no:cacheprovider` | 118 passed; one third-party syntax warning |
| Real-page browser behavior, API responses stubbed | `uv run --no-sync python -m pytest tests/test_insights_browser.py tests/test_post_job_browser.py -q -ra -p no:cacheprovider` | 2 passed; zero page errors; no skips |
| Configured default backend suite | `uv run --no-sync python -m pytest tests/ -q -n 2 -ra -p no:cacheprovider` | 1,240 passed, four dependency warnings; no skips reported |
| Syntax and whitespace | `node --check tests/browser/insights_panel.cjs`; repository `git diff --check` | Passed |
| Actual folio-insights receiver | Live ingest, repeat ingest, query and returned status | Not run: no receiver checkout or existing test corpus was supplied |

The default suite retains the existing `slow`, `demo_regen`, and `eval` exclusions. Its result does not certify those optional evaluations. An earlier full run had 1,239 passes and one failure in the new draft fixture because an HTTP test origin did not supply Web Crypto. HTTPS corrected the test setup, and the subsequent full run passed. No existing test was weakened or removed.

## Screenshot evidence

Set `FOLIO_ENRICH_INSIGHTS_SCREENSHOT=../docs/plans/evidence/fe-3-insights-after-push.png` when running the insights browser test from `backend/`. The test captures the successful push and refreshed corpus banner with the unsaved rejected disposition, then captures the narrow-screen view.

- `docs/plans/evidence/fe-3-insights-after-push.png`
- `docs/plans/evidence/fe-3-insights-after-push-mobile.png`

The captures use only synthetic propositions. The System indicator reflects intentionally unstubbed unrelated health services; it is not receiver evidence.

## Controller integration gate

Using the existing Insights test environment, record both repository revisions and verify synthetic export identity parity, ingest acceptance, repeat-ingest idempotence, expected hypothesis IRIs via corpus query, and returned status. Local HTTP mocks cannot close this gate. No service installation, signup, credential access or production data is required from this worker. This is an outstanding controller integration check, not a request for a new human decision.

Historical boundary: `docs/bridge-retirement-2026-10-09.md`. This receipt closes the local enrich checks only; it does not declare the entire cross-repository bridge complete.
