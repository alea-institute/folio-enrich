# Technology Stack: CSS Theme System

**Project:** FOLIO Enrich Theme System
**Researched:** 2026-03-22

## Recommended Stack

This is a pure CSS + vanilla JS implementation. No new dependencies. Every technique below has 95%+ browser support.

### Core Technique: `data-theme` Attribute + CSS Custom Properties

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `data-theme` attribute on `<html>` | HTML5 | Theme mode selector | Industry standard (Bootstrap 5.3, Tailwind, Bulma all use this pattern). CSS attribute selectors `[data-theme="dark"]` cleanly scope variable overrides. Works with three+ modes unlike `light-dark()`. |
| CSS Custom Properties | Baseline since 2017 | All color values | Already partially adopted (17 vars at `:root`, light overrides on `.panel-right`/`.panel-detail`). Cascade naturally through DOM — child elements inherit without explicit re-declaration. |
| `localStorage` | Web Storage API | Persist theme choice | Already used in the codebase for 6+ settings (debugMode, showThinking, panel states). Zero-dependency persistence that survives page refresh. |
| `prefers-color-scheme` media query | Baseline since 2020 | OS preference detection | Respects user's system-level dark/light setting as default when no explicit choice stored. Combined with `matchMedia` listener for real-time OS theme changes. |
| `color-scheme` CSS property | Baseline since 2022 | Native UA element theming | Tells the browser to style form controls, scrollbars, and selection colors natively for dark or light mode. Set alongside `data-theme` for free UA theming. |

**Confidence: HIGH** — All techniques are Baseline Widely Available with 95%+ support. This is the exact pattern used by Bootstrap 5.3, Tailwind CSS, and every major design system.

### Why NOT `light-dark()` CSS Function

| Decision | Rationale |
|----------|-----------|
| **Do not use `light-dark()`** | Only supports two modes (light/dark) via the `color-scheme` property. Cannot express a "Mixed" mode where left panels are dark and right panels are light. The function is also only Baseline Newly Available (May 2024, 87% support) — not widely available until ~Nov 2026. The `data-theme` + custom properties approach is both more flexible and more compatible. |

### Why NOT OKLCH / `color-mix()`

| Decision | Rationale |
|----------|-----------|
| **Do not adopt OKLCH or `color-mix()` in this milestone** | The existing codebase uses hex and RGBA throughout (~690 color references). Converting to OKLCH is a separate refactor with no theme-switching benefit. `color-mix()` is useful for palette generation but adds complexity without solving the core problem of three-mode switching. Keep hex/RGBA for now; OKLCH migration is a future optimization. |

## CSS Architecture

### Token Layer Strategy

Use a two-layer custom property system: **raw palette tokens** and **semantic tokens**.

```css
/* Layer 1: Raw palette (never used directly in components) */
:root {
  --palette-dark-bg: #0f1117;
  --palette-dark-surface: #1a1d27;
  --palette-light-bg: #ffffff;
  --palette-light-surface: #f5f6f8;
  /* ... */
}

/* Layer 2: Semantic tokens (what components actually use) */
:root,
[data-theme="dark"] {
  --bg: var(--palette-dark-bg);
  --surface: var(--palette-dark-surface);
  /* ... */
}

[data-theme="light"] {
  --bg: var(--palette-light-bg);
  --surface: var(--palette-light-surface);
  /* ... */
}
```

**Rationale:** Separating raw values from semantic names means changing a color value happens in one place (Layer 1), and adding a new theme mode means only remapping Layer 2 assignments. The existing `:root` vars and `.panel-right`/`.panel-detail` overrides already follow this pattern implicitly — this formalizes it.

**Confidence: HIGH** — This is the standard approach documented by every major CSS methodology (ITCSS, Open Props, design token specs).

### Three-Mode Implementation Pattern

```css
/* Dark mode (default, matches current :root) */
:root,
[data-theme="dark"] {
  --bg: #0f1117;
  --surface: #1a1d27;
  --text: #e4e6f0;
  --text-dim: #8b8fa3;
  /* ... all 17+ semantic tokens */
  color-scheme: dark;
}

/* Light mode */
[data-theme="light"] {
  --bg: #ffffff;
  --surface: #f5f6f8;
  --text: #1a1a2e;
  --text-dim: #6b6b80;
  /* ... all 17+ semantic tokens */
  color-scheme: light;
}

/* Mixed mode: dark root + light overrides on right/detail panels */
[data-theme="mixed"] {
  /* Root stays dark (inherits from :root defaults) */
  color-scheme: dark;
}
[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail {
  --bg: #ffffff;
  --surface: #f5f6f8;
  --text: #1a1a2e;
  --text-dim: #6b6b80;
  /* ... light semantic tokens */
  color-scheme: light;
}
```

**Why this specificity order works:** `[data-theme="mixed"] .panel-right` has higher specificity than `:root` or `[data-theme="dark"]`, so the light overrides win inside those panels. This is exactly the pattern `.panel-right` already uses — we are just moving it under a `data-theme` gate.

**Confidence: HIGH** — Directly extends the existing architecture. The codebase already does this with `.panel-right { --bg: #ffffff; }`.

### Flash-Prevention Script (FOUC / FART)

Place a **synchronous inline `<script>`** in `<head>`, before the `<style>` block:

```html
<head>
  <script>
    // Runs synchronously before first paint — prevents flash
    (function() {
      var stored = localStorage.getItem('folio-enrich-theme');
      if (stored && ['dark','light','mixed'].indexOf(stored) !== -1) {
        document.documentElement.setAttribute('data-theme', stored);
      } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.documentElement.setAttribute('data-theme', 'light');
      } else {
        document.documentElement.setAttribute('data-theme', 'mixed');
      }
    })();
  </script>
  <style>
    /* CSS follows... */
  </style>
</head>
```

**Key details:**
- Must be inline (not `defer`, not `async`, not external) to execute before render
- Must be placed before `<style>` so the attribute exists when CSS is parsed
- Uses `var` (not `const`/`let`) for maximum compatibility in this critical-path script
- Default for new users with dark OS preference: `mixed` (backward compatible with current UI)
- Default for new users with light OS preference: `light`
- localStorage key: `folio-enrich-theme` (namespaced to avoid collisions)

**Confidence: HIGH** — This is the universal technique used by every framework (Next.js, Astro, SvelteKit) and documented extensively. The V8 blog, PicoCSS, and CSS-Tricks all recommend this exact approach.

### OS Preference Change Listener

```javascript
// Listen for OS theme changes (user toggles system dark mode)
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  // Only auto-switch if user hasn't explicitly chosen a theme
  if (!localStorage.getItem('folio-enrich-theme')) {
    const newTheme = e.matches ? 'mixed' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
  }
});
```

**Confidence: HIGH** — `matchMedia` change events are Baseline since 2020.

### Canvas Color Integration

The graph canvas has only 2 hardcoded colors (`ctx.fillStyle = 'rgba(59,100,224,0.4)'` and `ctx.strokeStyle = 'rgba(228,230,240,0.5)'`). Use `getComputedStyle` to read CSS variables at render time:

```javascript
function getThemeColor(varName) {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(varName).trim();
}

// In canvas render:
ctx.fillStyle = getThemeColor('--accent') + '66'; // with alpha
ctx.strokeStyle = getThemeColor('--text') + '80';
```

**Alternative (better perf):** Cache resolved colors in a theme object, refresh on theme change:

```javascript
let themeColors = {};
function refreshThemeColors() {
  const s = getComputedStyle(document.documentElement);
  themeColors.accent = s.getPropertyValue('--accent').trim();
  themeColors.text = s.getPropertyValue('--text').trim();
}
// Call on theme switch and on DOMContentLoaded
```

**Confidence: HIGH** — `getComputedStyle` for custom properties is universal. The caching approach avoids per-frame reflow costs.

### JS `BRANCH_COLORS` Synchronization

The `BRANCH_COLORS` object has ~26 hardcoded hex values that duplicate the CSS `--branch-*` variables. Two options:

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Read from CSS vars at runtime** | Single source of truth, auto-syncs with theme | `getComputedStyle` call per branch per render | Use for canvas/graph rendering |
| **Keep JS object, add theme variants** | Fast lookup, no DOM queries | Duplication between CSS and JS | Use for non-canvas tooltip/badge coloring where perf matters |

**Recommended hybrid:** Keep `BRANCH_COLORS` as the JS lookup for DOM element coloring (which already works via CSS variables on those elements). For canvas rendering only, read from `getComputedStyle` via a cached theme object refreshed on theme change.

**Confidence: MEDIUM** — The hybrid is pragmatic but adds a maintenance surface. If branch colors do NOT change between themes (they likely should not — branch identity colors are semantic, not theme-dependent), then the JS object can stay as-is with zero changes.

### Scrollbar Theming

Current state: 6 hardcoded scrollbar colors (`#c0c0cc`, `#9090a0`) on `.panel-right`, `.panel-detail`, and `.modal`. These must use CSS variables.

```css
/* Global dark scrollbar */
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

/* Token definitions */
[data-theme="dark"] {
  --scrollbar-thumb: var(--border);       /* #2e3348 */
  --scrollbar-thumb-hover: var(--accent-dim); /* #4a5fa0 */
}
[data-theme="light"] {
  --scrollbar-thumb: #c0c0cc;
  --scrollbar-thumb-hover: #9090a0;
}
```

Also add `color-scheme: dark` or `color-scheme: light` to get native scrollbar theming in Firefox and future Chrome versions (Firefox already respects `color-scheme` for scrollbar coloring).

**Confidence: HIGH** — WebKit scrollbar pseudo-elements are universally supported. `color-scheme` for native scrollbar theming is a progressive enhancement.

## WCAG AA Contrast Validation

### Build-Time / Dev-Time Validation

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **Inline JS contrast checker (~30 lines)** | Validate all theme color pairs at dev time | Run once during theme development to verify all fg/bg combinations pass 4.5:1 (normal) / 3:1 (large) |
| **WebAIM Contrast Checker** (web tool) | Manual spot-check individual pairs | During design phase for new colors |
| **Chrome DevTools** (built-in) | Real-time contrast overlay on inspected elements | During development — shows contrast ratio in color picker |

### Inline Contrast Validation Function

Embed a dev-only utility (removable for production or gated behind `debugMode`):

```javascript
function luminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map(c => {
    c = c / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function contrastRatio(hex1, hex2) {
  const parse = h => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
  const l1 = luminance(...parse(hex1));
  const l2 = luminance(...parse(hex2));
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

// Validate all critical pairs
function validateThemeContrast() {
  const s = getComputedStyle(document.documentElement);
  const bg = s.getPropertyValue('--bg').trim();
  const text = s.getPropertyValue('--text').trim();
  const textDim = s.getPropertyValue('--text-dim').trim();
  const accent = s.getPropertyValue('--accent').trim();

  const pairs = [
    ['--text on --bg', text, bg, 4.5],
    ['--text-dim on --bg', textDim, bg, 4.5],
    ['--accent on --bg', accent, bg, 4.5],
  ];
  pairs.forEach(([name, fg, background, min]) => {
    const ratio = contrastRatio(fg, background);
    const pass = ratio >= min;
    console[pass ? 'log' : 'warn'](
      `${pass ? 'PASS' : 'FAIL'} ${name}: ${ratio.toFixed(2)}:1 (min ${min}:1)`
    );
  });
}
```

**Confidence: HIGH** — The WCAG relative luminance formula is a W3C standard (G17/G18 techniques). This is ~30 lines with no dependencies.

### Known Contrast Risks (from PROJECT.md)

| Pair | Current Ratio | Threshold | Status |
|------|--------------|-----------|--------|
| `--text-dim` (#8b8fa3) on `--bg` (#0f1117) | ~5.0:1 | 4.5:1 | Passes but marginal |
| `--accent` (#6c8cff) on dark `--bg` (#0f1117) | ~5.8:1 | 4.5:1 | Passes |
| `--accent` (#3b64e0) on light `--bg` (#ffffff) | ~4.6:1 | 4.5:1 | Barely passes — monitor |
| `--text-dim` (#6b6b80) on light `--bg` (#ffffff) | ~4.7:1 | 4.5:1 | Barely passes — monitor |
| Branch colors on dark bg | Varies | 3:1 (large) | Some may fail — must validate all 26 |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Theme selector | `data-theme` attribute | CSS class (`.theme-dark`) | Attribute selectors are semantically clearer, avoid class collision risk, and match the Bootstrap/Tailwind convention |
| Theme selector | `data-theme` attribute | `light-dark()` function | Only supports 2 modes, tied to `color-scheme` property, 87% browser support vs 99%+ for data attributes |
| Color format | Keep hex/RGBA | OKLCH / `color-mix()` | ~690 color references to convert. Separate refactor with no theme-switching benefit. OKLCH is a good future migration but orthogonal to this milestone. |
| Persistence | `localStorage` | Cookie | Cookies add HTTP overhead, require server awareness, and the codebase already uses localStorage for 6+ settings |
| Persistence | `localStorage` | URL parameter | Breaks shareability (shared links force theme on recipient) |
| FOUC prevention | Inline `<script>` in `<head>` | `<link media="(prefers-color-scheme: dark)">` | Link-based approach only handles 2 modes and requires separate CSS files (violates single-file constraint) |
| Contrast validation | Inline JS function | External tool (axe, Lighthouse) | External tools cannot validate CSS custom property pairs across theme modes. The inline function validates the actual computed colors at runtime. |

## Implementation Notes

### What to Hardcode-Audit

Before implementing, audit and convert these hardcoded color categories to CSS variables:

1. **Scrollbar colors** — 6 instances of `#c0c0cc` and `#9090a0` (lines 357-358, 385-386, 2034-2035)
2. **Detail section title** — `color: #6b6b80` (line 393), `border-bottom: 1px solid #e2e4ea` (line 394)
3. **Canvas fills** — `ctx.fillStyle = 'rgba(59,100,224,0.4)'` (line 8360), `ctx.strokeStyle = 'rgba(228,230,240,0.5)'` (line 8373)
4. **Chip dot gray** — `background: #555` (line 107)
5. **Edge chevron color** — `color: #fff` (line 296)
6. **JS fallback colors** — `BRANCH_COLORS` values and `'#6b6b80'` / `'#3b64e0'` fallbacks (~15 instances)
7. **Panel-right `p[style]` override** — `color: #6b6b80 !important` (line 361) — already uses `!important` to fight inline styles

### Installation / Setup

```bash
# No installation needed — pure CSS + vanilla JS
# No new npm/pip dependencies
# No build step changes
```

## Sources

- [MDN: light-dark() function](https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/light-dark) — Confirmed `light-dark()` only responds to `color-scheme` property, not `data-theme`
- [MDN: color-scheme property](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/color-scheme) — Native UA element theming
- [MDN: prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme) — OS preference detection
- [MDN: CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties) — Variable scoping and cascade
- [Bootstrap 5.3 Color Modes](https://getbootstrap.com/docs/5.3/customize/color-modes/) — `data-bs-theme` pattern reference
- [CSS-Tricks: Flash of inAccurate coloR Theme](https://css-tricks.com/flash-of-inaccurate-color-theme-fart/) — FOUC/FART prevention
- [Aaron Gustafson: Passing CSS Theme to Canvas](https://www.aaron-gustafson.com/blog/notebook/passing-your-css-theme-to-canvas/) — `getComputedStyle` for canvas colors
- [W3C WCAG G18 Technique](https://www.w3.org/WAI/WCAG21/Techniques/general/G18) — Contrast ratio calculation formula
- [Smashing Magazine: CSS Custom Properties in the Cascade](https://www.smashingmagazine.com/2019/07/css-custom-properties-cascade/) — Scoped property override patterns
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) — Manual contrast validation tool
