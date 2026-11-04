# Handoff: Canon law-and-morals overlap — PR #53 open

Written 2026-11-04 by the brainstorm/plan/build session. Receiving session: retire this per the three-condition rule once PR #53 merges and DEV is verified.

## State

- **PR:** https://github.com/alea-institute/folio-enrich/pull/53 from `feat/canon-law-morals-overlap` (one integration commit on main 264fc1c). CI `backend-tests` was pending at handoff.
- **Plan:** `docs/plans/2026-11-04-0806-feat-canon-law-morals-overlap-plan.md` — all units built; demos baked with GPT-6.1 Sol via the bake-only Codex CLI provider.
- **Old branch:** `session/1104-0708` holds the original 18-commit history plus two pre-existing commits (an Aug 17 WIP auto-save and an AGENTS.md note) that Damien chose to keep OFF the PR. Leave that branch alone.

## Next steps

1. Wait for CI on PR #53. If green, merge (standing authorization). If red, reproduce locally and fix on the PR branch.
2. Deploy to DEV (Hetzner, propositions-dev) per the repo's DEV procedure and verify an overlap demo and a live "both" run there. PROD is not a gate (SSH broken since 2026-10-30).
3. Follow-ups, not in this PR: re-bake the FOLIO demos against the Oct 30 FOLIO release; fix the three env-version test failures that also fail on pure main (router attribute, parquet byte, nupunkt split).

## Facts encoded in the plan and PR (don't re-derive)

- The Canon is a FOLIO fork: 14,407 shared classes, 12 label-drifted, 7 definition-drifted; 659 Canon labels are ambiguous in FOLIO, so regions use the local identifier.
- 47 model-curated bridges validate against the pins; `backend/scripts/bridge_queue.py` lists new Canon-only concepts after a pin bump.
- Codex CLI workers cannot run git (their sandbox mounts .git read-only); the orchestrator must run git.
