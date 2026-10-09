# folio-enrich bridge retirement boundary

This receipt covers the enrich side of
`docs/plans/2026-10-09-0645-feat-insights-bridge-plan.md`, units U2, U3 and U7.
It does not certify completion of work in other repositories.

| Seam | Enrich implementation | Retirement status |
| --- | --- | --- |
| Source/span identity | `folio_propositions.content_iri` and `document_source_uri` | Packaged dependency, pinned at `v0.4.0`; legacy UUIDs retained |
| Interchange | Shared-schema JSON and flat proposition NDJSON exports | No sibling-checkout import; persisted legacy jobs stamped on read |
| Corpus reads | Backend HTTP status and health client | No insights code imported into enrich |
| Corpus writes | Review-gated HTTP ingest of the shared-schema record | Requires annotation access; manual retry and interrupted-push recovery |
| Existing concept matching | `folio-resolve==0.4.0` | Packaged dependency; this lane does not change the earlier matching migration |

The final enrich application contains no `sys.path` references. The
folio-propositions lock resolves `v0.4.0` to
`bb62e5b6defdccd8d552b794e16bdc2267720628`.

U5 retires the sibling-checkout bridges **inside folio-insights**, with a
parity test for each seam; U6 updates **folio-resolve**'s migration schedule.
Those are separate lanes. There is no remaining enrich-side sibling-checkout
bridge to remove. The orchestrator must reconcile those lanes and verify the
actual cross-repository ingest/status contracts before declaring the overall
bridge plan complete.

## Local completion evidence

- Reviewed the original seven commits against locally available `origin/main`
  (`510a652`), the bridge plan, and the worker receipts. The current checkout
  has no `docs/handoffs/`; the latest historical handoff was already retired.
- Removed tracked Python bytecode from the Git index while retaining its
  working copy, and added bytecode ignore rules.
- Fixed the newly introduced lint findings. All 21 new Python files pass Ruff;
  a comparison of findings by file, rule and message shows zero new findings.
  Full-tree Ruff still reports legacy findings: 398 on the base, 389 after
  cleanup. No repository-specific lint command is configured.
- Focused offline verification: **91 passed, 0 failed, 9 deselected**. This
  covers identity/export, client failures, all four review/push combinations,
  access checks, overrides, retry and recovery. The deselection expression was
  `not production_parallel_path and not lookup and not route`; it is a
  verification limit, not an assertion that those omitted tests pass.
- JavaScript syntax: **5 passed, 0 failed** (three inline scripts and both
  browser test scripts). Whitespace checks passed.
- Browser tests: **0 passed, 0 failed, 2 skipped**, because no launchable
  Playwright Chromium was available in this sandbox.
- The required full backend run was bounded at 240 seconds and timed out.
  A separate unchanged ontology test reproduced unavailable external DNS
  (**3 passed, 1 failed, 2 deselected**). A dependency also tries to open its
  log outside the writable worktree; verification-only logging redirection
  allowed the focused run above. Threaded TestClient and the production
  parallel-path test still did not complete in bounded diagnostic runs.

**Release gate remains open:** the orchestrator must rerun the full backend
suite and browser tests in a suitable environment. This lane is not yet
certified PR-ready. Earlier worker receipts report green suites, but those
historical results are not a current-head verification receipt.

No push, PR, GitHub call or deployment was performed. The adjacent CI lane was
inspected only for status: modified `backend/tests/test_ontology_ingestion.py`
and untracked `.github/workflows/tests.yml`; neither was changed here.
