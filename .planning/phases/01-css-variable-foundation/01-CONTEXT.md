# Phase 1: CSS Variable Foundation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert all ~876 hardcoded CSS color values in `frontend/index.html` to CSS custom properties organized into a two-layer token system (palette primitives + semantic tokens), and define complete variable sets for Dark, Light, and Mixed themes under `data-theme` attribute selectors. Mixed mode must produce visually identical output to the current application.

</domain>

<decisions>
## Implementation Decisions

### Token Architecture
- **D-01:** Two-layer token system — palette primitives (e.g., `--gray-900`, `--blue-500`) that never change, plus semantic tokens (e.g., `--bg`, `--surface`, `--accent`) that themes swap. Themes redefine the semantic layer only.
- **D-02:** Kebab-case branch names for the 26 FOLIO branch colors (e.g., `--branch-litigation`, `--branch-corporate-law`, `--branch-ip`). Readable, matches FOLIO ontology naming.

### Light Theme Palette
- **D-03:** Cool gray temperature — white with blue-gray undertones. Values: `--bg: #ffffff`, `--surface: #f5f6fa`, `--surface2: #eceef4`, `--surface3: #e2e5ee`, `--border: #d0d4e0`, `--text: #1a1d27`, `--text-dim: #5c6070`. Professional, matches the dark theme's cool blue-gray personality.
- **D-04:** Darker blue accent in light mode — shift from `#4a7cff` (fails WCAG on white at 3.2:1) to `#2d5ee0` (passes at 5.1:1). Same hue family, just darker for contrast compliance.

### Branch Color Adaptation
- **D-05:** Theme-specific branch colors — define entirely different branch color values per theme (26 × 3 = 78 values). Not just opacity changes — full per-theme control.
- **D-06:** Claude's discretion on light-mode branch values — pick values that maintain hue identity and pass WCAG AA contrast. User reviews in final result, not upfront.

### Migration Approach
- **D-07:** All-at-once conversion — single pass audit, define, replace all 876 hardcoded colors. No incremental batches. One big commit avoids partial/mixed states.
- **D-08:** Before/after screenshot verification — take screenshots before migration, then after, visually compare using Chrome DevTools MCP to confirm Mixed mode backward compatibility.

### Claude's Discretion
- Light-mode branch color values (D-06) — Claude picks WCAG-compliant values per theme
- Semantic token naming for component-specific colors (e.g., `--tooltip-bg`, `--modal-border`) — Claude decides granularity

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — CSSF-01 through CSSF-07 define the specific requirements for this phase
- `.planning/PROJECT.md` — Constraints: single-file, no build step, backward compatible, no new deps

### Existing Code
- `frontend/index.html` — The single-file frontend; all CSS is inline in `<style>` block (~lines 1-2456), all JS follows
- `frontend/index.html` `:root` block — Current 16 CSS variables (--bg, --surface, --text, --accent, etc.)
- `frontend/index.html` `.panel-right`, `.panel-detail` — Current light-mode overrides (the "Mixed" pattern)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 16 CSS custom properties already defined at `:root` — these become the starting semantic tokens
- `.panel-right` and `.panel-detail` light overrides — this scoping pattern becomes the Mixed theme implementation

### Established Patterns
- All CSS is inline in `<style>` block within `frontend/index.html`
- Heavy use of RGBA for translucent overlays (will become `rgba(var(--color-rgb), opacity)` pattern)
- `BRANCH_COLORS` JS object duplicates branch colors — Phase 2 will unify this, but Phase 1 should define the CSS variables it will reference

### Integration Points
- 181 existing `var(--...)` usages already work — new variables follow same pattern
- `data-theme` attribute on `<html>` is the new theme selector — doesn't exist yet, Phase 1 creates it
- Branch color backgrounds used in annotation spans, concept pills, and tooltip headers

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

*Phase: 01-css-variable-foundation*
*Context gathered: 2026-04-04*
