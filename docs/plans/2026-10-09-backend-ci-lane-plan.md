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
