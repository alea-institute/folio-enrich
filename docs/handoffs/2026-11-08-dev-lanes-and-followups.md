---
session: "b1c305e6-70ec-5941-84d7-b9df3492eab7"
written_at: "2026-11-08T09:49:57.983Z"
head: "0b04d98fdbf58f6bccc32d34d3bc6ad18189c520"
branch: "docs/dev-lanes-and-followups"
---
# Handoff: DEV lanes, restart guard, and label follow-ups done; waiting items

This handoff supersedes `2026-11-07-label-fix-and-ruler-followups.md`. That handoff's completed items
now live in `docs/plans/2026-11-08-0700-chore-dev-lanes-guard-and-label-followups-plan.md` (status:
completed).

## State (2026-11-08)
- **folio-enrich PROD:** unchanged since 2026-11-07 (main `29846fd`). DEV runs `main` `382fce0`.
- **hetzner-dev:**
  - **Restart guard:** the fixed guard (dev-twin PR #23) is installed; deliberate `docker stop`s now
    last.
  - **Stopped previews:** folio-enrich #48 and #49, and folio-insights #50.
  - **Replayed lanes:** folio-mapper #15 (rebuilt by Coolify on the box) and folio-insights `master`
    (`99c3f6d`, from a prebuilt image, no build on the box).
  - **Disk:** 14 GB free on the Docker data disk. folio-insights #70 was skipped for disk.
- **Closed with no code change:** property altLabels (no language tags exist), and the label-search
  pool (0 rescues across 2,350 queries).

## Done later on 2026-11-08
- **Coolify panel:** Tailscale only (Damien, answer 1.1). The stale home-IP entry was removed from
  the Traefik panel lock, and a backup sits beside it. The public UI still answers 403, `/webhooks`
  still answers 302 for GitHub, and the tailnet panel answers 302.
- **Drawdown campaign:** resumed (Damien, answer 2.2) on this week's quota only, with no banked resets
  and no paid credits.
  - **chief #31:** shipped the `use_banked_resets` switch and the resume.
  - **chief #34:** made the switch fail closed and set the 92%/94% stops, which leave headroom for
    cloud tasks that are already running.
  - **Live:** release `5cac8ca`. At this writing the campaign sat in `pacing-hold` because the home
    box had less than about 24 GiB of free memory.
- **folio-enrich #68:** two tests now pass on pyarrow 26 and nupunkt 0.8, so the lockfile caution is
  retired.
- **folio-enrich #69:** CI retries the pinned spaCy model download, which had failed twice with 504s.
- **folio-enrich #72:** the Canon label-search pool was measured, with no change (see the plan).
- **folio-insights #70:** not replayed. Preview deploys rebuild on hetzner-dev, which the
  never-build-there rule forbids.

- **PRs #48–#50 (campaign items fe-1 to fe-3):** reviewed outside the campaign, because the
  drawdown gate cannot run folio-enrich's suite (`env-blocked`). The doc findings were fixed, and
  the PRs were squash-merged pinned to their CI-green heads: #50 as `cffe049`, #49 as `b97dda3` and
  #48 as `168ec54`. CI on `main` passed at `168ec54`.
- **Stale chief branch:** `feat/drawdown-no-banked-resets` was deleted with Damien's OK.

## Next steps
1. **Rollback cleanup (about 2026-11-14):** delete the dated PROD pre-deploy backups, the venv copies,
   and the superseded label-embedding cache, after proving nothing live references them. At the same
   time, consider pruning the superseded folio-insights image on hetzner-dev (about 9.4 GB), which
   Coolify keeps for rollback.
2. **Tailscale aliases:** when the PROD hosts join the tailnet, point the PROD SSH aliases at tailnet
   names.
3. **Preview-lane lesson:** prebuilt images skip Coolify's build only for main-branch apps. Preview
   deploys tag images by deployment id, so Coolify rebuilds them on the box.
