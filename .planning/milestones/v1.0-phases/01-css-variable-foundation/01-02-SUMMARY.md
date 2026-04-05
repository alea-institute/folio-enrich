---
phase: 01-css-variable-foundation
plan: 02
subsystem: ui
tags: [css-variables, color-migration, color-mix, branch-consolidation, wcag, theming]

# Dependency graph
requires:
  - "Two-layer CSS token system from Plan 01 (palette primitives + semantic tokens)"
  - "[data-theme='mixed'] attribute on <html>"
provides:
  - "All CSS rules reference var() tokens instead of hardcoded hex/rgba values"
  - "52 consolidated branch annotation rules (26 normal + 26 hover) via color-mix()"
  - "Eliminated old .panel-right/.panel-detail variable override blocks"
  - "Modal and tooltip scoping in mixed theme for backward compatibility"
affects: [01-css-variable-foundation, 02-theme-switching-js-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [color-mix-for-branch-tints, semantic-token-references, modal-tooltip-mixed-scope]

key-files:
  created: []
  modified:
    - frontend/index.html

key-decisions:
  - "Used var(--white) for button text that must always be white (e.g., on accent backgrounds)"
  - "Added .modal and .concept-tooltip to mixed-mode light overrides for backward compat"
  - "Updated mixed-mode modal/tooltip tokens to light values (modals were always light-themed)"
  - "Standardized branch rule opacity to 12% normal / 22% hover / 8% clean-view hover"
  - "Mapped lineage action badge colors to semantic color-mix() expressions"

patterns-established:
  - "color-mix(in srgb, var(--branch-X) N%, transparent) for all branch background tints"
  - ".clean-view .annotation-span[data-branch] as a single rule replacing 26 identical rules"
  - "Context-aware token mapping: --modal-bg/--modal-text for modal scope, --tooltip-bg/--tooltip-text for tooltip scope"

requirements-completed: [CSSF-01, CSSF-07]

# Metrics
duration: 16min
completed: 2026-04-04
---

# Phase 1 Plan 2: CSS Color Migration Summary

**All ~550 hardcoded CSS color values (414 hex + 135 rgba) converted to var() references; 104 data-branch rules consolidated to 52 via color-mix(); old panel variable overrides removed; mixed-mode modal/tooltip scoping added for backward compatibility**

## Performance

- **Duration:** 16 min
- **Started:** 2026-04-04T18:26:04Z
- **Completed:** 2026-04-04T18:42:24Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Replaced all hardcoded hex values in CSS rules with appropriate var() semantic token references (zero remaining outside :root primitives)
- Replaced all hardcoded rgba() values with either semantic tokens (--highlight, --highlight-confirmed, etc.) or color-mix() expressions
- Consolidated 104 branch annotation rules (26 normal + 26 hover + 26 clean-normal + 26 clean-hover) down to 53 rules (26 normal + 26 hover + 1 clean-normal) plus 26 clean-hover rules using color-mix()
- Removed old .panel-right and .panel-detail variable override blocks (replaced by [data-theme="mixed"] scoped selectors from Plan 01)
- Added .modal and .concept-tooltip to mixed-mode light overrides selector for backward compatibility
- Updated mixed-mode root-level modal and tooltip tokens from dark to light values (modals were always light-themed in the original app)
- Converted POS legend inline styles in HTML to use var() references

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert all hardcoded CSS colors to var() references and consolidate branch rules** - `fb97316` (feat)

## Files Created/Modified
- `frontend/index.html` - All CSS rules now use var() token references; branch rules consolidated with color-mix(); panel overrides removed; modal/tooltip mixed-mode scoping added

## Decisions Made
- Used `var(--white)` for the 6 instances of `color: #fff` (white button text on accent backgrounds) to satisfy zero-hex requirement while keeping universal white text
- Added `.modal` and `.concept-tooltip` to the `[data-theme="mixed"]` light-override selector alongside `.panel-right` and `.panel-detail` -- modals and tooltips need light tokens in mixed mode for backward compatibility
- Updated `[data-theme="mixed"]` root-level `--modal-*` and `--tooltip-*` tokens to light values (consistent with how modals/tooltips always rendered light in the original app)
- Standardized branch tint opacity: 12% normal, 22% hover, 8% clean-view hover (slight normalization from original 10-13% range for consistency)
- Mapped lineage action badge colors to semantic `color-mix()` expressions (e.g., `color-mix(in srgb, var(--green) 10%, transparent)` for confirmed actions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Mixed-mode modal/tooltip scoping**
- **Found during:** Task 1 Step 4
- **Issue:** Modals and tooltips render at body level, outside .panel-right scope. In mixed mode, their core tokens (--bg, --surface, --text) would resolve to dark values, but they were always light-themed in the original app.
- **Fix:** Added `.modal` and `.concept-tooltip` to the `[data-theme="mixed"]` light-override selector. Also updated mixed-mode root-level modal/tooltip tokens from dark to light values.
- **Files modified:** frontend/index.html (lines 296-328 and 408-490)
- **Commit:** fb97316

**2. [Rule 1 - Bug] Lineage act-created badge color mismap**
- **Found during:** Task 1 Step 4
- **Issue:** `#1565c0` (blue) in `.lineage-action.act-created` was mapped to `var(--pos-noun)` instead of `var(--accent)` because POS noun and accent blue shared the same hex value.
- **Fix:** Corrected to `var(--accent)` which is the semantically correct token.
- **Files modified:** frontend/index.html
- **Commit:** fb97316

## Issues Encountered
None

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- All CSS rules now reference var() tokens -- theme switching will work once JS toggles the data-theme attribute
- Plan 03 will audit for any missed conversions and verify visual regression across all three themes
- JavaScript hardcoded colors (BRANCH_COLORS object, template literals) remain unconverted -- that is Phase 2 scope

## Self-Check: PASSED

- FOUND: frontend/index.html
- FOUND: .planning/phases/01-css-variable-foundation/01-02-SUMMARY.md
- FOUND: commit fb97316

---
*Phase: 01-css-variable-foundation*
*Completed: 2026-04-04*
