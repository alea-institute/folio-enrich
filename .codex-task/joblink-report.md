# Job deep-link report

## Summary

- Added startup support for `?job=<id>` before demo/cache restoration.
- Completed jobs fetched from `/enrich/{id}` now hydrate the full results state and render every results tab.
- Added optional `&tab=<name>` selection when the requested tab exists.
- Successful deep-links remove `job` and `tab` from the URL with `history.replaceState` while preserving unrelated parameters.
- Missing, unavailable, or incomplete jobs show the existing toast UI and fall through to normal startup.
- Job deep-links perform the existing gold-session lookup by `job_id` in lookup-only mode. A lookup miss never creates a session.
- Existing gold sessions render while Annotation mode is off, with mutation controls disabled or hidden until Annotation mode is enabled (admin-token behavior is unchanged).

## Files

- `frontend/index.html`
  - Added `tryLoadJob()` and wired it ahead of `tryLoadDemo()` in `init()`.
  - Added the `lookupOnly` option to `ensurePropositionSession()`.
  - Added read-only presentation safeguards for a loaded proposition session while Annotation mode is off.
- `.codex-task/joblink-report.md`
  - This implementation and verification report.

## Verification

- Inline JavaScript syntax: `node --check` passed for both extracted inline `<script>` blocks.
- Duplicate IDs: no duplicate static HTML IDs. Each touched static element ID occurs exactly once. A broad raw scan also found dynamic template placeholders such as `${annId}`; these are generated IDs, not duplicate literal DOM IDs.
- Backend regression: `cd backend && .venv/bin/python -m pytest tests/test_gold_store.py -q` passed (`12 passed in 0.19s`). The environment printed three non-fatal `Failed to create stream fd: Operation not permitted` messages before pytest output.
- No backend files changed.
- No git or network commands were used.

## Test evidence

This is a behavior-bearing, single-file browser startup change. The repository has no frontend unit-test harness for `frontend/index.html`; verification therefore used the requested per-script syntax checks, static DOM-ID checks, code-level inspection of the startup/hydration/session paths, and the prescribed backend gold-store regression test.
