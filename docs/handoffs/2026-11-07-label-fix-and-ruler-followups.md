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
3. **Damien's decisions:** two are filed in Cockpit:
   - a Coolify API token for the `*.dev.openlegalstandard.org` previews (the token on the box returns 401). The folio-api DEV preview still answers 421, and the Coolify folio-enrich DEV app is stale.
   - required CI checks on main.
4. **DEV parallel cap:** DEV runs with a pipeline cap of 1. A cold both job now peaks at 908 MiB of 1.56 GiB, so 2 likely fits. Raising it is a DEV `.env` change; test two concurrent cold both jobs before and after.
5. **hetzner-dev memory:** the 8 GB box sits near its ceiling. Coolify previews for folio-enrich PRs #48 and #49 and a folio-insights PR preview hold about 1.6 GB, and a `postgres` container has been restart-looping for 11 days. Never build images on it; build DEV images on the home box and `docker load` them (see the label-fix plan).
6. **Drawdown PRs:** #48–#50 are left to the Chief drawdown campaign's merge gate (halted on an unanswered spend decision).
7. **Smaller follow-ups:**
   - property altLabels may still carry translations, because folio-python keeps no language for property altLabels.
   - label-search recall is capped at the library's top 20 before rescoring.
