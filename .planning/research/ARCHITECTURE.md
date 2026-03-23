# Architecture Patterns

**Domain:** CSS Theme System for Large Single-File Vanilla JS Application
**Researched:** 2026-03-22

## Recommended Architecture

### System Overview

```
<html data-theme="dark|light|mixed">
  <head>
    <script> (flash prevention: reads localStorage, sets data-theme) </script>
    <style>
      :root { --palette-*: raw values }
      [data-theme="dark"]  { --bg: ...; --text: ...; color-scheme: dark; }
      [data-theme="light"] { --bg: ...; --text: ...; color-scheme: light; }
      [data-theme="mixed"] { color-scheme: dark; }
      [data-theme="mixed"] .panel-right,
      [data-theme="mixed"] .panel-detail { --bg: ...; --text: ...; color-scheme: light; }
      /* Components use var(--bg), var(--text), etc. -- never raw hex */
    </style>
  </head>
  <body>
    <header> (theme toggle button) </header>
    <main>
      <div class="panel panel-left">   (inherits from html) </div>
      <div class="panel panel-center"> (inherits from html) </div>
      <div class="panel panel-right">  (may override in mixed mode) </div>
      <div class="panel panel-detail"> (may override in mixed mode) </div>
    </main>
    <script>
      ThemeManager.init() // orchestrates toggle, persistence, OS detection
    </script>
  </body>
</html>
```

### Two-Layer Token Architecture

The theme system uses a two-layer design token architecture: palette primitives and semantic tokens. Each theme maps primitives to semantics.

```
Layer 1: Palette Primitives    --palette-dark-bg: #0f1117
         |
Layer 2: Semantic Tokens       --bg: var(--palette-dark-bg)
```

**Why two layers, not three.** A three-layer system (primitive -> semantic -> component) adds indirection that pays off in multi-team design systems with shared component libraries. For a single-file vanilla JS application with no component library, the component layer is unnecessary -- semantic tokens are already specific enough. If a component needs a unique mapping (e.g., tooltip background differs from page background), a targeted component token can be added case-by-case without establishing a full layer.

**Why not one layer.** Flat `:root` definitions (the current state) work for one theme but break when the same semantic name must resolve to different raw values per theme. The palette layer provides the raw values; theme selectors map them to semantics.

### Theme Cascade Strategy: `data-theme` Attribute

Use `data-theme` attribute on `<html>` for global theme, with scoped CSS selectors for per-panel overrides in Mixed mode.

```css
/* Layer 1: Raw palette -- define once in :root, never use in components */
:root {
  /* Dark palette */
  --palette-dark-bg: #0f1117;
  --palette-dark-surface: #1a1d27;
  --palette-dark-surface2: #242836;
  --palette-dark-surface3: #2e3348;
  --palette-dark-border: #2e3348;
  --palette-dark-text: #e4e6f0;
  --palette-dark-text-dim: #8b8fa3;
  --palette-dark-accent: #6c8cff;
  --palette-dark-accent-dim: #4a5fa0;

  /* Light palette */
  --palette-light-bg: #ffffff;
  --palette-light-surface: #f5f6f8;
  --palette-light-surface2: #ecedf1;
  --palette-light-surface3: #e2e4ea;
  --palette-light-border: #d0d2da;
  --palette-light-text: #1a1a2e;
  --palette-light-text-dim: #6b6b80;
  --palette-light-accent: #3b64e0;
  --palette-light-accent-dim: #5a7ae8;
}

/* Layer 2: Semantic tokens -- what components use */
[data-theme="dark"] {
  --bg: var(--palette-dark-bg);
  --surface: var(--palette-dark-surface);
  --text: var(--palette-dark-text);
  color-scheme: dark;
  /* ... */
}

[data-theme="light"] {
  --bg: var(--palette-light-bg);
  --surface: var(--palette-light-surface);
  --text: var(--palette-light-text);
  color-scheme: light;
  /* ... */
}

/* Mixed mode: dark globally, light on right/detail */
[data-theme="mixed"] {
  --bg: var(--palette-dark-bg);
  --surface: var(--palette-dark-surface);
  --text: var(--palette-dark-text);
  color-scheme: dark;
}
[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail {
  --bg: var(--palette-light-bg);
  --surface: var(--palette-light-surface);
  --text: var(--palette-light-text);
  color-scheme: light;
}
```

**Why `data-theme` over class-based.** Both have identical CSS specificity (attribute selectors and class selectors are equal weight). `data-theme` was chosen because: (1) it is semantically correct -- theme is data about the element, not styling state; (2) it enforces single-value constraint (an element can have one `data-theme` value, but could accidentally accumulate multiple theme classes); (3) it matches the pattern used by Bootstrap 5.3+, Radix, and other major design systems, making it the current community standard. Performance differences between attribute and class selectors are unmeasurable in a single-file vanilla JS app.

**Why `color-scheme` is required.** Without the `color-scheme` CSS property, native browser elements (form inputs, `<select>` dropdowns, native scrollbars, selection highlights) will remain in the browser's default light style even in dark mode. Setting `color-scheme: dark` tells the UA to render these elements with dark chrome.

**Confidence:** HIGH (MDN docs, Bootstrap 5.3 source, Radix Themes source)

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Flash-prevention script** (inline JS in `<head>`) | Reads `localStorage` + OS preference, sets `data-theme` on `<html>` before first paint | `localStorage`, `matchMedia` API |
| **Palette primitives** (CSS `:root`) | Defines all raw color values -- dark palette, light palette, status colors, branch colors | Referenced by semantic token layer |
| **Semantic token layer** (CSS `[data-theme]` selectors) | Maps primitives to meaning (`--bg`, `--text`, `--accent`, etc.) per theme mode | Referenced by all CSS rules and `var()` usage |
| **Component tokens** (CSS, case-by-case) | Optional per-component overrides where semantic tokens are insufficient (`--tooltip-bg`, `--graph-node-bg`, `--scrollbar-thumb`) | Referenced by specific component CSS rules |
| **ThemeManager** (JS singleton) | Orchestrates theme switching: toggle cycling, `localStorage` writes, OS listener, canvas color refresh, UI updates | `data-theme` attribute, `localStorage`, `matchMedia`, canvas render functions, toggle icon |
| **Theme toggle button** (UI) | Header button; click cycles Dark -> Light -> Mixed | ThemeManager |
| **Settings modal theme section** (UI) | Radio/select for explicit theme selection | ThemeManager |
| **Canvas Theme Bridge** (JS) | Caches resolved CSS variable values for canvas rendering; refreshes on theme change | `getComputedStyle`, ThemeManager change callback |
| **Branch Color Resolver** (JS) | Replaces hardcoded `BRANCH_COLORS` object with CSS-variable-backed lookups | `getComputedStyle`, provides colors to tooltip/pill/badge generation |

### Data Flow

```
User clicks toggle   -->  ThemeManager.cycle()
                            |
                            +--> document.documentElement.setAttribute('data-theme', newTheme)
                            |      |
                            |      +--> CSS cascade instantly resolves all var() values
                            |      |     (browser does this automatically, zero JS needed)
                            |      |
                            |      +--> color-scheme property updates UA form elements
                            |
                            +--> localStorage.setItem('folio-enrich-theme', newTheme)
                            |
                            +--> refreshCanvasColors() --> getComputedStyle reads new vars
                            |      |
                            |      +--> graph/minimap canvas redraws with new palette
                            |
                            +--> updateToggleIcon(newTheme) --> swaps SVG icon + aria-label

OS theme changes      -->  matchMedia listener fires
                            |
                            +--> if no explicit localStorage preference:
                                   ThemeManager.setTheme(osIsDark ? 'mixed' : 'light')
```

**Key insight:** CSS custom properties cascade automatically. When `data-theme` changes, every element using `var(--bg)` updates instantly with zero JavaScript. The JS listeners are only needed for three things: (1) canvas rendering, which cannot read CSS variables natively; (2) HTML strings built in JS that use hardcoded hex values instead of `var()` references; (3) updating the toggle button icon/label.

### FOUC Prevention (Critical Path)

An inline `<script>` in `<head>` must execute before the browser's first paint.

```html
<head>
  <!-- Before any <style> or <link> -->
  <script>
    (function() {
      var t = localStorage.getItem('folio-enrich-theme');
      if (!t) {
        t = window.matchMedia('(prefers-color-scheme: light)').matches
          ? 'light' : 'mixed';
      }
      document.documentElement.setAttribute('data-theme', t);
    })();
  </script>
  <style>
    /* ...all CSS including theme definitions... */
  </style>
</head>
```

**Why before `<style>`.** The inline script sets `data-theme` before the browser encounters the stylesheet. When the stylesheet is parsed, the correct theme's variable values are already active. No flash occurs because the browser never renders with wrong values.

**Why `mixed` as default (not `dark`).** The current application renders in mixed mode. First-time users with no `localStorage` value who have no OS light preference should see the existing visual behavior. Users with `prefers-color-scheme: light` get light mode. This preserves backward compatibility.

**Confidence:** HIGH (well-documented pattern, used by Next.js, Astro, Hugo, and many others)

## Patterns to Follow

### Pattern 1: Semantic Variable Naming Convention

**What:** Keep the existing `--category` and `--category-modifier` naming that the codebase already uses.

**When:** Naming every CSS custom property in the system.

**Naming taxonomy for this project:**

```css
/* Primitives (palette layer) -- prefixed to prevent direct use */
--palette-dark-bg: #0f1117;
--palette-light-bg: #ffffff;

/* Semantics -- what the color means (existing names preserved) */
--bg:               /* page/panel background */
--surface:          /* elevated surface (headers, cards) */
--surface2:         /* secondary surface (inputs, chips) */
--surface3:         /* tertiary surface (hover states) */
--border:           /* borders and dividers */
--text:             /* primary text */
--text-dim:         /* secondary/muted text */
--accent:           /* primary interactive color */
--accent-dim:       /* secondary interactive color */
--green:            /* success/positive */
--orange:           /* warning/caution */
--red:              /* error/danger */
--cyan:             /* info */
--purple:           /* special (properties) */

/* Branch semantics (domain-specific) */
--branch-actor:     /* Actor / Player branch color */
--branch-area-of-law:
/* ...26 total branch colors... */

/* Highlights (annotation-specific) */
--highlight:
--highlight-confirmed:
--highlight-preliminary:
--highlight-rejected:

/* Confidence tiers */
--conf-high-text:
--conf-high-bg:
--conf-mid-text:
--conf-mid-bg:
--conf-low-text:
--conf-low-bg:

/* Component tokens (only where semantic tokens are insufficient) */
--tooltip-bg:       /* may differ from --bg in some themes */
--graph-node-bg:    var(--surface2);
--graph-edge:       var(--accent);
--graph-edge-see-also: var(--purple);
--scrollbar-thumb:  /* per-theme specific */
--scrollbar-thumb-hover:
```

**Rationale:** The existing `--bg`, `--text`, `--accent` names are already good semantic tokens. Keep them. The new work is (a) adding the palette layer underneath, (b) adding confidence tier and branch color tokens that adapt per theme, and (c) adding targeted component tokens only where a component's color mapping genuinely differs from the semantic default.

### Pattern 2: Scoped Variable Overrides for Mixed Mode

**What:** Override semantic tokens on specific DOM subtrees using CSS cascade.

**When:** Mixed mode -- where left panels use dark palette and right panels use light palette.

**Why:** CSS custom properties naturally cascade through the DOM tree. Setting `--bg` on `.panel-right` makes all children of that panel see the light value without any additional selectors.

```css
[data-theme="mixed"] {
  --bg: var(--palette-dark-bg);
  --surface: var(--palette-dark-surface);
  --text: var(--palette-dark-text);
  color-scheme: dark;
}

[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail {
  --bg: var(--palette-light-bg);
  --surface: var(--palette-light-surface);
  --text: var(--palette-light-text);
  color-scheme: light;
}
```

**This is exactly what the codebase already does** with `.panel-right { --bg: #ffffff; }` -- the architecture formalizes it under `data-theme` control and eliminates the current duplication between `.panel-right` and `.panel-detail` (which are currently identical 15-line blocks).

### Pattern 3: Branch Colors as Adaptive Tokens

**What:** Branch colors need different values per theme. Dark backgrounds need lighter/more saturated colors; light backgrounds need darker/less saturated colors.

**When:** Rendering branch-colored badges, pills, borders, and graph nodes.

**Key realization from codebase analysis:** The project already has two complete sets of branch colors -- the CSS variables (dark palette, `:root` lines 30-41) and the JS `BRANCH_COLORS` object (light palette, lines 3120-3148). These are the two theme palettes. They need to be unified into CSS variable definitions for each theme, eliminating the JS object entirely.

```css
[data-theme="dark"], [data-theme="mixed"] {
  --branch-actor: #5ec4d4;          /* bright on dark */
  --branch-area-of-law: #e8a54c;
  /* ... */
}

[data-theme="light"] {
  --branch-actor: #1e6fa0;          /* darker on light */
  --branch-area-of-law: #1a5276;
  /* ... */
}

[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail {
  --branch-actor: #1e6fa0;
  --branch-area-of-law: #1a5276;
  /* light variants for right/detail panels */
}
```

### Pattern 4: ThemeManager Singleton

**What:** A single JS object that owns all theme state and operations.

**When:** Always -- centralizes theme logic instead of scattering it across event handlers.

```javascript
const ThemeManager = {
  MODES: ['dark', 'light', 'mixed'],
  STORAGE_KEY: 'folio-enrich-theme',

  init() {
    // Flash-prevention script already set data-theme; read it
    this.current = document.documentElement.getAttribute('data-theme') || 'mixed';
    this._bindToggle();
    this._bindSettingsModal();
    this._bindOSListener();
    this._refreshCanvasColors();
  },

  setTheme(mode) {
    this.current = mode;
    document.documentElement.setAttribute('data-theme', mode);
    localStorage.setItem(this.STORAGE_KEY, mode);
    this._updateToggleIcon(mode);
    this._refreshCanvasColors();
  },

  cycle() {
    const idx = this.MODES.indexOf(this.current);
    this.setTheme(this.MODES[(idx + 1) % this.MODES.length]);
  },

  _bindOSListener() {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem(this.STORAGE_KEY)) {
        this.setTheme(e.matches ? 'mixed' : 'light');
      }
    });
  },

  _refreshCanvasColors() {
    const s = getComputedStyle(document.documentElement);
    _canvasTheme.nodeColor = s.getPropertyValue('--graph-node-bg').trim() || '#242836';
    _canvasTheme.edgeColor = s.getPropertyValue('--graph-edge').trim() || '#3b64e0';
    _canvasTheme.viewportStroke = s.getPropertyValue('--text').trim() || '#e4e6f0';
    // Trigger graph redraw if visible
    if (document.getElementById('graphModal')?.classList.contains('visible')) {
      renderMinimap();
    }
  },
};
```

### Pattern 5: Canvas Theme Bridge via getComputedStyle

**What:** Canvas 2D rendering cannot use `var()` references. Extract CSS variable values into a JS object, then use that object for all `ctx.fillStyle` / `ctx.strokeStyle` assignments.

**When:** Any canvas drawing (minimap, graph overlays).

```javascript
const _canvasTheme = {};

function refreshCanvasTheme() {
  const style = getComputedStyle(document.documentElement);
  _canvasTheme.nodeColor = style.getPropertyValue('--graph-node-bg').trim() || '#242836';
  _canvasTheme.edgeColor = style.getPropertyValue('--graph-edge').trim() || '#3b64e0';
  _canvasTheme.viewportStroke = style.getPropertyValue('--text').trim() || '#e4e6f0';
}

// Use in rendering (replacing hardcoded rgba values)
function renderMinimap() {
  // ...
  ctx.fillStyle = _canvasTheme.nodeColor;      // was: 'rgba(59,100,224,0.4)'
  ctx.strokeStyle = _canvasTheme.viewportStroke; // was: 'rgba(228,230,240,0.5)'
}
```

**Source:** Aaron Gustafson's "Passing Your CSS Theme to Canvas" pattern, adapted for manual theme switching.

**Critical:** Cache computed values -- never call `getComputedStyle` inside `requestAnimationFrame` or render loops. Refresh only on theme change.

**Confidence:** HIGH (documented pattern with direct browser API)

### Pattern 6: Eliminating Hardcoded Colors in JS Template Strings

**What:** Replace hex color literals in JS-generated HTML with `var()` references or CSS classes.

**The problem, quantified:** The codebase has ~124 instances of `style="...color..."` or `style="...background..."` in JS template strings, plus ~411 hardcoded hex values in CSS rules.

**Strategy, in preference order:**

```javascript
// BEST: CSS class (fully participates in cascade, can be overridden per theme)
html += `<div class="meta-hint">...</div>`;
// CSS: .meta-hint { color: var(--text-dim); font-size: 12px; }

// GOOD: var() in inline style (theme-aware but cannot be overridden by CSS)
html += `<div style="color:var(--text-dim);font-size:12px">...</div>`;

// BAD: hardcoded hex (theme-blind, must be eliminated)
html += `<div style="color:#6b6b80;font-size:12px">...</div>`;
```

For branch colors set via JS (e.g., `div.style.borderLeftColor = branchHex`), use CSS custom properties on the element:
```javascript
div.style.setProperty('--branch-color', branchHex);
// CSS: .graph-node { border-left-color: var(--branch-color); }
```

### Pattern 7: Scrollbar Theming with Progressive Enhancement

**What:** Use `scrollbar-color` CSS property as the standard, with `::-webkit-scrollbar` as fallback.

```css
[data-theme="dark"] {
  --scrollbar-thumb: #3a3f54;
  --scrollbar-track: transparent;
}
[data-theme="light"] {
  --scrollbar-thumb: #c0c0cc;
  --scrollbar-track: transparent;
}

.panel-body {
  scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
  scrollbar-width: thin;
}

/* WebKit fallback */
.panel-body::-webkit-scrollbar { width: 5px; }
.panel-body::-webkit-scrollbar-track { background: var(--scrollbar-track); }
.panel-body::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
```

**Current state:** Three separate scrollbar implementations exist (global, light panels, modal) -- two of them hardcoded. All should converge on `var(--scrollbar-thumb)`.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Transition on body/html for Theme Switch

**What:** Adding `transition: background-color 0.3s, color 0.3s` to `body` or `html`.
**Why bad:** Forces the browser to animate EVERY element's background and color simultaneously. On a 9,668-line file with hundreds of styled elements, this causes jank, intermediate color flashes, and elements transitioning at different rates.
**Instead:** Apply theme changes instantly (no transition). If subtle feedback is desired, animate only the toggle button itself.

### Anti-Pattern 2: Duplicating CSS Rules Per Theme

**What:** Writing separate rule blocks for each theme:
```css
/* BAD */
[data-theme="dark"] .header-btn { background: #242836; color: #8b8fa3; }
[data-theme="light"] .header-btn { background: #ecedf1; color: #6b6b80; }
```
**Why bad:** Triples the CSS volume. Every component needs N copies for N themes.
**Instead:** Write component rules ONCE using `var()`, and define variables per theme.

### Anti-Pattern 3: Mixing Hardcoded and Variable Colors in the Same Component

**What:** `.graph-node { background: var(--surface2); }` but `.graph-node:hover { border-color: #5a7ae8; }`.
**Why bad:** Theme switch updates the variable-based properties but hardcoded values stay fixed. The current codebase has this problem extensively.
**Instead:** Convert all color values in a component's CSS rules to variables at the same time. Partial conversion creates false confidence that theming works.

### Anti-Pattern 4: Using `!important` for Theme Overrides

**What:** `.panel-right .panel-body p[style] { color: #6b6b80 !important; }` (line 361).
**Why bad:** Exists to override JS-generated inline styles. It fights the cascade instead of fixing the root cause, and the hardcoded hex is theme-blind.
**Instead:** Fix the JS that generates the inline style to use `var(--text-dim)`, then remove the `!important` rule.

### Anti-Pattern 5: Duplicating Variable Blocks

**What:** `.panel-right` and `.panel-detail` (lines 335-383) contain identical 15+ variable overrides.
**Why bad:** Any change must be made twice.
**Instead:** In Mixed mode, use a single grouped selector: `[data-theme="mixed"] .panel-right, [data-theme="mixed"] .panel-detail { /* shared overrides */ }`.

### Anti-Pattern 6: Reading getComputedStyle in Render Loops

**What:** Calling `getComputedStyle(el).getPropertyValue('--accent')` inside `requestAnimationFrame`.
**Why bad:** `getComputedStyle` triggers style recalculation. At 60fps this causes continuous reflow.
**Instead:** Cache resolved values in a JS object. Refresh only on theme change.

### Anti-Pattern 7: Inline Styles for Theme Colors in JS

**What:** Setting `element.style.color = '#6b6b80'` in JavaScript.
**Why bad:** Inline styles have highest specificity, overriding any CSS variable-based theming.
**Instead:** Use CSS classes that reference variables, or `element.style.setProperty('color', 'var(--text-dim)')`.

## Current State Audit

### What Already Uses CSS Variables (Theme-Ready)

| Component | Variable Usage | Status |
|-----------|---------------|--------|
| Body background/text | `var(--bg)`, `var(--text)` | Ready |
| Header | `var(--surface)`, `var(--border)`, `var(--accent)` | Ready |
| Panel structure | `var(--border)` | Ready |
| Status chips | `var(--surface2)`, `var(--text-dim)`, `var(--accent)` | Ready |
| Buttons (base) | `var(--surface2)`, `var(--border)`, `var(--text-dim)` | Ready |
| Highlight spans | `var(--highlight)`, `var(--highlight-confirmed)` | Ready |
| Graph node (base) | `var(--surface2)`, `var(--surface3)`, `var(--text)` | Partial (hover/focus hardcoded) |
| Scrollbars (global) | `var(--border)`, `var(--accent-dim)` | Ready |
| Pipeline progress | `var(--red)`, `var(--green)`, `var(--accent)` | Ready |
| Graph viewport | `var(--bg)` | Ready |

### What Uses Hardcoded Colors (Needs Migration)

| Component | Hardcoded Count | Severity | Notes |
|-----------|----------------|----------|-------|
| Tooltip system | ~25 hex values | High | Light-mode-only: `#1a1a2e`, `#6b6b80`, `#3b64e0`, `#555`, `#888` |
| Detail panel sections | ~20 hex values | High | `#6b6b80`, `#1a1a2e`, `#e2e4ea`, `#3b64e0` throughout |
| Confidence tiers | ~18 hex values | High | `#166534`, `#92400e`, `#991b1b`, `#dcfce7`, `#fef3c7`, `#fee2e2` |
| Modal system | ~15 hex values | High | `#ffffff`, `#1a1a2e`, `#c0c0cc`, `#3b64e0` |
| Graph modal/legend | ~12 hex values | Medium | `#1a1d27`, `#2e3348`, `#8b8fa3` (always dark context) |
| Ancestry tree | ~12 hex values | Medium | `#e8e9f0`, `#1a1a2e`, `#f0f0f5`, `#6b6b80` (always light context) |
| Feedback buttons | ~10 hex values | Medium | Green/red states: `#22c55e`, `#ef4444`, backgrounds |
| JS `BRANCH_COLORS` object | 26 values | High | Used in ~10 places for inline styles |
| JS template strings | ~40+ inline styles | High | `style="color:#6b6b80"` patterns throughout |
| Canvas rendering | 2 values | Low | `rgba(59,100,224,0.4)`, `rgba(228,230,240,0.5)` |
| SVG edge strokes | 2 values | Low | `#3b64e0`, `#7c3aed` in JS |
| Graph node JS styles | 1 value | Low | `borderLeftColor` from `BRANCH_COLORS` |
| POS legend swatches | 5 values | Low | Hardcoded in HTML attributes |
| Panel-specific scrollbars | 6 values | Low | `#c0c0cc`, `#9090a0` in 3 locations |

## Suggested Build Order

The theme system has clear dependency chains. Each phase builds on the previous, and intermediate states are visually stable.

### Phase 1: Foundation (No Visual Change)

**Build:** Palette primitives in `:root` + FOUC prevention script in `<head>` + `data-theme="mixed"` attribute + ThemeManager singleton (without toggle UI).

**Dependencies:** None -- this is the base layer.

**What changes visually:** Nothing. The existing `:root` dark variables and `.panel-right`/`.panel-detail` light overrides continue working unchanged. The `data-theme` attribute exists but no CSS selects on it yet.

**Why first:** Everything else depends on the attribute being present and the primitive tokens being defined. Doing this first with zero visual change proves the foundation is sound.

### Phase 2: Theme Variable Definitions (Semantic Layer)

**Build:** `[data-theme="dark"]`, `[data-theme="light"]`, `[data-theme="mixed"]` selectors with full semantic variable mappings. Replace `:root` semantic vars with `[data-theme]` scoped vars. Replace `.panel-right`/`.panel-detail` duplicated overrides with `[data-theme="mixed"]` grouped selector. Add `color-scheme` property.

**Dependencies:** Phase 1 (attribute must exist).

**What changes visually:** Mixed mode looks identical to current state. Dark and Light are now functional for components already using `var()`. Components with hardcoded colors will look wrong in non-mixed modes.

**Why second:** This is the core mechanism. Once semantic tokens resolve correctly per theme, every `var()`-based component switches themes automatically.

### Phase 3: Theme Toggle UI + Persistence

**Build:** Header toggle button (cycle: Dark -> Light -> Mixed), settings modal radio group, `localStorage` persistence, `prefers-color-scheme` default detection, toggle icon/label updates.

**Dependencies:** Phase 2 (themes must be defined to switch between them).

**What changes visually:** Users can switch themes. Variable-based components switch cleanly. Hardcoded-color components look wrong in non-mixed modes -- this is expected and visible, motivating Phase 4.

**Why third:** Provides immediate user-visible functionality and a testing mechanism for remaining migration work.

### Phase 4: CSS Hardcoded Color Migration

**Build:** Replace all ~411 hardcoded hex values in CSS rules with `var()` references. Add confidence tier tokens, scrollbar tokens, and any needed component tokens.

**Dependencies:** Phase 2 (semantic tokens must exist to reference).

**What changes visually:** Tooltips, modals, detail panel, confidence badges, ancestry tree, graph nodes, scrollbars all become theme-aware.

**Sub-order within Phase 4 (by user visibility):**
1. Confidence tier colors (appear everywhere, high visibility)
2. Tooltip system (appears on hover over any annotation)
3. Modal system (settings, graph, cascade, synthetic, demo)
4. Detail panel (ancestry tree, metadata grid, notes)
5. Graph components (node hover/focus, legend, edge colors)
6. Feedback buttons, POS legend, remaining scattered values

### Phase 5: JS Color Migration

**Build:** Replace `BRANCH_COLORS` object with CSS variable reads via `getComputedStyle`. Eliminate inline `style="color:#..."` in template strings. Implement Canvas Theme Bridge for minimap/edges.

**Dependencies:** Phase 2 (variables must exist to read), Phase 4 (CSS side should be done first).

**What changes visually:** JS-generated HTML respects themes. Canvas minimap and graph edges use theme colors. `BRANCH_COLORS` object is deleted.

**Sub-order within Phase 5:**
1. `BRANCH_COLORS` replacement (used in ~10 locations, highest impact)
2. Canvas Theme Bridge for minimap + SVG edges (2 locations)
3. Template string cleanup (replace ~40+ inline `style="color:#..."` with CSS classes or `var()`)

### Phase 6: Accessibility Audit + Branch Color Tuning

**Build:** WCAG AA contrast verification for all text/background combinations in all three modes. Adjust branch color palettes per theme. Address known risks: `--text-dim` on `--bg` (marginal), `--accent` in light mode (barely passes), branch colors on dark backgrounds.

**Dependencies:** Phases 4-5 (all colors must be variable-based before auditing is meaningful).

**Why last:** Auditing is meaningless until all hardcoded colors are eliminated. Running it earlier would miss problems and require re-running.

## Scalability Considerations

| Concern | Current (1 theme context) | At 3 themes | At future expansion |
|---------|--------------------------|-------------|---------------------|
| CSS size | ~2,456 lines | ~2,600 lines (+6% for theme blocks) | Each new theme adds ~50-80 lines of variable overrides |
| Theme switch perf | N/A | Instant (<1ms, browser resolves CSS vars natively) | No degradation; CSS custom property resolution is O(1) per property |
| JS bridge perf | N/A | One `getComputedStyle` call + ~10 property reads | Negligible cost; add properties as needed |
| Maintenance | Duplicated .panel-right/.panel-detail blocks | Primitives shared, only semantic mappings differ per theme | Adding "High Contrast" theme = 1 new `[data-theme]` block |
| Branch colors | 26 colors, 2 palettes split across CSS and JS | 26 colors x 2 palettes, unified in CSS | New branches need 2 color values per theme |
| Canvas colors | 2 hardcoded values | Cached theme bridge reads ~5 vars | Stable; graph rendering scope is fixed |

## Sources

- [MDN: CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties) -- Cascade, scoping, and inheritance behavior; HIGH confidence
- [MDN: color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/color-scheme) -- UA element theming; HIGH confidence
- [Aaron Gustafson: Passing CSS Theme to Canvas](https://www.aaron-gustafson.com/notebook/passing-your-css-theme-to-canvas/) -- Canvas + getComputedStyle pattern; HIGH confidence
- [Aleksandr Hovhannisyan: The Perfect Theme Switch](https://www.aleksandrhovhannisyan.com/blog/the-perfect-theme-switch/) -- FOUC prevention + localStorage pattern; HIGH confidence
- [Bootstrap 5.3 Color Modes](https://getbootstrap.com/docs/5.3/customize/color-modes/) -- data-bs-theme architecture reference; HIGH confidence
- [Smashing Magazine: Naming Best Practices for Design Tokens](https://www.smashingmagazine.com/2024/05/naming-best-practices/) -- Naming conventions; MEDIUM confidence
- [Imperavi: Designing Semantic Colors](https://imperavi.com/blog/designing-semantic-colors-for-your-system/) -- Semantic color architecture; MEDIUM confidence
- [Penpot: Developer's Guide to Design Tokens](https://penpot.app/blog/the-developers-guide-to-design-tokens-and-css-variables/) -- Token layer architecture; MEDIUM confidence
- [Alexander Cerutti: Guide to Theme Switching](https://medium.com/@cerutti.alexander/a-mostly-complete-guide-to-theme-switching-in-css-and-js-c4992d5fd357) -- data-theme vs class comparison; MEDIUM confidence
- Codebase analysis: `frontend/index.html` lines 9-41, 335-383, 3120-3148, 8337-8377 -- PRIMARY SOURCE
