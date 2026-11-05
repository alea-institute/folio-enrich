---
title: "chore: deploy folio-api and folio-enrich to PROD (2026-11-04)"
status: active
date: 2026-11-04
---

# Scope

1. folio-api (folio.openlegalstandard.org): fast-forward the box from fccd305 to 49b5a29
   (PR #22 MCP mount fix plus CI/tests/docs). Done first; low risk.
2. folio-enrich (enrich.openlegalstandard.org): PROD runs 8695065 (2026-07-03), 125 commits
   behind main 0190e3c, including "Enrich against both", the union-ruler memory fix (#54), and
   the pipeline concurrency cap (#57).

# Access

Both boxes allow port 22 only from the static Hetzner DEV IP; SSH aliases `folio-prod` and
`enrich-prod` jump through `hetzner-dev`.

# folio-enrich procedure (bare metal, systemd, uv-managed venv)

1. Preflight: DEV runs the same commit; three concurrent both jobs complete without restart.
2. Backup (rollback point): record HEAD; `cp -a backend/.venv` to a dated sibling; copy
   `backend/.env`; tar `~/.folio-enrich` (jobs, feedback, caches).
3. Stage caches: FOLIO label embeddings and Canon label embeddings + lemma caches built by
   main's code, copied in ahead of time (checksums verified), so startup does not rebuild
   indexes on the 2-core box.
4. Switch: `git merge --ff-only origin/main`; `uv pip install -e .` into the venv; add
   `FOLIO_ENRICH_ADMIN_TOKEN` (public deploy; admin routes fail closed without it) and
   `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES=2`; install the staged caches; restart.
5. Verify: /health, /health/detail, frontend loads, a FOLIO job, a both job, admin routes
   return 403 without the token and 200 with it, memory headroom for mapper/ontokit.
6. Rollback: stop service; restore venv dir, `.env`, `~/.folio-enrich`; `git checkout` prior
   HEAD; start; verify /health.
