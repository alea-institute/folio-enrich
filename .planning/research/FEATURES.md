# Feature Landscape

**Domain:** CSS theme system (Dark/Light/Mixed) for a legal document annotation tool
**Researched:** 2026-03-22

## Table Stakes

Features users expect. Missing = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `data-theme` attribute on `<html>` | Industry standard mechanism; CSS specificity works naturally with `[data-theme="dark"]` selectors; screen readers and browser extensions can detect theme | Low | Every major theme system (web.dev, Tailwind, shadcn) uses this pattern |
| CSS custom properties for all colors | Eliminates hardcoded hex values; enables instant theme switching without class juggling; already partially in place with 17+ `:root` vars | Medium | Current codebase has ~80+ unique colors, many hardcoded -- the audit and migration is the real work |
| `localStorage` persistence | Users expect their theme choice to survive page refresh and browser restart; simplest persistence mechanism that needs no backend | Low | Single key-value pair; read in `<head>` script, write on toggle |
| Flash-prevention script in `<head>` | "Flash of wrong theme" (FOWT) is immediately noticeable and feels broken; users on dark mode seeing a white flash is a known pain point | Low | Inline blocking `<script>` before `<style>` that reads `localStorage` and sets `data-theme` before first paint; ~10 lines of JS |
| `prefers-color-scheme` detection as default | Users who have set OS-level dark/light preference expect apps to respect it; this is the baseline expectation in 2025+ | Low | `window.matchMedia('(prefers-color-scheme: dark)')` with `.matches` check; only used when no explicit user preference stored |
| WCAG AA contrast compliance (all modes) | Legal professionals are the target audience; accessibility is non-negotiable; WCAG AA is 4.5:1 for normal text, 3:1 for large text and UI components | High | Every variable pairing must be audited across all three themes; known risks: `--text-dim` on `--bg` (marginal at 5.0:1), `--accent` in light mode (4.6:1), some branch colors on dark backgrounds |
| Theme toggle in header | Users need a visible, discoverable control; header placement is the established convention (GitHub, VS Code, MDN all put it there) | Low | A `<button>` element (not a link or div) with proper `aria-label`; cycles through modes |
| Theme setting in settings modal | Power users expect theme control alongside other settings; provides labels and descriptions that a toggle icon alone cannot | Low | Radio buttons or segmented control showing all three options with labels |
| Modal/tooltip theming | Modals and tooltips that don't match the current theme look broken; they inherit from `:root` or need explicit variable scoping | Medium | Modals are currently dark-themed; in Light mode they must flip; in Mixed mode they follow their parent panel's palette |
| Scrollbar theming per mode | Bright white scrollbars in a dark panel (or dark scrollbars in a light panel) are visually jarring; breaks immersion | Low | Use `scrollbar-color` CSS property (Baseline since Dec 2025) plus `::-webkit-scrollbar` fallbacks; current codebase already has some webkit scrollbar styles |

## Differentiators

Features that set this product apart. Not expected, but valued when present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Mixed mode (dark-left, light-right) | Unique to this app; the split-panel approach matches how legal professionals work: dark for navigation/input, light for document reading; preserves current beloved default | Medium | Requires CSS variable scoping per panel region -- `.panel-left` and center get dark vars, `.panel-right` and `.panel-detail` get light vars; this is already the current behavior, just needs to be formalized under `[data-theme="mixed"]` |
| Branch color opacity adaptation per theme | FOLIO branch colors (26 semantic categories) render as translucent backgrounds on annotation spans; these need different opacity levels on dark vs light backgrounds to maintain readability and visual distinction | Medium | Dark backgrounds need ~15-22% opacity; light backgrounds need ~8-12% opacity; current `--highlight` vars partially handle this but branch-specific backgrounds are computed in JS |
| Canvas/graph theme awareness | The minimap and ontology graph use hardcoded `ctx.fillStyle` and `ctx.strokeStyle` values; theme-aware graph rendering is uncommon in annotation tools | Medium | Read colors from CSS variables via `getComputedStyle()` or maintain a theme-aware color object; requires redraw on theme change |
| Smooth CSS transition on theme switch | Prevents jarring instant color flip; communicates intentionality; feels polished | Low | `transition: background-color 0.3s, color 0.3s` on `body` and major containers; guard behind `prefers-reduced-motion: no-preference` for accessibility |
| `prefers-color-scheme` change listener | When user changes OS theme mid-session (and has no explicit override stored), app follows automatically without refresh | Low | `matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ...)` ; only fires when no explicit user preference exists |
| Three-mode toggle icon | Sun/moon/split icon that visually communicates the current mode at a glance; more informative than a generic settings icon | Low | SVG icons inline in the button; swap on mode change; accessible via `aria-label` describing current state |
| JS color references read from CSS variables | `BRANCH_COLORS` object and other JS-side color lookups (used in graph rendering, dynamic span styling) should derive from CSS vars so they auto-update on theme change | Medium | Replace hardcoded hex values in `BRANCH_COLORS` with `getComputedStyle(document.documentElement).getPropertyValue('--branch-actor')` pattern, or use a theme-aware helper function |

## Anti-Features

Features to explicitly NOT build. Each would add complexity without proportional value.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Per-panel theme customization | Allowing users to independently set light/dark on each panel explodes the test matrix (2^4 = 16 combinations for 4 panels) and creates confusing UX; the three preset modes already cover the meaningful configurations | Offer exactly three modes: Dark, Light, Mixed; if user feedback demands more, revisit in v2 |
| Custom color palette editor | Building a full color picker UI with live preview and persistence is a major feature that serves a tiny minority of users; legal professionals want to read documents, not design color schemes | Rely on the three well-designed palettes; if power users want customization, they can use browser dev tools |
| CSS `light-dark()` function as primary mechanism | While `light-dark()` is elegant, it only supports two-value switching (light or dark) and cannot express the Mixed mode where different panels use different palettes; it also requires `color-scheme` property which conflicts with per-region scoping | Use `data-theme` attribute with CSS custom property overrides scoped to `[data-theme="dark"]`, `[data-theme="light"]`, and `[data-theme="mixed"]`; this is more flexible and handles the three-mode requirement |
| High-contrast mode (beyond WCAG AA) | WCAG AAA (7:1 ratio) is a separate concern; building it now adds another full palette to design, test, and maintain | Ship WCAG AA first; track user requests; if needed later, add as a fourth mode with minimal incremental CSS |
| View Transitions API for theme animation | While cinematic (circular wipe from toggle button), Safari requires manual flag enablement, and the complexity-to-value ratio is poor for a professional tool where subtlety beats flashiness | Use simple CSS `transition` on `background-color` and `color` (guarded by `prefers-reduced-motion`); instant and cross-browser |
| Print-specific theme | The app already has a dedicated HTML export format; adding print media queries for the main UI duplicates effort for a use case where users export first | Keep the existing HTML export; add `@media print` only if users explicitly request printing the main UI |
| Automatic time-based theme switching | Switching themes based on time of day adds complexity (timezone handling, configurable schedule) for a feature most users already handle at the OS level via `prefers-color-scheme` | Respect OS-level auto-switching via `prefers-color-scheme`; the OS handles sunrise/sunset logic |

## Feature Dependencies

```
localStorage persistence
  --> Flash-prevention script (reads localStorage before paint)
  --> prefers-color-scheme detection (fallback when no stored preference)

data-theme attribute on <html>
  --> CSS custom properties for all colors (vars scoped under [data-theme="..."])
  --> Theme toggle in header (writes data-theme)
  --> Theme setting in settings modal (writes data-theme)
  --> Modal/tooltip theming (inherits from data-theme)
  --> Scrollbar theming (scoped under data-theme)

CSS custom properties for all colors
  --> WCAG AA contrast compliance (auditing requires all colors as variables)
  --> Branch color opacity adaptation (opacity vars change per theme)
  --> Canvas/graph theme awareness (JS reads vars)
  --> JS color references from CSS variables (replaces BRANCH_COLORS hardcoding)

Mixed mode
  --> CSS custom properties for all colors (panel-scoped variable overrides)
  --> Branch color opacity adaptation (different per panel region)

prefers-color-scheme detection
  --> prefers-color-scheme change listener (extends the detection with live updates)

Smooth CSS transition
  --> data-theme attribute (transitions fire on attribute change)
  --> prefers-reduced-motion guard (must check before applying)
```

## MVP Recommendation

Build in this order based on dependency chain:

### Phase 1: Foundation (must come first)
1. **CSS variable audit and migration** -- Convert all ~80+ hardcoded colors to CSS custom properties; this is the bottleneck everything else depends on
2. **`data-theme` attribute mechanism** -- Define `[data-theme="dark"]`, `[data-theme="light"]`, `[data-theme="mixed"]` variable sets
3. **WCAG AA contrast audit** -- Validate every variable pairing across all three palettes; fix failures before shipping

### Phase 2: Switching Infrastructure
4. **`localStorage` persistence** -- Store and retrieve theme preference
5. **Flash-prevention `<head>` script** -- Read preference and set `data-theme` before first paint
6. **`prefers-color-scheme` detection** -- Fallback when no stored preference
7. **Theme toggle button in header** -- Visible cycling control with `aria-label`
8. **Theme setting in settings modal** -- Full three-option control with labels

### Phase 3: Polish and Edge Cases
9. **Modal/tooltip theming** -- Ensure overlays inherit correct palette
10. **Scrollbar theming** -- `scrollbar-color` per mode
11. **Canvas/graph theme awareness** -- Read colors from CSS vars; redraw on theme change
12. **Branch color opacity adaptation** -- Per-theme opacity levels for annotation spans
13. **JS `BRANCH_COLORS` migration** -- Replace hardcoded hex with CSS variable reads
14. **Smooth CSS transition** -- `transition` on major containers, guarded by `prefers-reduced-motion`
15. **`prefers-color-scheme` live listener** -- Follow OS changes in real time

**Defer:** High-contrast mode, per-panel customization, custom color editor, View Transitions API animation -- none of these are needed for a complete, polished v1.

## Sources

- [web.dev: Building a theme switch component](https://web.dev/building-a-theme-switch-component/) -- HIGH confidence (Google reference implementation)
- [web.dev: Color themes with Baseline CSS features](https://web.dev/patterns/theming/theme-switch) -- HIGH confidence
- [MDN: prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-color-scheme) -- HIGH confidence
- [MDN: light-dark()](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/light-dark) -- HIGH confidence (used to evaluate and reject for this use case)
- [MDN: scrollbar-color](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/scrollbar-color) -- HIGH confidence
- [Can I Use: light-dark()](https://caniuse.com/mdn-css_types_color_light-dark) -- HIGH confidence (browser support data)
- [Smashing Magazine: Inclusive Dark Mode](https://www.smashingmagazine.com/2025/04/inclusive-dark-mode-designing-accessible-dark-themes/) -- MEDIUM confidence
- [CSS-Tricks: Complete Guide to Dark Mode](https://css-tricks.com/a-complete-guide-to-dark-mode-on-the-web/) -- MEDIUM confidence
- [Whitep4nth3r: Best theme toggle in JavaScript](https://whitep4nth3r.com/blog/best-light-dark-mode-theme-toggle-javascript/) -- MEDIUM confidence
- [DEV Community: Three-way dark mode switch](https://dev.to/colinaut/dark-mode-three-way-switch-40e) -- MEDIUM confidence (three-mode pattern validation)
- [Dylan Smith: The UX of dark mode toggles](https://dylanatsmith.com/wrote/the-ux-of-dark-mode-toggles) -- MEDIUM confidence (persistence strategy)
- [BOIA: Dark mode doesn't satisfy WCAG contrast requirements](https://www.boia.org/blog/offering-a-dark-mode-doesnt-satisfy-wcag-color-contrast-requirements) -- MEDIUM confidence (accessibility requirements)
- [Greeden blog: Complete Accessibility Guide for Dark Mode](https://blog.greeden.me/en/2026/02/23/complete-accessibility-guide-for-dark-mode-and-high-contrast-color-design-contrast-validation-respecting-os-settings-icons-images-and-focus-visibility-wcag-2-1-aa/) -- MEDIUM confidence
