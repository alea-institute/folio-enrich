# Handoff: unified proposition engine (plan done, execution under way)

## State (2026-10-26)
- **Plan:** `docs/plans/2026-10-26-0700-feat-unified-proposition-engine-plan.md` on branch `feat/unified-proposition-engine` (brainstorm, ce-plan, ce-doc-review folded in; commit e58c645). ce-work started.
- **U1 (folio-propositions v0.5.0):** implemented and verified (133 tests, ruff, mypy) on folio-propositions branch `feat/unified-record-v0.5.0`, commit f2c75a6, not yet reviewed, pushed, merged, or tagged.
- **Fast gold annotation** (`docs/plans/2026-10-26-0725-feat-fast-gold-annotation-plan.md`, branch `feat/fast-gold-annotation`, commit e375d6b): implemented, 1232 tests pass with locked deps, browser AE1-AE4 pass at 1280/390. ce-code-review round in progress; confirmed bugs to fix before merge: failed edit then approve drops the edit (P1, two reviewers incl. cross-model), held number key validates unseen items (P1), two stationary touches discard (P2), mid-swipe re-render, number key on unchanged type records edit, shortcuts on discarded cards. Then PR, merge, deploy DEV (Hetzner propositions-dev; deploy recipe in project memory).
- **Next units:** U2 (needs v0.5.0 tag + folio-insights pin-only bump first), then U3/U8, U4, U5/U9, U6/U7, U10, U11 per the plan's dependency table.

## Decisions recorded (Cockpit)
- `folio-enrich-2026-10-25-2017-insights-into-enrich-scope`, `...-2022-insights-propositions-combine`, `...-2046-insights-single-doc-surface`: answered by Damien.
- `folio-enrich-2026-10-26-1239-bakeoff-spend-cap`: OPEN hard block (LLM benchmark spend); Chief recommends $10; only Damien can approve. Lexicon tier proceeds without it.
- Damien (2026-10-26): at a conference; proceed as if he will not annotate.

## Conventions learned
- Use `uv sync --locked --extra dev` plus the pinned en_core_web_sm 3.8.0 wheel for a faithful test env; unpinned installs produce 2 false failures.
- Workers launch via cockpit `agents/worker-wrapper.sh` from the target worktree; task specs live in cockpit `agents/tasks/`.
