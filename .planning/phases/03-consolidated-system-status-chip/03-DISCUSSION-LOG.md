# Phase 03: Consolidated system status chip - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 03-consolidated-system-status-chip
**Areas discussed:** Expand mechanism, 'Standby' rollup, FOLIO manage action, Collapsed chip text

---

## Expand mechanism — reveal pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Anchored popover | Panel drops below the chip listing subsystem rows; closes on Esc/outside-click/re-click; keeps header stable | ✓ |
| Inline expansion | Chip expands in place, pushing header down; simpler positioning but reflows header | |
| Small modal | Centered modal (like FOLIO/settings); maximum room but heavier for a passive check | |

**User's choice:** Anchored popover
**Notes:** Keeps header layout stable; matches the common status-chip pattern.

## Expand mechanism — always vs only-when-degraded

| Option | Description | Selected |
|--------|-------------|----------|
| Always expandable | Always clickable; popover shows all four green rows + metrics even when healthy | ✓ |
| Only when degraded | Inert when green, clickable only on degradation; less clutter but affordance appears/disappears and hides metrics | |

**User's choice:** Always expandable
**Notes:** Consistent affordance; metrics stay reachable at any time.

## Expand mechanism — live update vs snapshot

| Option | Description | Selected |
|--------|-------------|----------|
| Update live | Rows reflect latest poll while open; worst-status rollup updates too | ✓ |
| Snapshot on open | Freeze values at open; refresh on next open; avoids content shift but can be stale | |

**User's choice:** Update live

---

## 'Standby' rollup — lazy-loaded subsystems on fresh load

| Option | Description | Selected |
|--------|-------------|----------|
| Counts as healthy | Standby treated as non-alarming → chip quiet green at rest; popover row labels it 'Standby' | ✓ |
| Neutral tier | Distinct calm tier that doesn't trip orange but isn't green; adds a 4th status level | |
| Counts as degraded | Standby rolls up orange → chip orange on every fresh load; conflicts with 'quiet green' goal | |

**User's choice:** Counts as healthy
**Notes:** Required to satisfy STATUS-02 ('quiet green when all healthy') on a fresh page load.

## 'Standby' rollup — FOLIO 'Update Available' / 'Updating'

| Option | Description | Selected |
|--------|-------------|----------|
| Stay green | Informational, not degraded → System stays green; FOLIO popover row carries the update note | ✓ |
| Trip to orange | Chip nudges user about pending update, but turns orange for a non-fault → alert fatigue | |

**User's choice:** Stay green
**Notes:** Reserves chip color for actual problems. Net effect: orange tier currently has no populating subsystem state; kept available for future partial-degradation signals.

---

## FOLIO manage action — relocation of the clickable affordance

| Option | Description | Selected |
|--------|-------------|----------|
| Action in popover row | FOLIO row gets a 'Manage' button/gear opening the existing FOLIO modal; discoverable + contextual | ✓ |
| Gear on System chip | Single gear on the aggregate chip; ambiguous (implies 'manage all') | |
| Settings only | Drop chip entry point; reachable from settings; cleanest header but removes quick access | |

**User's choice:** Action in popover row
**Notes:** FOLIO is the only subsystem with a management action; others get no per-row action.

---

## Collapsed chip text — healthy state

| Option | Description | Selected |
|--------|-------------|----------|
| Icon + 'System' | Green check + 'System'; quiet/minimal; satisfies icon+text | ✓ |
| Icon + 'System OK' | More explicit reassurance, slightly more text | |
| Icon + 'System' + count | Adds '4/4' style indicator; most informative but noisier | |

**User's choice:** Icon + 'System'

## Collapsed chip text — failure naming

| Option | Description | Selected |
|--------|-------------|----------|
| Icon + 'System: FOLIO' | Worst-status icon + names culprit; '+N' overflow for multiple failures | ✓ |
| Icon + 'FOLIO error' | Direct subsystem + state; loses stable 'System' identity when degraded | |
| Icon + 'System' + count | Stable label + '1 issue' count; weaker for STATUS-03 (must name failing subsystem) | |

**User's choice:** Icon + 'System: FOLIO' (with '+N' for multiple)
**Notes:** Satisfies STATUS-03 (names the failing subsystem at a glance).

---

## Claude's Discretion

- Exact icon glyphs (check / warning / error) and popover visual design — deferred to `/gsd:ui-phase` + planning, within icon+text + theme-aware + WCAG AA intent.
- Popover open/close/focus mechanics and ARIA attribute choices.
- Internal refactor of `setChip()` / `checkHealth()` to drive the consolidated chip.
- STATUS-07 header overlap: treated as resolved by the 4→1 consolidation; residual layout work confirmed in planning/ui-phase. (Low-stakes implementation fork — decided without asking.)

## Deferred Ideas

- Folding the LLM chip into the System chip — out of scope (actionable control, not passive health).
- Restyling/regrouping the layer chips (Nouns/Verbs/Individuals/POS) — separate concern.
- Responsive/mobile header layout — not in this milestone.
- A dedicated orange/'degraded' subsystem signal — tier kept available but unpopulated today.
