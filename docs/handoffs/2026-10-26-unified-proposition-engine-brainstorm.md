# Handoff: unified proposition engine (plan done, execution under way)

## State (2026-10-26)
- **Plan:** `docs/plans/2026-10-26-0700-feat-unified-proposition-engine-plan.md` on branch `feat/unified-proposition-engine` (brainstorm, ce-plan, ce-doc-review folded in; commit e58c645). ce-work started.
- **U1 (folio-propositions v0.5.0):** implemented and verified (133 tests, ruff, mypy) on folio-propositions branch `feat/unified-record-v0.5.0`, commit f2c75a6. NEXT: ce-code-review it, push, PR, merge, tag v0.5.0; then the folio-insights pin-only bump; then U2.
- **Fast gold annotation:** SHIPPED. PR #47 merged (26e5c61) after ce-code-review run 20261026-080720-1708a913 (7 findings fixed in 6b80a75); deployed to DEV and verified (Palsgraf validation session intact, 104 unreviewed).
- **Next units:** U2 (needs v0.5.0 tag + folio-insights pin-only bump first), then U3/U8, U4, U5/U9, U6/U7, U10, U11 per the plan's dependency table.

## Decisions recorded (Cockpit)
- `folio-enrich-2026-10-25-2017-insights-into-enrich-scope`, `...-2022-insights-propositions-combine`, `...-2046-insights-single-doc-surface`: answered by Damien.
- `folio-enrich-2026-10-26-1239-bakeoff-spend-cap`: OPEN hard block (LLM benchmark spend); Chief recommends $10; only Damien can approve. Lexicon tier proceeds without it.
- Damien (2026-10-26): at a conference; proceed as if he will not annotate.

## Conventions learned
- Use `uv sync --locked --extra dev` plus the pinned en_core_web_sm 3.8.0 wheel for a faithful test env; unpinned installs produce 2 false failures.
- Workers launch via cockpit `agents/worker-wrapper.sh` from the target worktree; task specs live in cockpit `agents/tasks/`.
