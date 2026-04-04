# Roadmap: FOLIO Enrich Theme System

## Overview

This roadmap delivers a three-mode theme system (Dark / Light / Mixed) for the FOLIO Enrich frontend. The work progresses from converting ~690 hardcoded color references into a CSS variable system, through wiring up theme switching with JS integration, to verifying WCAG AA accessibility compliance across all modes and ensuring every component themes correctly. The foundation phase is the largest effort; the later phases build on it with progressively less CSS churn and more behavioral/verification work.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: CSS Variable Foundation** - Convert all hardcoded colors to CSS custom properties and define three complete theme variable sets
- [ ] **Phase 2: Theme Switching & JS Integration** - Wire up toggle UI, persistence, flash prevention, and update all JS color references to use the variable system
- [ ] **Phase 3: Accessibility & Component Polish** - Verify WCAG AA compliance across all themes and ensure modals, tooltips, and scrollbars theme correctly

## Phase Details

### Phase 1: CSS Variable Foundation
**Goal**: Every color in the application is controlled by CSS custom properties organized into a two-layer token system, with complete variable sets defined for all three themes
**Depends on**: Nothing (first phase)
**Requirements**: CSSF-01, CSSF-02, CSSF-03, CSSF-04, CSSF-05, CSSF-06, CSSF-07
**Success Criteria** (what must be TRUE):
  1. Zero hardcoded color values remain in the CSS (every hex, rgb, rgba, hsl, and named color replaced with a CSS variable reference)
  2. Switching the `data-theme` attribute on `<html>` between "dark", "light", and "mixed" changes the application's color scheme without any page reload
  3. Mixed mode produces visually identical output to the current application appearance (backward compatible)
  4. Branch color backgrounds are legible in all three themes (opacity adapts per theme context)
**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md -- Define palette primitives and three-theme semantic token system
- [ ] 01-02-PLAN.md -- Convert all hardcoded CSS colors to var() references, consolidate branch rules
- [ ] 01-03-PLAN.md -- Convert inline style colors, visual verification checkpoint

### Phase 2: Theme Switching & JS Integration
**Goal**: Users can switch between themes using UI controls, with their choice persisting and all JavaScript-driven colors responding to theme changes
**Depends on**: Phase 1
**Requirements**: THSW-01, THSW-02, THSW-03, THSW-04, THSW-05, THSW-06, JSIT-01, JSIT-02, JSIT-03
**Success Criteria** (what must be TRUE):
  1. User can cycle through Dark/Light/Mixed themes via a header bar toggle and see the UI update instantly
  2. User can select a specific theme from the settings modal and see it applied immediately
  3. User's theme choice survives page reload with no flash of wrong theme
  4. First-time visitors see a theme matching their OS preference (dark OS = dark theme, light OS = light theme)
  5. Graph canvas re-renders with correct colors when theme changes (no stale colors from previous theme)
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Accessibility & Component Polish
**Goal**: Every text element meets WCAG AA contrast ratios in every theme mode, and all overlay components (modals, tooltips, scrollbars) render with theme-appropriate styling
**Depends on**: Phase 2
**Requirements**: A11Y-01, A11Y-02, A11Y-03, A11Y-04, A11Y-05, A11Y-06, CMPT-01, CMPT-02, CMPT-03
**Success Criteria** (what must be TRUE):
  1. All body text passes WCAG AA contrast (4.5:1 ratio) against its background in dark, light, and mixed themes
  2. All 26 branch color labels are readable against their backgrounds in all three themes
  3. Dim text (`--text-dim`) and accent-colored text (`--accent`) maintain safe contrast margins above WCAG AA thresholds
  4. Modals, tooltips, and scrollbars visually match the active theme (no dark-on-dark or light-on-light illegibility)
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. CSS Variable Foundation | 0/3 | Planning complete | - |
| 2. Theme Switching & JS Integration | 0/2 | Not started | - |
| 3. Accessibility & Component Polish | 0/2 | Not started | - |
