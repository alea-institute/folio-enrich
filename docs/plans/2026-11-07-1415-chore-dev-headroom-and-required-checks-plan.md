---
title: "chore: DEV headroom, parallel cap, and required checks on main"
type: chore
status: completed
date: 2026-11-07
---

# chore: DEV headroom, parallel cap, and required checks on main

## Context

The 2026-11-07 label-fix and Aho-Corasick ruler work left four decisions for the owner. On 2026-11-07 he answered them inline (recorded in Cockpit):

| Decision | Answer |
|---|---|
| Mint a new Coolify API token for the `*.dev.openlegalstandard.org` previews | Not now (the previews stay stale) |
| Require CI before merging to `main` | Yes, on folio-enrich and folio-api |
| Raise the DEV pipeline cap from 1 to 2 | Yes; test, and revert on failure |
| Free hetzner-dev memory | Stop the stale previews and the looping postgres |

## Steps and results

### 1. hetzner-dev memory

- **Stopped (`docker stop` only):** the Coolify previews for folio-enrich PR #48 and #49 (`48.`/`49.folio-enrich.dev.openlegalstandard.org`) and for folio-insights PR #50 (already merged). No volume or image was removed. A preview restarts on its PR's next push.
- **postgres (dev-services):** already exited since 2026-10-26, when the docker data disk filled ("no space left on device"). The status list still showed "Restarting". The data disk now has 22 GB free, so the container would likely start if a service needs it again.
- **Result:** available memory went from 1.34 GB to 2.24 GB, and swap use from 4.0 of 4.0 GB to 3.4 GB.

### 2. Required checks on `main`

- **folio-enrich:** branch protection requires `backend-tests`, pinned to the GitHub Actions app.
- **folio-api:** branch protection requires `API tests`, pinned to the GitHub Actions app.
- **Not added:** no review requirement, no up-to-date-branch requirement, and no admin enforcement. Force pushes to `main` are refused (the protection default).
- **Safe for every PR:** both workflows run on every `pull_request` with no path filter, so no PR waits on a check that never runs.

### 3. DEV pipeline cap

- **Change:** `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES` went from 1 to 2 in the DEV env file (the code default is 2). The env file was backed up first. The container was then recreated (`--no-deps --no-build`), so the test started cold.
- **Test:** two different demo texts (`advice_regulatory`, `advice_litigation`) ran as concurrent `both`-mode jobs on the cold container.
  - **Both completed in 31 s:** 270 and 207 annotations. The regulatory memo's 270 matches the single-job count.
  - **Memory:** the cgroup `memory.peak` was 1,302 MiB of the 1,600 MiB limit (81%, page cache included), with zero `oom`/`oom_kill` events.
- **Kept at 2.** The revert gate (exceeding the limit) did not trip.
- **Rollback:** restore the dated env backup, then recreate `propositions-dev`.

## 4. Coolify token and stuck deploy queue (later on 2026-11-07)

- **Token:** Damien minted a Coolify API token (read and deploy only) and installed it on hetzner-dev through a prompting command. Coolify had no API tokens left, so the old one had been revoked. The token value never entered a transcript.
- **Panel access:** the Coolify panel accepts only the home IP and the tailnet. The home IP entry is stale, and a browser behind an HTTP proxy cannot reach the tailnet address. Damien reset the root login with Coolify's `root:change-email` and `root:reset-password` commands.
- **Queue jam:** a folio-mapper PR #15 deploy died on 2026-10-26 (data disk full) but stayed `in_progress`. Coolify runs a server's deploys one at a time, so 25 more queued behind it, and no DEV preview had deployed since.
  - **Fix (Damien's call):** all 26 were cancelled through the API (`cancelled-by-user`; Coolify 4.1.2 answers 500 but records the cancel). There was no Coolify restart, and every app kept its running container.
  - **Not replayed:** folio-insights `main` and PRs #70, #78 and #79, folio-mapper PR #15, and folio-enrich PR #50. Their owners can re-trigger them. Each would build on hetzner-dev.
- **Deploys without building on the box:** both images were built on the home box from `main`, tagged `<app-uuid>:<full commit sha>`, and `docker load`ed onto hetzner-dev. A Coolify deploy then skips the build ("image found with the same Git Commit SHA") and only rolls the container.
  - **folio-api DEV (`008ae8b`):** `POST /mcp` initialize returns 200 (421 before), and a foreign Origin still gets 403.
  - **folio-enrich DEV (`382fce0`):** health returns 200, the container runs folio-python 0.4.0, and a FOLIO job completed with 7 annotations.

## Deferred

- **Stale panel IP:** the home-IP entry in the Coolify panel's IP lock no longer matches the home IP. It needs a refresh, or switch to tailnet-only access.
- **Box headroom:** hetzner-dev swap stays near full. Re-triggered builds on the box risk another out-of-memory stall, so build elsewhere and load the image as above.
