# Handoff: Canon law-and-morals overlap — brainstorm done, planning in progress

Written 2026-11-04 by the brainstorm/planning session; updated when the plan became implementation-ready. Receiving session: retire this per the three-condition rule once the plan executes and learnings are captured.

## State

- **Plan:** `docs/plans/2026-11-04-0806-feat-canon-law-morals-overlap-plan.md` (`ce-unified-plan/v1`). Implementation-ready: nine units in four PRs, reviewed by five document reviewers (21 fixes applied, no open items). Run `ce-work <that path>`; start at U1. Implementation goes to Codex workers per standing policy.
- **Shape (decided):** an "Enrich against both" mode runs once over the union of FOLIO and the Canon; regions (shared / Canon-only / FOLIO-only / shared-drifted) come from the shared local identifier; one text surface plus an overlap side panel; model-curated moral-to-legal bridges with optional human review; 4–5 overlap demos and 2–3 dense Canon breadth demos.

## Facts the plan already encodes (don't re-derive)

- The Canon is a FOLIO fork: 14,407 of 14,972 Canon classes reuse a FOLIO local identifier under a different base IRI; 12 of those differ in label.
- Label matching is unsafe: 659 Canon labels match more than one FOLIO class.
- The demo deep-link loader takes the ontology from the URL, not from the baked demo JSON — overlap demos need their own loading rule (R16).
- Current Canon demos score 12–27 concept tags per 100 words; FOLIO's `rich_*` demos score 34–44.
