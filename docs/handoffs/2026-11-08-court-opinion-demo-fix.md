# Handoff: Court Opinion demo tag fixes (in progress)

## Task
Requested 2026-11-08 by the openlegalstandard.org FOLIO Tools showcase session for Damien: fix the
root causes of the wrong tags in the Court Opinion demo, re-bake the demo, merge, deploy PROD, then
re-record the website's Enrich demo media and report back to that session.

## State
- **Branch:** `fix/court-opinion-demo-tags` (from main `804fb1e`).
- **Plan + diagnosis:** `docs/plans/2026-11-08-1200-fix-court-opinion-demo-tags-plan.md` (10 root causes, units U1-U5).
- **Baseline:** backend suite 1709 passed on a venv synced from `uv.lock` (`uv sync --frozen --extra dev` + the en_core_web_sm wheel CI installs). A venv from `uv pip install -e .` drifts and shows 3 false failures.
- **In flight:** three Codex workers (U1 resolver, U2 ruler/StringMatch/replay, U3 frontend), disjoint files, no commits by workers.

## Next steps
1. Verify each worker's diff and rerun the full suite.
2. `cd backend && .venv/bin/python scripts/replay_fix_demos.py` and review every changed demo (opinion first; keep "excessive force" → Excessive Force Claim).
3. Browser-check `?demo=opinion`: tags, Show Uncertain, popover Escape/×/Remove, counts.
4. PR → merge → PROD deploy per `docs/plans/2026-11-04-2200-chore-prod-deploy-enrich-and-folio-api-plan.md`; the lemma cache version changes, so pre-build and stage caches before restart.
5. Website media: `node scripts/demos/capture.mjs enrich` in openlegalstandard.org, path-limited commit of media files on `feat/folio-tools-showcase`; propose caption text in that repo's `docs/handoffs/2026-11-08-enrich-demo-rerecorded.md` if captions drift.
6. Report back to the requesting session.
