# Handoff: Proposition System Phase A — plan ready for execution

Written 2026-08-17 by the planning session (context limit reached). Receiving session: retire this per the three-condition rule once ce-work completes and learnings are captured.

## State

- **Execute this:** `docs/plans/2026-08-16-2234-feat-proposition-system-phase-a-plan.md` (implementation-ready, `ce-unified-plan/v1`). Invoke `ce-work` with that path; start at U1 (library) — note its exit gate (tag/publish v0.1.0, land exact pin) before U2.
- **System context:** `docs/ideation/2026-08-16-axiom-proposition-extraction-ideation.html` (the merged Proposition System — five layers, two-exit gate, decisions). Published artifact (same content): claude.ai/code artifact `efb4f353-70be-44c5-88fe-3ce9b6f58d87`.
- **Cross-repo:** folio-insights carries a HOLD banner atop `PRD-v2.0-draft-2.md` (shard-envelope work waits for this plan's review packet). Do not remove it until the packet lands and R18's disposition is recorded.
- **Review provenance:** two ce-doc-review rounds (round 1 incl. independent Codex cross-model pass) — all applied fixes are in the plan text; no unapplied findings remain except one FYI (contained-triple linkage now specified as `triple_ids`).

## Open items for Damien (non-blocking to start U1's code, blocking its exit gate)

1. PyPI publish vs. git-tag pin for `folio-propositions` v0.1.0 (new-repo creation + publish are external actions — confirm at the gate).
2. First gold opinion selection (R12 criteria: published, dense, mixes law/fact propositions with citations).

## Gotchas the plan already encodes (don't re-derive)

- Byte-neutral surface = exports + SSE; job JSON gains exactly one empty `propositions` key (KTD3). New harness `backend/tests/test_proposition_byte_neutral.py`; the existing TestFolioByteNeutral is a prompt-template test, not a pipeline harness.
- Annotation-session jobs must join the job store's cleanup-exemption list or the 30-day sweep can delete unexported gold sessions (U3 approach 4).
- `Reject` is reserved for the disposition enum; candidate removal is `Discard` (R3).
