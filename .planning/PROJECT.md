# FOLIO Enrich — Theme System

## What This Is

A three-mode theme system (Dark / Light / Mixed) for the FOLIO Enrich frontend — a legal document annotation tool that enriches text with FOLIO ontology concepts, individuals, properties, and triples. Users can toggle between themes via a header button or settings swatches, with their choice persisting across sessions. All themes meet WCAG AA accessibility standards.

## Core Value

Every text element in every theme mode meets WCAG AA contrast ratios (4.5:1 for normal text, 3:1 for large text) — accessibility is non-negotiable.

## Current State

**Shipped:** v1.0 Three-Mode Theme System (2026-04-05)

The complete theme system is live:
- Two-layer CSS token system with 490+ variable definitions
- Three themes (Dark, Light, Mixed) toggleable via `data-theme` attribute
- Header toggle button (🌙/☀️/◑) + settings modal swatches
- localStorage persistence with flash-prevention inline script
- Default theme: Light (changed from OS preference per user request)
- All 272 text-on-background pairs + 224 branch tints pass WCAG AA
- Automated contrast audit script at `scripts/contrast-audit.mjs`

## Next Milestone Goals

TBD — run `/gsd:new-milestone` to define the next milestone.

## Requirements

### Validated (shipped in v1.0)

- ✓ Three theme modes: Dark (all panels dark), Light (all panels light), Mixed (current dark-left/light-right) — v1.0
- ✓ `data-theme` attribute on `<html>` for theme switching — v1.0
- ✓ Complete CSS variable system covering all hardcoded colors — v1.0
- ✓ Theme toggle in header bar (cycle: Dark → Light → Mixed) — v1.0
- ✓ Theme setting in settings modal with all three options — v1.0
- ✓ `localStorage` persistence of theme choice — v1.0
- ✓ Flash-prevention inline script in `<head>` — v1.0
- ✓ Light default for new users — v1.0 (adjusted from `prefers-color-scheme`)
- ✓ WCAG AA contrast compliance for all text in all themes — v1.0
- ✓ Branch color background opacity adapts per theme — v1.0
- ✓ JS color references read from CSS variables — v1.0
- ✓ Graph canvas colors respond to theme (MutationObserver) — v1.0
- ✓ Modal/tooltip theming per mode — v1.0
- ✓ Scrollbar theming per mode (via color-scheme) — v1.0

### Out of Scope

- Per-panel theme customization — excessive complexity
- Custom color palette editor — not needed for core theme switching
- High-contrast mode (beyond WCAG AA) — potential v2 feature
- Print-specific theme — existing HTML export handles this separately

## Context

- **Frontend architecture**: Single-file `frontend/index.html` (~10,200 lines), inline `<style>` block, vanilla JS
- **No build step**: Pure CSS + vanilla JS implementation
- **Deployment**: DEV on Railway (auto-deploy from `dev` branch), PROD on openlegalstandard.org (manual from `main`)
- **Audit tooling**: `scripts/contrast-audit.mjs` runs WCAG checks via `node scripts/contrast-audit.mjs`

## Constraints

- **Single file**: All changes in `frontend/index.html` — no external CSS/JS files
- **No build step**: Vanilla JS, no bundler or preprocessor
- **Backward compatible**: Mixed mode produces identical visual output to pre-v1.0 state
- **No new dependencies**: Pure CSS + vanilla JS implementation
- **Performance**: Theme switch is instant (no perceptible delay)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `data-theme` attribute on `<html>` | Modern standard, works with CSS specificity | ✓ Good — v1.0 |
| Two-layer token system (palette + semantic) | Themes swap semantic layer only | ✓ Good — v1.0 |
| Cool gray light palette | Professional, matches dark theme personality | ✓ Good — v1.0 |
| Darker blue `#2d5ee0` accent in light mode | WCAG compliance (5.54:1 on white) | ✓ Good — v1.0 |
| Theme-specific branch colors (78 values) | Full per-theme control vs opacity-only | ✓ Good — v1.0 |
| `getThemeColor()` helper reads CSS vars at runtime | Single source of truth, no JS duplication | ✓ Good — v1.0 |
| BRANCH_COLORS object eliminated | CSS vars are authoritative | ✓ Good — v1.0 |
| Flash-prevention inline script in `<head>` | Prevents FOUC before first paint | ✓ Good — v1.0 |
| Default theme = Light (changed from OS preference) | User preference discovered post-deploy | ✓ Good — v1.0 |
| MutationObserver for canvas re-render | Seamless theme changes while graph open | ✓ Good — v1.0 |

---
*Last updated: 2026-04-05 after v1.0 milestone*
