# FOLIO Enrich

## What This Is

FOLIO Enrich is a legal document annotation tool that enriches text with FOLIO ontology concepts, individuals, properties, and triples. A FastAPI backend runs a 14-stage pipeline (ingestion → normalization → parallel entity-ruler / LLM-concept / early-individual / early-property / early-triple → reconciliation → resolution → rerank → branch-judge → string-match → LLM individual/property → triple enrichment → metadata), and a single-file vanilla-JS frontend (`frontend/index.html`) presents the annotated document with an entity graph, detail panels, and 13 export formats.

## Core Value

Make legal documents semantically rich — every recognizable concept, individual, property, and SVO triple is tagged with a FOLIO IRI and surfaced in a UI that meets WCAG AA accessibility standards.

## Current State

**Shipped:** v1.1 Post-v1.0 Verification & Polish (2026-05-21)

PROD live at https://enrich.openlegalstandard.org/ running `71b5e9b`. Frontend includes:
- Three-mode theme system (v1.0) — Dark / Light / Mixed, WCAG AA compliant
- Entity graph with folio-mapper-style edge routing (cubic Bezier, 90° through node centers), theme-aware minimap, force-enabled core layers (Nouns / Verbs / Individuals)
- Detail panel with CANDIDATE DETAILS / ENTITY GRAPH tabs + new SVG icon
- Ontology metadata (synonyms, translations, see-also) rendered as styled pills
- LLM UX: friendly setup banner + chip showing "Not Configured" when no provider key is set
- Favicon (nodes-and-edges SVG glyph)

## Current Milestone: v1.2 Header & Status UX

**Goal:** Make the header status bar render reliably across all platforms and consolidate passive health indicators so problems are obvious and clutter is gone.

**Target features:**
- Robust translation flags — replace Unicode emoji flags (unrendered on Windows, look broken) with self-contained inline SVG flags for FOLIO's locale set; render on every OS and immune to content/privacy blockers.
- Consolidated system status chip — collapse Backend / FOLIO / Embedding / spaCy into one "System" chip: quiet green when all healthy, worst-status rollup that names the failing subsystem when degraded, click-to-expand per-subsystem detail, WCAG-compliant (icon + text, not color alone). LLM chip stays a separate actionable control.

<details>
<summary>Previous shipped milestones</summary>

**v1.0 Three-Mode Theme System (2026-04-05):** Two-layer CSS token system with 490+ variable definitions; three themes via `data-theme`; localStorage persistence with flash prevention; all 272 text-on-bg pairs + 224 branch tints pass WCAG AA; automated contrast audit at `scripts/contrast-audit.mjs`.

</details>

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

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-22 — started v1.2 Header & Status UX milestone*
