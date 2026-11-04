# Handoff: Canon law-and-morals overlap — brainstorm done, planning in progress

Written 2026-11-04 by the brainstorm/planning session; updated when the plan became implementation-ready. Receiving session: retire this per the three-condition rule once the plan executes and learnings are captured.

## State

- **Plan:** `docs/plans/2026-11-04-0806-feat-canon-law-morals-overlap-plan.md` — U1–U8 built, simplified, code-reviewed (9 reviewers; 7 findings confirmed and fixed), and pushed on this branch.
- **Demos baked** with GPT-6.1 Sol through the bake-only Codex CLI provider (`--provider codex-cli`): 5 overlap demos and 3 synthetic breadth demos (42.6-49.4 tags/100 words). The real Catholic Encyclopedia "Abbot" text scored 24.0 and was dropped. FOLIO demos are stale against the Oct 30 FOLIO release; that predates this work.
- **PR held:** the branch carries two pre-existing commits not on main (a "WIP: PreCompact auto-save" with `.codex-task/` and `.planning/` files, and an AGENTS.md note). Decide whether they belong before opening the PR.
- **Residual risks** from review (not blocking): see the plan's review notes in the PR description when opened.

## Facts the plan already encodes (don't re-derive)

- The Canon is a FOLIO fork: 14,407 of 14,972 Canon classes reuse a FOLIO local identifier; 12 differ in label, 7 in definition.
- Label matching is unsafe: 659 Canon labels match more than one FOLIO class.
- 47 model-curated bridges ship in `backend/data/bridges/canon_folio_bridges.json`, validated against the pins.
