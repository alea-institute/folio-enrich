---
phase: 01-css-variable-foundation
plan: 01
subsystem: ui
tags: [css-custom-properties, design-tokens, theming, data-theme, wcag]

# Dependency graph
requires: []
provides:
  - "Two-layer CSS token system (palette primitives + semantic tokens)"
  - "Three complete theme variable sets: dark, light, mixed"
  - "78 branch color variables (26 branches x 3 themes)"
  - "data-theme='mixed' attribute on <html> for backward compatibility"
  - "Component-level semantic tokens: modal, tooltip, graph, scrollbar, confidence, feedback"
affects: [01-css-variable-foundation, 02-theme-switching-js-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-layer-token-system, data-theme-attribute-selectors, palette-primitives-plus-semantic-tokens]

key-files:
  created: []
  modified:
    - frontend/index.html

key-decisions:
  - "Palette primitives use --{hue}-{lightness} naming (e.g., --gray-950, --blue-400)"
  - "Semantic tokens use --{purpose} naming (e.g., --bg, --modal-bg, --branch-actor-player)"
  - "Mixed theme duplicates all dark-theme tokens at root, then overrides for .panel-right/.panel-detail"
  - "Light theme accent shifted to #2d5ee0 for WCAG AA compliance (5.1:1 vs 3.2:1 on white)"
  - "Graph component stays dark-themed even in light mode (per research recommendation)"

patterns-established:
  - "Layer 1 (:root): Static palette primitives that never change between themes"
  - "Layer 2 ([data-theme]): Semantic tokens that reference primitives via var()"
  - "Branch color naming: --branch-{kebab-case-name} (26 branches + default)"
  - "Component tokens: --{component}-{property} (modal-bg, tooltip-border, etc.)"

requirements-completed: [CSSF-02, CSSF-03, CSSF-04, CSSF-05, CSSF-06, CSSF-07]

# Metrics
duration: 3min
completed: 2026-04-04
---

# Phase 1 Plan 1: CSS Token System Summary

**Two-layer CSS token system with 490+ variable definitions across three theme selectors (dark/light/mixed) plus 78 per-theme branch colors and component-level semantic tokens for modals, tooltips, graph, scrollbar, confidence tiers, and feedback**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-04T18:19:09Z
- **Completed:** 2026-04-04T18:22:12Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Defined palette primitives in :root (Layer 1): 24 static color values organized by neutrals-dark, neutrals-light, blues, status, and light-panel backward-compat colors
- Defined complete semantic token sets for [data-theme="dark"], [data-theme="light"], and [data-theme="mixed"] selectors, each with 84+ semantic tokens covering core, status, highlights, component, scrollbar, confidence, feedback, individual, property, layer chip, POS tag, and branch color categories
- Added [data-theme="mixed"] .panel-right/.panel-detail scoped override with full light-theme token set for backward compatibility
- Set data-theme="mixed" on the HTML element so the app looks identical to its current state

## Task Commits

Each task was committed atomically:

1. **Task 1: Define palette primitives and semantic token system for three themes** - `b77cd9d` (feat)

## Files Created/Modified
- `frontend/index.html` - Added two-layer CSS token system: palette primitives in :root, semantic tokens under [data-theme="dark"], [data-theme="light"], [data-theme="mixed"], and [data-theme="mixed"] .panel-right/.panel-detail selectors

## Decisions Made
- Palette primitives follow --{hue}-{lightness} convention per D-01 (e.g., --gray-950, --blue-400)
- Light theme accent uses #2d5ee0 per D-04 for WCAG AA compliance on white backgrounds
- Branch colors use full per-theme definitions per D-05/D-06 (26 bright for dark, 26 dark for light)
- Mixed theme root tokens duplicate dark theme; scoped .panel-right/.panel-detail override to light
- Graph component tokens (--graph-header-*) stay dark even in light theme per research recommendation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Token system is fully defined and ready for Plan 02 to reference when replacing hardcoded colors
- All existing CSS rules remain untouched -- Plan 02 will convert ~876 hardcoded color values to var() references
- data-theme="mixed" on <html> ensures the app looks identical until Plan 02 wires things up

## Self-Check: PASSED

- FOUND: frontend/index.html
- FOUND: .planning/phases/01-css-variable-foundation/01-01-SUMMARY.md
- FOUND: commit b77cd9d

---
*Phase: 01-css-variable-foundation*
*Completed: 2026-04-04*
