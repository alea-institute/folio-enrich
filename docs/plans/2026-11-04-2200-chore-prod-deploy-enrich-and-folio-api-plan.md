---
title: "chore: deploy folio-api and folio-enrich to PROD (2026-11-04)"
status: completed
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

# Receipt (2026-11-05 01:53 UTC)

## folio-api

Deployed `49b5a29`; receipt in folio-api `docs/plans/evidence/2026-11-04-mcp-mount-prod-deploy-receipt.md`
(PR #26). Follow-up: the MCP SDK's Host-header guard answers `POST /mcp` with 421;
`folio-mcp` needs `folio.openlegalstandard.org` in its allowed hosts.

## folio-enrich: 8695065 → 9a28361

Fixes landed first, each through green CI:

- #56: flaky provider-route test skips app lifespan.
- #57: `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES` (default 2).
- #58: serialized ontology loads. Found during preflight: cold concurrent both requests
  raced on one cache temp file (two 503s) and each parsed its own Canon graph.

DEV preflight (main 9a28361, container 1600m): cap 2 still restarted under two cold both jobs,
so DEV runs `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES=1`. Three concurrent cold both jobs then
completed in series (peak 1.47 GiB, no restart).

PROD changes:

| Change | Detail |
|---|---|
| Code | `git merge --ff-only origin/main` |
| Dependencies | `uv pip install -e .` (+15 packages incl. anthropic, openai, pyjwt, folio-resolve 0.4.0, folio-propositions v0.4.0; nothing removed) |
| `.env` | added `FOLIO_ENRICH_ADMIN_TOKEN` (value kept off-box in the operator's config dir only) and `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES=2`; mode 600 |
| systemd | drop-in `folio-enrich.service.d/memory.conf`: `MemoryMax=4G` so a runaway enrich restarts itself instead of the kernel OOM-killing mapper or ontokit |
| Caches | pre-built FOLIO label embeddings and Canon label embeddings + lemma caches installed before restart (checksums verified), so startup did not rebuild indexes |

Verification:

| Check | Result |
|---|---|
| Restart to `/health` 200 | 16 s |
| `/health/detail` | ontology, embedding (69,368 vectors from cache), spaCy, citations ready; `llm: no_api_key` (BYOK) |
| Admin gate | `PUT /settings` with a real field: 403 without token, 200 with it; `POST /ollama/setup` 403 without |
| FOLIO job (11 KB) | completed, 213 annotations, 24 s |
| Both job (16 KB) | completed, 281 annotations (178 shared, 70 folio_only, 33 canon_only), 29 s |
| Memory | enrich RSS 1.47 GB idle → 2.47 GB peak; box 3.1 GB available; 0 restarts |
| Other services | folio-mapper, ontokit-api, ontokit-web, caddy active |
| Browser | page renders with ontology selector, Propositions and Insights tabs |

Rollback (kept on the box until removed after a quiet week):
`sudo systemctl stop folio-enrich`; restore `backend/.venv` from the dated venv copy, `.env`
and `~/.folio-enrich` from the dated backup dir; `git checkout 8695065`; remove the
memory drop-in if wanted (`daemon-reload`); `sudo systemctl start folio-enrich`.
