---
session: "dd62c4fe-b574-42ae-a010-5ccb7952810d"
written_at: "2026-11-07T09:38:00.813Z"
head: "61a1ccdc7f221a483783f910ea2442582c87cb60"
branch: "docs/ac-ruler-receipt"
---
# Handoff: label fix and Aho-Corasick ruler shipped; follow-ups

## State (2026-11-07)
- **folio-enrich PROD:** main `29846fd`, with folio-python pinned at 0.4.0. **DEV:** propositions-dev, the same commit.
- **folio-api PROD:** `beebde3`. Public `POST /mcp` on folio and soli answers 200.
- **Receipts:**
  - `docs/plans/2026-11-07-0745-fix-translation-alt-label-leak-plan.md`
  - `docs/plans/2026-11-07-0830-refactor-aho-corasick-entity-ruler-plan.md`
  - folio-api `docs/plans/evidence/2026-11-07-mcp-public-hosts-prod-deploy-receipt.md`

## Next steps
1. **Tailscale:** when Mike's Tailscale lands, switch the PROD SSH aliases to tailnet names and drop the jump through hetzner-dev.
2. **Rollback assets:** after a quiet week (about 2026-11-14), delete the dated pre-deploy backups and venv copies on the enrich box, plus the superseded label-embedding cache files (the old 69k-label ones). Delete only after confirming nothing live references them.
3. **Coolify DEV unjammed 2026-11-07:** a new API token was installed, the stuck deploy queue was cleared, and folio-api and folio-enrich DEV were deployed from images built off the box (see the headroom plan, section 4). Lanes not replayed: folio-insights `main` and PRs #70, #78 and #79, folio-mapper PR #15, and folio-enrich PR #50. The Coolify panel's home-IP entry is stale.
4. **Done 2026-11-07** (`docs/plans/2026-11-07-1415-chore-dev-headroom-and-required-checks-plan.md`):
   - required CI checks on main for folio-enrich and folio-api.
   - the DEV pipeline cap raised to 2 (two concurrent cold both jobs peak at 1,302 of 1,600 MiB).
   - the stale previews on hetzner-dev stopped. Never build images on that box; build DEV images on the home box and `docker load` them (see the label-fix plan).
5. **hetzner-dev headroom:** watch swap, which still holds 3.4 of 4 GB.
6. **Drawdown PRs:** #48–#50 are left to the Chief drawdown campaign's merge gate (halted on an unanswered spend decision).
7. **Smaller follow-ups:**
   - property altLabels may still carry translations, because folio-python keeps no language for property altLabels.
   - label-search recall is capped at the library's top 20 before rescoring.
