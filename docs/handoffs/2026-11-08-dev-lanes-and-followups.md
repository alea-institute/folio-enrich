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

## Next steps
1. **Owner decisions:**
   - **Coolify panel access:** Cockpit ask `folio-enrich-2026-11-08-0908-coolify-panel-lock`.
   - **PRs #48–#50:** held by the drawdown spend ask `chief-2026-10-31-2255-drawdown-credit-halt`.
2. **Rollback cleanup (about 2026-11-14):** delete the dated PROD pre-deploy backups, the venv copies,
   and the superseded label-embedding cache, after proving nothing live references them. At the same
   time, consider pruning the superseded folio-insights image on hetzner-dev (about 9.4 GB), which
   Coolify keeps for rollback.
3. **Tailscale aliases:** when the PROD hosts join the tailnet, point the PROD SSH aliases at tailnet
   names.
4. **Lockfile bump caution:** pyarrow above 23 and nupunkt above 0.6 break the proposition
   byte-neutral Parquet fixture and one sentence-split test. Regenerate the fixture and check the
   split expectation in the same PR that bumps `uv.lock`.
5. **Preview-lane lesson:** prebuilt images skip Coolify's build only for main-branch apps. Preview
   deploys tag images by deployment id, so Coolify rebuilds them on the box.
