# Backend CI lane completion

Scope: finish the offered workflow and deterministic ontology URL test on
`ci/drain-backend-tests`; integrate fetched `origin/main` including bridge PR #44
with a merge commit. Publication belongs to the orchestrator; use no network.

1. Review the draft workflow against the backend lockfile, Docker Python/model
   versions, pytest markers, and newly merged bridge tests. Install only the dev
   extra; keep optional heavyweight embeddings and browser tooling outside CI.
2. Preserve the DNS stub for the allowlisted URL test. Reproduce the known demo
   freshness and agreement collision failures when locally feasible. Apply
   narrowly scoped, documented expected-failure/skip markers, without regenerating
   demos, calling paid providers, or suppressing unrelated failures.
3. Run bounded focused tests and the default backend suite using available local
   dependencies. Validate workflow YAML with actionlint if available, otherwise
   a YAML parser and explicit structural checks. Run available backend lint and
   compare legacy findings to the base rather than sweeping unrelated files.
4. Review the final diff, commit completed changes atomically, and write
   `.codex-out/lane-result.md` with exact counts, limitations, commits, suggested
   PR text, blockers, and any decisions requiring Damien.

Acceptance: default backend tests pass; the three known failures are documented
at their individual tests; workflow syntax passes available local checks; no
network use, history rewriting, unrelated changes, or secret-file reads.

## Revision (2026-10-20, sweep-2026-10-20)

The quarantine markers from step 2 are withdrawn. `test_demos_are_fresh`,
`test_regenerate_if_stale` and `test_agreement_collision_discovered` carry the
`demo_regen` or `slow` marks, so the default `addopts` already deselects them;
CI never ran them. They stay unmarked and keep failing honestly when run with
`-m demo_regen` / `-m slow` until demos are rebaked and an OWL fixture is pinned.

The one real CI failure was `test_expired_jwks_fetch_failure_does_not_use_stale_keys`:
it expired the JWKS cache by setting the fetch timestamp to 0, which reads as
fresh whenever the host's monotonic clock is below the 600 s TTL (fresh CI
runners). The test now expires the cache relative to `time.monotonic()`.
Production code sets the timestamp from the same clock and is unaffected.
