# Phase 2: Theme Switching & JS Integration - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up theme toggle UI controls in the header bar and settings modal, implement localStorage persistence with flash prevention, default to OS prefers-color-scheme for new users, and update all JavaScript color references (128 hardcoded hex values + BRANCH_COLORS object + canvas graph) to use the CSS variable system established in Phase 1.

</domain>

<decisions>
## Implementation Decisions

### Toggle UI
- **D-01:** Icon cycle button in header bar — single button that cycles Dark → Light → Mixed on click. Shows current theme icon (moon 🌙 / sun ☀️ / split ◑). Tooltip shows current theme + next on click. Minimal header footprint.

### JS Color Migration
- **D-02:** `getThemeColor(varName)` helper function — reads CSS variable values at runtime via `getComputedStyle(document.documentElement).getPropertyValue('--' + name)`. All JS template literal hex values replaced with calls to this helper.
- **D-03:** BRANCH_COLORS object eliminated entirely — all branch color lookups use `getThemeColor('branch-' + branchSlug)`. Single source of truth (CSS vars). No cached JS object.

### Graph/Canvas Theming
- **D-04:** Theme-adaptive canvas — graph renders with theme-appropriate colors (not always-dark). Light theme gets light canvas background with adjusted node/edge colors.
- **D-05:** Re-render on theme switch — MutationObserver watches `data-theme` attribute changes on `<html>`. When theme changes while graph modal is open, canvas re-renders with new theme colors immediately.

### Settings Modal
- **D-06:** Visual swatches in settings modal — three clickable mini-preview rectangles showing Dark/Light/Mixed with representative background + text colors. Active swatch gets highlight border. Placed in an "Appearance" section of the existing settings modal.

### Claude's Discretion
- Flash-prevention script implementation details (THSW-04) — inline `<head>` script that reads localStorage and sets `data-theme` before first paint
- `color-scheme` CSS property values per theme (THSW-06) — `dark` for dark, `light` for light, mixed TBD
- Exact icon characters/SVGs for the theme toggle button
- Settings modal swatch styling details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — THSW-01 through THSW-06, JSIT-01 through JSIT-03 define this phase
- `.planning/PROJECT.md` — Constraints: single-file, no build step, no new deps

### Phase 1 Output
- `.planning/phases/01-css-variable-foundation/01-CONTEXT.md` — Token architecture decisions (two-layer, kebab-case branches)
- `.planning/phases/01-css-variable-foundation/01-RESEARCH.md` — CSS variable patterns, color-mix(), pitfalls
- `frontend/index.html` — The CSS variable system is now in place (data-theme selectors, semantic tokens, 78 branch colors)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Settings modal already exists (`#settingsModal`, `openSettings()`, `closeSettings()`) — add Appearance section
- Header `.header-right` section — place for theme toggle button
- `data-theme="mixed"` already set on `<html>` by Phase 1 — toggle just changes this attribute
- Phase 1 semantic tokens respond to `data-theme` changes instantly — no additional CSS needed

### Established Patterns
- Modal open/close pattern: `.modal-overlay.visible` class toggle
- Header buttons: `.secondary` class with inline styles
- Event handling: direct `onclick` attributes in HTML

### Integration Points
- `BRANCH_COLORS` object at line ~3531 — 27 entries to eliminate
- 128 hex values in JS template literals (lines 3422+) — convert to getThemeColor() calls
- Canvas graph (`ctx.fillStyle`, `ctx.strokeStyle`) at lines ~8785-8798 — need theme-aware colors
- `localStorage` key convention: existing app uses `folio_enrich_cache` — theme key should follow pattern

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-theme-switching-js-integration*
*Context gathered: 2026-04-05*
