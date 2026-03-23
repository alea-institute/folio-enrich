# FOLIO Enrich — Theme System

## What This Is

A three-mode theme system (Dark / Light / Mixed) for the FOLIO Enrich frontend — a legal document annotation tool that enriches text with FOLIO ontology concepts, individuals, properties, and triples. The theme system gives users control over the UI appearance while ensuring WCAG AA accessibility compliance across all modes.

## Core Value

Every text element in every theme mode must meet WCAG AA contrast ratios (4.5:1 for normal text, 3:1 for large text) — accessibility is non-negotiable.

## Requirements

### Validated

- ✓ Dark-themed left/center panels with CSS variables at `:root` — existing
- ✓ Light-themed right/detail panels with CSS variable overrides — existing
- ✓ 17+ CSS custom properties for core palette — existing
- ✓ 26 branch-specific semantic colors — existing

### Active

- [ ] Three theme modes: Dark (all panels dark), Light (all panels light), Mixed (current dark-left/light-right)
- [ ] `data-theme` attribute on `<html>` for theme switching
- [ ] Complete CSS variable system covering all hardcoded colors
- [ ] Theme toggle in header bar (cycle: Dark → Light → Mixed)
- [ ] Theme setting in settings modal with all three options
- [ ] `localStorage` persistence of theme choice
- [ ] Flash-prevention inline script in `<head>`
- [ ] `prefers-color-scheme` media queries as default for new users
- [ ] WCAG AA contrast compliance for all text in all themes (4.5:1 normal, 3:1 large)
- [ ] Branch color background opacity adapts per theme
- [ ] JS color references read from CSS variables or use theme-aware helper
- [ ] Graph canvas colors respond to theme
- [ ] Modal/tooltip theming per mode
- [ ] Scrollbar theming per mode

### Out of Scope

- Per-panel theme customization (e.g., user picks which panels are light/dark) — excessive complexity for v1
- Custom color palette editor — not needed for core theme switching
- High-contrast mode (beyond WCAG AA) — potential v2 feature
- Print-specific theme — existing HTML export handles this separately

## Context

- **Frontend architecture**: Single-file `frontend/index.html` (~9,668 lines), inline `<style>` block (~2,456 lines CSS), vanilla JS
- **Current theme state**: Mixed — dark `:root` variables, light overrides scoped to `.panel-right` and `.panel-detail` classes
- **Color inventory**: ~80+ unique colors, heavy RGBA usage for translucent overlays, 26 branch colors in both CSS and JS (`BRANCH_COLORS` object)
- **No media queries**: Zero `@media` rules currently — no responsive breakpoints or `prefers-color-scheme`
- **Canvas rendering**: Graph uses hardcoded `ctx.fillStyle`/`ctx.strokeStyle` — needs theme awareness
- **Known contrast risks**: `--text-dim` on `--bg` is marginal (5.0-5.2:1), `--accent` in light mode barely passes (4.6:1), some branch colors may fail on dark backgrounds

## Constraints

- **Single file**: All changes in `frontend/index.html` — no external CSS/JS files
- **No build step**: Vanilla JS, no bundler or preprocessor
- **Backward compatible**: Mixed mode must produce identical visual output to current state
- **No new dependencies**: Pure CSS + vanilla JS implementation
- **Performance**: Theme switch must be instant (no perceptible delay or flash)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `data-theme` attribute on `<html>` | Modern standard, semantic, works with CSS specificity naturally | — Pending |
| CSS variables for all colors | Eliminates hardcoded values, enables clean theme switching | — Pending |
| Mixed as default theme | Backward compatible, preserves existing user experience | — Pending |
| `prefers-color-scheme` as fallback | Respects OS-level preference when user hasn't explicitly chosen | — Pending |
| `localStorage` for persistence | Simple, no backend needed, survives page refresh | — Pending |
| Flash-prevention script in `<head>` | Inline script reads localStorage before first paint, prevents FOUC | — Pending |
| WCAG AA as minimum standard | Legal professional audience requires accessible interface | — Pending |

---
*Last updated: 2026-03-22 after initialization*
