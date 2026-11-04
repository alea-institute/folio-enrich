# Handoff: union ruler memory fix in progress

## Goal
Make a live "Enrich against both" job fit DEV's propositions-dev container (mem_limit 1600m).

## State
- Branch fix/union-ruler-memory from main 9b77ee9.
- Plan: docs/plans/2026-11-04-1530-fix-union-ruler-memory-plan.md (holds the measurements: FOLIO ruler +528 MB, private union ruler +551 MB, only 2,245 union labels absent from FOLIO).
- A Codex worker is implementing the plan in backend/app/pipeline/stages/entity_ruler_stage.py and tests/test_both_main_integration.py; its report lands in .codex-out/union-ruler-report.md (untracked).

## Next steps
1. Verify the worker's diff and rerun the suite plus the -m slow union tests.
2. Rerun the local RSS measurement; expect the union bundle to add tens of MB, not ~550.
3. Commit, PR, merge, deploy DEV, run a live both job in the container, confirm no restart.

## Supersedes
docs/handoffs/2026-11-04-canon-union-ruler-memory.md (resumed by this session).
