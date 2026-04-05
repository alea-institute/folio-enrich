# Phase 2: Theme Switching & JS Integration - Research

**Researched:** 2026-04-02
**Domain:** Theme toggle UI, localStorage persistence, flash prevention, JS color migration, canvas/graph re-rendering
**Confidence:** HIGH

## Summary

Phase 2 wires up the theme system established in Phase 1 so users can actually switch themes. The work breaks into four distinct domains: (1) theme toggle UI in both the header bar and settings modal, (2) persistence via localStorage with flash-prevention and OS-preference detection, (3) migrating all ~107 hardcoded hex/rgba color references remaining in the JavaScript section (lines 2856-10093) to use CSS variables or a `getThemeColor()` helper, and (4) making the graph canvas and SVG edge rendering re-render with correct theme colors on theme change.

The current frontend at `frontend/index.html` (10,093 lines) already has the complete CSS variable system from Phase 1: palette primitives in `:root`, semantic tokens in `[data-theme="dark"]`, `[data-theme="light"]`, and `[data-theme="mixed"]` selectors, and 78 branch color variables (26 per theme). The `<html>` element has `data-theme="mixed"` hardcoded on line 2. The `BRANCH_COLORS` JS object at line 3531 contains 27 entries duplicating the light-theme branch colors. There are 134 hex values in the JS section, of which ~27 are the BRANCH_COLORS entries, ~6 are HTML entities (not colors), and ~101 are actual color values used in template literals, inline styles, and canvas operations.

The `color-scheme` CSS property (THSW-06) is not yet present anywhere in the file and must be added per theme to enable native scrollbar and form control theming.

**Primary recommendation:** Build a `getThemeColor(name)` helper that reads CSS variables via `getComputedStyle`, a `branchSlug(displayName)` converter for branch name lookups, and a `setTheme(theme)` function that sets `data-theme`, `color-scheme`, and persists to localStorage. Use a MutationObserver on `document.documentElement` filtered to `['data-theme']` to trigger graph re-renders when the theme changes.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Icon cycle button in header bar -- single button that cycles Dark -> Light -> Mixed on click. Shows current theme icon (moon / sun / split). Tooltip shows current theme + next on click. Minimal header footprint.
- **D-02:** `getThemeColor(varName)` helper function -- reads CSS variable values at runtime via `getComputedStyle(document.documentElement).getPropertyValue('--' + name)`. All JS template literal hex values replaced with calls to this helper.
- **D-03:** BRANCH_COLORS object eliminated entirely -- all branch color lookups use `getThemeColor('branch-' + branchSlug)`. Single source of truth (CSS vars). No cached JS object.
- **D-04:** Theme-adaptive canvas -- graph renders with theme-appropriate colors (not always-dark). Light theme gets light canvas background with adjusted node/edge colors.
- **D-05:** Re-render on theme switch -- MutationObserver watches `data-theme` attribute changes on `<html>`. When theme changes while graph modal is open, canvas re-renders with new theme colors immediately.
- **D-06:** Visual swatches in settings modal -- three clickable mini-preview rectangles showing Dark/Light/Mixed with representative background + text colors. Active swatch gets highlight border. Placed in an "Appearance" section of the existing settings modal.

### Claude's Discretion
- Flash-prevention script implementation details (THSW-04) -- inline `<head>` script that reads localStorage and sets `data-theme` before first paint
- `color-scheme` CSS property values per theme (THSW-06) -- `dark` for dark, `light` for light, mixed TBD
- Exact icon characters/SVGs for the theme toggle button
- Settings modal swatch styling details

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| THSW-01 | User can toggle theme via a control in the header bar | Toggle UI section: icon cycle button in `.header-right`, cycles Dark->Light->Mixed. Architecture Patterns provides `cycleTheme()` function and HTML structure. |
| THSW-02 | User can select theme (Dark/Light/Mixed) in the settings modal | Settings Modal section: "Appearance" section with three visual swatches added before existing "FOLIO Ontology" section. Code example provides swatch HTML/CSS. |
| THSW-03 | Theme choice persists across page reloads via localStorage | Persistence section: `localStorage.setItem('theme', value)` in `setTheme()`. Key name `'theme'` follows existing bare-key convention (like `'debugMode'`, `'detailPanelVisible'`). |
| THSW-04 | Flash-prevention inline script in `<head>` applies stored theme before first paint | Flash Prevention section: 6-line inline `<script>` between `</style>` (line 2855) and `</head>` (line 2856). Reads localStorage, falls back to `prefers-color-scheme`, sets `data-theme` attribute synchronously. |
| THSW-05 | New users without a stored preference default to OS `prefers-color-scheme` preference | Flash Prevention section: `window.matchMedia('(prefers-color-scheme: dark)').matches` check in the inline script. Dark OS -> dark theme, light OS -> light theme. No stored preference -> OS detection. |
| THSW-06 | `color-scheme` CSS property set per theme for native form control and scrollbar theming | color-scheme section: Add `color-scheme: dark` to `[data-theme="dark"]`, `color-scheme: light` to `[data-theme="light"]`, `color-scheme: dark` to `[data-theme="mixed"]` root (dark sidebar has scrollbars). Also set via JS in `setTheme()`. |
| JSIT-01 | All inline JS color assignments refactored to read from CSS variables or use theme-aware helper | JS Migration section: 101 hex values across ~80 lines. Categorized into semantic token mappings. `getThemeColor()` for canvas/computed values, `var(--token)` for template literal inline styles. |
| JSIT-02 | Canvas/graph re-renders with correct theme colors when theme changes | Graph Re-render section: MutationObserver on `data-theme`, calls `renderMinimap()` when graph modal is open. SVG edges and HTML nodes already use CSS variables from Phase 1 CSS; only canvas minimap needs JS re-render. |
| JSIT-03 | `BRANCH_COLORS` JS object eliminated or unified with CSS variable system | Branch Migration section: Replace all 13 BRANCH_COLORS lookups with `getThemeColor('branch-' + branchSlug(name))`. Delete the 27-entry object. Add `branchSlug()` converter function. |

</phase_requirements>

## Standard Stack

### Core
| Technology | Version | Purpose | Why Standard |
|------------|---------|---------|--------------|
| CSS `color-scheme` property | Baseline (all browsers since Jan 2022) | Native scrollbar/form theming per mode | Eliminates need for custom scrollbar CSS; browser handles dark/light form controls |
| `localStorage` API | Web Storage L2 | Theme preference persistence | Universal support, synchronous read, no dependencies |
| `MutationObserver` API | DOM L4 | Detect `data-theme` attribute changes for graph re-render | 98%+ support, efficient, no polling, works with any attribute mutation |
| `window.matchMedia` | CSSOM View Module | Detect OS color scheme preference | Universal support, standard way to query media features from JS |
| `getComputedStyle` + `getPropertyValue` | CSSOM | Read resolved CSS variable values at runtime | Standard API, returns computed values after cascade resolution |
| Vanilla JS | ES6+ | All toggle/persistence/helper logic | Matches project constraint (no build step, no new deps) |

### Supporting
| Technology | Purpose | When to Use |
|------------|---------|-------------|
| `requestAnimationFrame` | Debounce graph re-render on theme switch | Prevents multiple re-renders if theme changes rapidly |
| CSS `transition` | Optional smooth color transitions on theme switch | Could add in Phase 3 (ENHC-02), not in scope here |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `MutationObserver` for graph re-render | Custom event `dispatchEvent(new Event('themechange'))` | Simpler but requires every theme-setting codepath to dispatch; MutationObserver catches ALL changes including DevTools edits |
| `getComputedStyle` per call | Cache CSS vars in JS object on theme change | Faster but creates a second source of truth; `getComputedStyle` is fast enough for color lookups (sub-ms) |
| Inline `<head>` script for flash prevention | `<meta name="color-scheme">` only | Meta tag alone cannot select from three themes; script is required for three-way choice |

### No Installation Required
This phase adds zero dependencies. All work is pure JS within the existing `<script>` block plus a small inline `<head>` script.

## Architecture Patterns

### Theme System Architecture

```
 [Flash Prevention]         [User Interaction]         [Graph Re-render]
 Inline <head> script       Toggle / Settings          MutationObserver
        |                        |                           |
        v                        v                           v
   Read localStorage  -->  setTheme(theme)  -->  data-theme attr changes
   Set data-theme          Write localStorage       Observer fires
   Set color-scheme        Update toggle icon        Re-render minimap
                           Update color-scheme       Re-render SVG edges
```

### Core Functions

```javascript
// ── Theme System ──

function getThemeColor(name) {
  return getComputedStyle(document.documentElement)
    .getPropertyValue('--' + name).trim();
}

function branchSlug(displayName) {
  // 'Actor / Player' -> 'actor-player'
  // 'Document / Artifact' -> 'document-artifact'
  // 'Financial Concepts and Metrics' -> 'financial-concepts'
  return displayName
    .toLowerCase()
    .replace(/\s*\/\s*/g, '-')      // ' / ' -> '-'
    .replace(/\s+and\s+.*$/, '')     // strip ' and ...' suffix
    .replace(/\s+/g, '-')            // spaces -> hyphens
    .replace(/-+/g, '-');            // collapse multiple hyphens
}

function getBranchColor(displayName) {
  const slug = branchSlug(displayName);
  return getThemeColor('branch-' + slug) || getThemeColor('branch-default');
}

const THEME_CYCLE = ['dark', 'light', 'mixed'];
const THEME_ICONS = { dark: '\u{1F319}', light: '\u2600\uFE0F', mixed: '\u25D1' };
const THEME_LABELS = { dark: 'Dark', light: 'Light', mixed: 'Mixed' };

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  // Set color-scheme for native UI theming
  const scheme = theme === 'light' ? 'light' : 'dark';
  document.documentElement.style.setProperty('color-scheme', scheme);
  localStorage.setItem('theme', theme);
  updateThemeToggle(theme);
  updateThemeSwatches(theme);
}

function cycleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'mixed';
  const idx = THEME_CYCLE.indexOf(current);
  const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
  setTheme(next);
}

function updateThemeToggle(theme) {
  const btn = document.getElementById('themeToggleBtn');
  if (!btn) return;
  const nextIdx = (THEME_CYCLE.indexOf(theme) + 1) % THEME_CYCLE.length;
  const nextTheme = THEME_CYCLE[nextIdx];
  btn.textContent = THEME_ICONS[theme];
  btn.title = `Theme: ${THEME_LABELS[theme]} (click for ${THEME_LABELS[nextTheme]})`;
}
```

### Flash Prevention Script (inline in `<head>`)

This script goes between `</style>` (line 2855) and `</head>` (line 2856). It must be synchronous and minimal.

```html
<script>
(function() {
  var t = localStorage.getItem('theme');
  if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.style.setProperty('color-scheme', t === 'light' ? 'light' : 'dark');
})();
</script>
```

**Critical details:**
- Uses `var` not `const`/`let` for maximum compatibility
- No dependencies on any other script
- Must execute synchronously (no async, no defer)
- Runs before `<body>` is parsed, so no DOM elements exist yet
- Sets both `data-theme` and `color-scheme` to prevent any flash
- Falls back to `light` (not `mixed`) for new users with light OS preference -- `mixed` is only set by explicit user choice

### Header Toggle Button Placement

The toggle button goes into `.header-right` (line 2914) as the first child, before the "Show Uncertain" toggle. This positions it prominently but maintains the existing button flow.

```html
<div class="header-right">
  <button class="header-btn" id="themeToggleBtn" onclick="cycleTheme()" title="Theme: Mixed (click for Dark)">&#9681;</button>
  <!-- existing buttons follow -->
  <label class="toggle">...</label>
  ...
</div>
```

### Settings Modal Appearance Section

Added as the FIRST section in the settings modal body, before "FOLIO Ontology":

```html
<div class="settings-section-label">Appearance</div>
<div class="theme-swatches" style="display:flex;gap:10px;margin-bottom:16px">
  <button class="theme-swatch" onclick="setTheme('dark')" data-theme-value="dark" title="Dark theme">
    <div class="swatch-preview swatch-dark">
      <span class="swatch-text">Aa</span>
    </div>
    <span class="swatch-label">Dark</span>
  </button>
  <button class="theme-swatch" onclick="setTheme('light')" data-theme-value="light" title="Light theme">
    <div class="swatch-preview swatch-light">
      <span class="swatch-text">Aa</span>
    </div>
    <span class="swatch-label">Light</span>
  </button>
  <button class="theme-swatch" onclick="setTheme('mixed')" data-theme-value="mixed" title="Mixed theme">
    <div class="swatch-preview swatch-mixed">
      <span class="swatch-text-left">Aa</span>
      <span class="swatch-text-right">Aa</span>
    </div>
    <span class="swatch-label">Mixed</span>
  </button>
</div>
```

### MutationObserver for Graph Re-render

Placed in the main `<script>` block, after the graph functions are defined:

```javascript
// Theme change observer -- re-render graph when theme changes
const _themeObserver = new MutationObserver((mutations) => {
  for (const m of mutations) {
    if (m.attributeName === 'data-theme') {
      // Re-render minimap (canvas) with new theme colors
      renderMinimap();
      // SVG edges use hardcoded stroke colors -- re-render full graph
      if (_graphData) {
        layoutAndRender();
      }
    }
  }
});
_themeObserver.observe(document.documentElement, {
  attributes: true,
  attributeFilter: ['data-theme']
});
```

### Branch Name to CSS Variable Slug Mapping

The BRANCH_COLORS object keys map to CSS variable names as follows:

| Display Name (JS) | CSS Variable | Slug |
|--------------------|-------------|------|
| `Actor / Player` | `--branch-actor-player` | `actor-player` |
| `Area of Law` | `--branch-area-of-law` | `area-of-law` |
| `Asset Type` | `--branch-asset-type` | `asset-type` |
| `Communication Modality` | `--branch-communication-modality` | `communication-modality` |
| `Currency` | `--branch-currency` | `currency` |
| `Data Format` | `--branch-data-format` | `data-format` |
| `Document / Artifact` | `--branch-document-artifact` | `document-artifact` |
| `Document Metadata` | `--branch-document-metadata` | `document-metadata` |
| `Engagement Terms` | `--branch-engagement-terms` | `engagement-terms` |
| `Event` | `--branch-event` | `event` |
| `Financial Concepts and Metrics` | `--branch-financial-concepts` | `financial-concepts` |
| `FOLIO Type` | `--branch-folio-type` | `folio-type` |
| `Forums and Venues` | `--branch-forums-venues` | `forums-venues` |
| `Governmental Body` | `--branch-governmental-body` | `governmental-body` |
| `Industry` | `--branch-industry` | `industry` |
| `Language` | `--branch-language` | `language` |
| `Legal Authorities` | `--branch-legal-authorities` | `legal-authorities` |
| `Legal Entity` | `--branch-legal-entity` | `legal-entity` |
| `Legal Use Cases` | `--branch-legal-use-cases` | `legal-use-cases` |
| `Location` | `--branch-location` | `location` |
| `Matter Narrative` | `--branch-matter-narrative` | `matter-narrative` |
| `Matter Narrative Format` | `--branch-matter-narrative-format` | `matter-narrative-format` |
| `Objectives` | `--branch-objectives` | `objectives` |
| `Service` | `--branch-service` | `service` |
| `Standards Compatibility` | `--branch-standards-compatibility` | `standards-compatibility` |
| `Status` | `--branch-status` | `status` |
| `System Identifiers` | `--branch-system-identifiers` | `system-identifiers` |

The `branchSlug()` function must handle these edge cases:
- Slashes with spaces: `'Actor / Player'` -> `'actor-player'`
- `'and'` conjunctions: `'Financial Concepts and Metrics'` -> `'financial-concepts'` (the CSS var is `--branch-financial-concepts`, not `--branch-financial-concepts-and-metrics`)
- `'Forums and Venues'` -> `'forums-venues'` (same pattern)

### JS Hex Color to Semantic Token Mapping

This is the complete mapping of hardcoded JS hex values to their CSS variable replacements:

| Hex Value | Count | Semantic Token | Usage Context |
|-----------|-------|---------------|---------------|
| `#6b6b80` | 25 | `var(--text-dim)` | Fallback gray text, loading states, secondary labels |
| `#3b64e0` | 11 | `var(--accent)` | Links, concept highlights, edge strokes, outlines |
| `#009688` | 9 | `var(--individual-citation)` | Citation/individual highlights, teal badges, outlines |
| `#888` | 9 | `var(--text-dim)` | Tooltip secondary text, normalized form labels |
| `#991b1b` | 6 | `var(--conf-low)` or `var(--red)` | Error states, low confidence text |
| `#e67e22` | 4 | `var(--individual-entity)` | Entity type indicator (orange) |
| `#1a1a2e` | 4 | `var(--text)` | Dark text in detail panels, lineage stage names |
| `#dcfce7` | 4 | `var(--conf-high-bg)` | High confidence background |
| `#fef3c7` | 4 | `var(--conf-mid-bg)` | Medium confidence background |
| `#fee2e2` | 4 | `var(--conf-low-bg)` | Low confidence background |
| `#166534` | 4 | `var(--conf-high)` | High confidence text |
| `#92400e` | 4 | `var(--conf-mid)` | Medium confidence text |
| `#d0d0da` | 4 | `var(--border)` | Triple item borders, filter button borders |
| `#a0a0b0` | 3 | `var(--text-dim)` | Lighter dim text variant |
| `#9C27B0` | 3 | `var(--property-underline)` | Property badges, purple highlights |
| `#8888a0` | 3 | `var(--text-dim)` | Grouped item counts, alt labels |
| `#f87171` | 2 | `var(--red)` | Danger/clear-all button color |
| `#f6f6fa` | 2 | `var(--surface)` | Tooltip link backgrounds (light context) |
| `#f0f0f4` | 2 | `var(--surface2)` | Lineage confidence badges |
| `#7c3aed` | 1 | `var(--purple)` | seeAlso edge stroke color |
| `#ff9800` | 1 | `var(--orange)` | Passive voice badge background |
| `#dc2626` | 1 | `var(--red)` | Deprecated badge |
| `#f8f8fa` | 1 | `var(--surface)` | Graph node non-focus fill |
| `#f5f6f8` | 1 | `var(--surface)` | Graph node fill |
| `#eeeef6` | 1 | `var(--surface2)` | Tooltip link hover |
| `#e0e0e8` | 1 | `var(--border)` | Tooltip link border |
| `#d0d2da` | 1 | `var(--border)` | Graph node stroke |
| `#c0c0d0` | 1 | `var(--text-dim)` | Current node accent |
| `#b91c1c` | 1 | Part of BRANCH_COLORS | Event branch (to be eliminated) |
| `#b03020` | 1 | Part of BRANCH_COLORS | Objectives branch (to be eliminated) |
| `#9e6b0a` | 1 | `var(--orange)` | Triple predicate color |
| `#1a7a7a` | 1 | `var(--cyan)` | Triple subject color |
| `#6b3fa0` | 1 | `var(--purple)` | Triple object color |
| `#666` | 2 | `var(--text-dim)` | Conditional text fallback |
| `#fff` | 2 | `var(--white)` | White text on colored badges |
| `#444` | 1 | `var(--text)` | Definition text in tooltips |
| `#aaa` | 1 | `var(--text-dim)` | IRI display text |
| `#555` | 1 | `var(--text-dim)` | Confidence percentage text |
| `rgba(59,100,224,0.4)` | 1 | `getThemeColor('accent')` with alpha | Canvas minimap node fill |
| `rgba(228,230,240,0.5)` | 1 | `getThemeColor('text')` with alpha | Canvas minimap viewport stroke |
| `rgba(232,165,76,0.15)` | 1 | `color-mix()` in CSS or `var()` | Individual layer toggle bg |
| `rgba(176,126,232,0.15)` | 1 | `color-mix()` in CSS or `var()` | Property layer toggle bg |
| `rgba(156,39,176,0.12)` | 1 | `var(--property-underline)` with tint | Property tooltip badge bg |

### Two Migration Strategies by Context

**Strategy A: Template literal inline styles** -- Replace hex with `var(--token)` directly in the template string. CSS variables resolve correctly in inline `style` attributes.

```javascript
// Before
html += `<div style="color:#6b6b80">text</div>`;
// After
html += `<div style="color:var(--text-dim)">text</div>`;
```

**Strategy B: Canvas/computed values** -- Use `getThemeColor()` because canvas `ctx.fillStyle` cannot accept CSS `var()` syntax.

```javascript
// Before
ctx.fillStyle = 'rgba(59,100,224,0.4)';
// After
const accentColor = getThemeColor('accent');
ctx.fillStyle = accentColor ? `${accentColor}66` : 'rgba(59,100,224,0.4)';
// Note: appending hex alpha '66' = 40% opacity
```

**Strategy C: Branch color lookups** -- Replace `BRANCH_COLORS[name] || fallback` with `getBranchColor(name)`.

```javascript
// Before
const branchColor = BRANCH_COLORS[branch] || '#6b6b80';
// After
const branchColor = getBranchColor(branch);
```

### Anti-Patterns to Avoid

- **Caching getComputedStyle results across theme changes:** The whole point of `getThemeColor()` is that it reads LIVE values. Never cache the result in a module-level variable. Call it fresh each time you need a color value for canvas/SVG.
- **Setting `color-scheme` only in CSS:** The flash-prevention script runs before CSS is fully parsed on some browsers. Set `color-scheme` in both the inline `<head>` script AND the CSS selectors.
- **Using `getThemeColor()` in template literals for inline styles:** Unnecessary overhead. Template literal HTML that sets `style="color:..."` can use `var(--token)` directly. Reserve `getThemeColor()` for canvas 2D context and computed values only.
- **Forgetting the `detail.branch_color` fallback chain:** Many lines currently do `detail.branch_color || BRANCH_COLORS[detail.branch] || '#6b6b80'`. After migration, `detail.branch_color` from the API should be IGNORED (it is a static hex from the backend, not theme-aware). The pattern becomes `getBranchColor(detail.branch)`.
- **Leaving `onmouseover`/`onmouseout` inline style handlers with hex colors:** Line ~3751 (tooltip link hover) has `onmouseover="this.style.background='#eeeef6'"`. These must be converted to `var()` references or moved to CSS `:hover` rules.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Flash of wrong theme | Complex CSS-only `prefers-color-scheme` media queries | Inline `<head>` script reading localStorage | Three themes cannot be expressed with media queries alone; script is the standard pattern |
| Theme change detection for graph | Custom event system or polling | `MutationObserver` on `data-theme` attribute | Standard API, catches all mutation sources (JS, DevTools, extensions), no event dispatch needed |
| Branch display name to CSS var slug | Manual mapping object (another 27-entry dict) | `branchSlug()` string transform function | Algorithmic conversion eliminates maintenance of a second mapping table |
| Native scrollbar/form theming | Custom scrollbar CSS per theme | `color-scheme` CSS property | One property handles scrollbars, checkboxes, radio buttons, select menus, text inputs natively |

**Key insight:** The hardest part of this phase is not the toggle UI or persistence (those are straightforward) -- it is the mechanical refactoring of ~80 lines of JS template literals containing hardcoded hex colors. This is tedious but each replacement follows one of three simple patterns (A/B/C above). The risk is missing a replacement, not getting the pattern wrong.

## Common Pitfalls

### Pitfall 1: Flash Prevention Script Breaks on First Visit
**What goes wrong:** New user has no localStorage entry. Script returns `null` from `getItem('theme')`. If the fallback logic is wrong, `data-theme` gets set to `null` or empty string, which matches no CSS selector, and the page renders with `:root` fallback values only.
**Why it happens:** Not handling the `null` case from `localStorage.getItem`.
**How to avoid:** Explicit fallback chain: `localStorage.getItem('theme')` -> `matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'`. Never set an empty or null `data-theme`.
**Warning signs:** New incognito window shows broken/missing colors.

### Pitfall 2: Graph SVG Edges Use Hardcoded Stroke Colors
**What goes wrong:** Theme changes but graph edge colors (the lines between nodes) stay the old color because they are set via `path.setAttribute('stroke', '#3b64e0')` in `renderGraph()`.
**Why it happens:** SVG `stroke` attributes set via JS are not CSS variables -- they are literal attribute values that don't respond to theme changes.
**How to avoid:** Either (a) set stroke colors using CSS classes that reference CSS variables, or (b) re-render the entire graph on theme change. Since the graph already re-renders on layout changes, option (b) via `layoutAndRender()` in the MutationObserver callback is simplest. But also convert the hardcoded stroke colors to use `getThemeColor()` so the re-render picks up the correct theme colors.
**Warning signs:** After switching theme with graph open, edge lines remain the old color.

### Pitfall 3: `branchSlug()` Edge Cases
**What goes wrong:** Display name `'Financial Concepts and Metrics'` converts to `'financial-concepts-and-metrics'` but the CSS variable is `--branch-financial-concepts`. Lookup returns empty string.
**Why it happens:** The CSS variable names from Phase 1 used shortened kebab-case names that don't include "and ..." suffixes.
**How to avoid:** The `branchSlug()` function must strip ` and ...` suffixes. Verify the function against ALL 27 branch names in the mapping table above.
**Warning signs:** Some branch colors show as the fallback gray after migration.

### Pitfall 4: `color-scheme` on Mixed Theme
**What goes wrong:** Mixed theme sets `color-scheme: light` which makes scrollbars in the dark left panel render with light colors (white track, dark thumb) -- visually jarring.
**Why it happens:** `color-scheme` is inherited and applies to the whole page. Mixed theme has both dark and light panels.
**How to avoid:** Set `color-scheme: dark` on the root for mixed theme (the majority of chrome is dark). The light panels' form controls will still render dark-schemed, but scrollbars in the right panel can be overridden with `color-scheme: light` specifically on `.panel-right` and `.panel-detail` in the mixed theme CSS. Alternatively, just set `color-scheme: dark` for mixed theme globally -- the scrollbar-color CSS properties from Phase 1 already handle per-panel scrollbar styling.
**Warning signs:** Scrollbar colors look wrong in mixed mode panels.

### Pitfall 5: Double-Rendering on Init
**What goes wrong:** The inline `<head>` script sets `data-theme`, then the `init()` function also calls `setTheme()`, causing a redundant re-render and a brief attribute mutation that triggers the MutationObserver.
**Why it happens:** Two codepaths setting the same attribute.
**How to avoid:** The `init()` function should read the current `data-theme` attribute (already set by the `<head>` script) and only call `updateThemeToggle()` and `updateThemeSwatches()` -- NOT `setTheme()` which would re-set the attribute. Only call `setTheme()` on user interaction.
**Warning signs:** MutationObserver fires on page load even though no theme change occurred.

### Pitfall 6: Confidence Tier Colors in Inline Styles
**What goes wrong:** The confidence tier colors (`#dcfce7`, `#166534`, etc.) appear in ternary expressions that compute background/foreground colors inline. Replacing with `var()` in a ternary is awkward.
**Why it happens:** Pattern like `confPct >= 80 ? '#dcfce7' : confPct >= 50 ? '#fef3c7' : '#fee2e2'` doesn't easily convert to CSS variables.
**How to avoid:** Replace the ternary with the corresponding CSS variable: `confPct >= 80 ? 'var(--conf-high-bg)' : confPct >= 50 ? 'var(--conf-mid-bg)' : 'var(--conf-low-bg)'`. This is a direct 1:1 replacement -- each hex value maps to exactly one semantic token.
**Warning signs:** Confidence badges show wrong colors or no color in non-dark themes.

### Pitfall 7: Tooltip Link onmouseover/onmouseout With Hex
**What goes wrong:** The tooltip link component (line ~3751) uses `onmouseover="this.style.background='#eeeef6'"` and `onmouseout="this.style.background='#f6f6fa'"`. These are inline event handlers with hardcoded colors.
**Why it happens:** These were written before the CSS variable system existed.
**How to avoid:** Convert to `var()` references: `onmouseover="this.style.background='var(--surface2)'"` and `onmouseout="this.style.background='var(--surface)'"`. CSS variables resolve correctly in inline style assignments.
**Warning signs:** Tooltip links have wrong hover color in light/mixed themes.

## Code Examples

### Example 1: Complete setTheme() and cycleTheme()
```javascript
// Source: Synthesized from MDN localStorage, MutationObserver, matchMedia docs
const THEME_CYCLE = ['dark', 'light', 'mixed'];
const THEME_ICONS = { dark: '\u{1F319}', light: '\u2600\uFE0F', mixed: '\u25D1' };
const THEME_LABELS = { dark: 'Dark', light: 'Light', mixed: 'Mixed' };

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.style.setProperty('color-scheme',
    theme === 'light' ? 'light' : 'dark');
  localStorage.setItem('theme', theme);
  updateThemeToggle(theme);
  updateThemeSwatches(theme);
}

function cycleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'mixed';
  const idx = THEME_CYCLE.indexOf(current);
  setTheme(THEME_CYCLE[(idx + 1) % THEME_CYCLE.length]);
}

function updateThemeToggle(theme) {
  const btn = document.getElementById('themeToggleBtn');
  if (!btn) return;
  const nextIdx = (THEME_CYCLE.indexOf(theme) + 1) % THEME_CYCLE.length;
  btn.textContent = THEME_ICONS[theme];
  btn.title = `Theme: ${THEME_LABELS[theme]} (click for ${THEME_LABELS[THEME_CYCLE[nextIdx]]})`;
}

function updateThemeSwatches(theme) {
  document.querySelectorAll('.theme-swatch').forEach(s => {
    s.classList.toggle('active', s.dataset.themeValue === theme);
  });
}
```

### Example 2: getThemeColor() and getBranchColor()
```javascript
// Source: MDN getComputedStyle + getPropertyValue docs
function getThemeColor(name) {
  return getComputedStyle(document.documentElement)
    .getPropertyValue('--' + name).trim();
}

function branchSlug(displayName) {
  return displayName
    .toLowerCase()
    .replace(/\s*\/\s*/g, '-')
    .replace(/\s+and\s+.*$/, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function getBranchColor(displayName) {
  if (!displayName) return getThemeColor('branch-default') || '#8b8fa3';
  return getThemeColor('branch-' + branchSlug(displayName))
    || getThemeColor('branch-default')
    || '#8b8fa3';
}
```

### Example 3: Flash Prevention Inline Script
```html
<!-- Between </style> and </head> -->
<script>
(function() {
  var t = localStorage.getItem('theme');
  if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.style.setProperty('color-scheme', t === 'light' ? 'light' : 'dark');
})();
</script>
```

### Example 4: Canvas Minimap with Theme Colors
```javascript
// Before (hardcoded)
ctx.fillStyle = 'rgba(59,100,224,0.4)';
ctx.strokeStyle = 'rgba(228,230,240,0.5)';

// After (theme-aware)
function renderMinimap() {
  // ... existing setup code ...

  // Draw nodes with theme-aware color
  const accentHex = getThemeColor('accent') || '#6c8cff';
  positions.forEach(p => {
    ctx.fillStyle = hexToRgba(accentHex, 0.4);
    ctx.fillRect(/* ... */);
  });

  // Draw viewport rect with theme-aware color
  const textHex = getThemeColor('text') || '#e4e6f0';
  ctx.strokeStyle = hexToRgba(textHex, 0.5);
  // ... rest of viewport drawing ...
}

// Simple hex-to-rgba utility for canvas
function hexToRgba(hex, alpha) {
  hex = hex.replace('#', '');
  if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
  const r = parseInt(hex.substring(0,2), 16);
  const g = parseInt(hex.substring(2,4), 16);
  const b = parseInt(hex.substring(4,6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
```

### Example 5: MutationObserver for Graph Re-render
```javascript
// Source: MDN MutationObserver docs
const _themeObserver = new MutationObserver((mutations) => {
  for (const m of mutations) {
    if (m.attributeName === 'data-theme') {
      renderMinimap();
      if (_graphData && document.getElementById('graphModal').classList.contains('visible')) {
        layoutAndRender();
      }
    }
  }
});
_themeObserver.observe(document.documentElement, {
  attributes: true,
  attributeFilter: ['data-theme']
});
```

### Example 6: Migrating Confidence Tier Ternaries
```javascript
// Before (4 occurrences, lines ~4486, ~4601, ~4772, ~5072)
const confBg = confPct != null ? (confPct >= 80 ? '#dcfce7' : confPct >= 50 ? '#fef3c7' : '#fee2e2') : '';
const confFg = confPct != null ? (confPct >= 80 ? '#166534' : confPct >= 50 ? '#92400e' : '#991b1b') : '';

// After
const confBg = confPct != null ? (confPct >= 80 ? 'var(--conf-high-bg)' : confPct >= 50 ? 'var(--conf-mid-bg)' : 'var(--conf-low-bg)') : '';
const confFg = confPct != null ? (confPct >= 80 ? 'var(--conf-high)' : confPct >= 50 ? 'var(--conf-mid)' : 'var(--conf-low)') : '';
```

### Example 7: Migrating Graph Edge Stroke Colors
```javascript
// Before (line 8719)
path.setAttribute('stroke', isSeeAlso ? '#7c3aed' : '#3b64e0');

// After
path.setAttribute('stroke', isSeeAlso ? getThemeColor('purple') : getThemeColor('accent'));
```

### Example 8: CSS color-scheme Per Theme
```css
/* Add to existing [data-theme] selectors in CSS */
[data-theme="dark"] {
  color-scheme: dark;
  /* ... existing tokens ... */
}

[data-theme="light"] {
  color-scheme: light;
  /* ... existing tokens ... */
}

[data-theme="mixed"] {
  color-scheme: dark;
  /* ... existing tokens ... */
}

/* Optional: override for light panels in mixed mode */
[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail {
  color-scheme: light;
  /* ... existing tokens ... */
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `<body class="theme-dark">` toggle | `data-theme` attribute on `<html>` | 2022-2023 | Cleaner specificity, semantic, industry standard |
| FOUC (flash of unstyled content) acceptance | Inline `<head>` script for instant theme | 2020+ | Zero-flash theme loading, essential for dark mode |
| Custom scrollbar CSS per theme | `color-scheme` CSS property | 2020 (Chrome 81+) | Browser handles native UI theming automatically |
| Polling for theme changes | `MutationObserver` | 2015+ (mature) | Event-driven, zero overhead, catches all mutation sources |
| Hardcoded color objects in JS | `getComputedStyle().getPropertyValue()` | Always available | Single source of truth in CSS, no duplication |

**Deprecated/outdated:**
- **`window.matchMedia` listeners for live theme detection**: Only needed if supporting OS-level live switching. For this app with explicit three-way toggle, the listener is only needed at initialization time in the flash-prevention script.
- **`prefers-color-scheme` as the sole theme mechanism**: Cannot express three themes. Used only as initial default for new users.

## Open Questions

1. **Mixed Theme Default for New Users with Light OS**
   - What we know: Flash-prevention falls back to `prefers-color-scheme`. Dark OS -> dark theme, light OS -> light theme. Mixed is never the automatic default.
   - What's unclear: Should mixed ever be the default? It was the original UI mode.
   - Recommendation: Do NOT default to mixed automatically. Mixed is a unique layout mode that users should explicitly choose. New users get dark or light based on OS preference. Existing users who never set a preference will see their first load use OS detection instead of mixed.

2. **`color-scheme` Value for Mixed Mode Panels**
   - What we know: `color-scheme` inherits. Setting `dark` on root means all form controls render dark.
   - What's unclear: Should the light panels in mixed mode get `color-scheme: light` override?
   - Recommendation: Set `color-scheme: dark` on mixed root. Add `color-scheme: light` to the `[data-theme="mixed"] .panel-right, [data-theme="mixed"] .panel-detail` selector. This gives light scrollbars and form controls in the right panels while keeping dark chrome elsewhere.

3. **Backend `branch_color` Field**
   - What we know: The API response includes `branch_color` as a hex string. Many JS lines use `detail.branch_color || BRANCH_COLORS[detail.branch] || '#6b6b80'`.
   - What's unclear: Should the backend `branch_color` still be respected at all?
   - Recommendation: Ignore `detail.branch_color` entirely. The CSS variable system is the single source of truth. Replace the fallback chain with `getBranchColor(detail.branch)`. The backend field becomes unused by the frontend but remains in the API for backward compatibility with other consumers.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Visual regression via Chrome DevTools MCP screenshots + structural grep + backend pytest |
| Config file | None (no automated CSS/JS test framework for frontend) |
| Quick run command | `grep -cP '(?<!&)#[0-9a-fA-F]{3,8}\b' frontend/index.html` (count should decrease by ~100+) |
| Full suite command | `cd backend && .venv/bin/python -m pytest tests/ -v` (backend unaffected; confirms no regressions) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| THSW-01 | Header toggle cycles themes | visual | Chrome DevTools: click toggle, screenshot each state | Manual |
| THSW-02 | Settings modal swatches select themes | visual | Chrome DevTools: open settings, click each swatch, screenshot | Manual |
| THSW-03 | Theme persists across reload | visual | Chrome DevTools: set theme, reload page, screenshot | Manual |
| THSW-04 | No flash on reload | visual | Chrome DevTools: hard reload with network throttling, screenshot first paint | Manual |
| THSW-05 | OS preference detection | visual | Chrome DevTools: emulate prefers-color-scheme, clear localStorage, reload | Manual |
| THSW-06 | color-scheme set per theme | visual | Inspect scrollbars/form controls in each theme | Manual |
| JSIT-01 | Zero hardcoded JS colors | structural | `awk 'NR>2855' frontend/index.html \| grep -cP '(?<!&)#[0-9a-fA-F]{6}\b'` -- should be ~0 (only palette primitives in `:root`) | No automated test |
| JSIT-02 | Graph re-renders on theme change | visual | Chrome DevTools: open graph modal, switch theme, screenshot canvas | Manual |
| JSIT-03 | BRANCH_COLORS eliminated | structural | `grep -c 'BRANCH_COLORS' frontend/index.html` -- should be 0 | No automated test |

### Sampling Rate
- **Per task commit:** `grep -cP '(?<!&)#[0-9a-fA-F]{6}\b' frontend/index.html` + `grep -c 'BRANCH_COLORS' frontend/index.html`
- **Per wave merge:** Chrome DevTools MCP screenshots of all three themes + graph modal
- **Phase gate:** Zero BRANCH_COLORS references, zero non-primitive hex values in JS, visual verification of all three themes + graph re-render

### Wave 0 Gaps
- None -- this phase modifies existing code patterns. No new test infrastructure needed. Backend test suite runs as a regression check.

## Sources

### Primary (HIGH confidence)
- `frontend/index.html` lines 1-10093 -- direct audit of all hex values, BRANCH_COLORS, canvas code, settings modal, header structure
- [MDN: MutationObserver](https://developer.mozilla.org/en-US/docs/Web/API/MutationObserver) -- API documentation for attribute observation
- [MDN: MutationObserver.observe()](https://developer.mozilla.org/en-US/docs/Web/API/MutationObserver/observe) -- `attributeFilter` option documentation
- [MDN: color-scheme CSS property](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/color-scheme) -- native UI theming per mode
- [MDN: Window.getComputedStyle()](https://developer.mozilla.org/en-US/docs/Web/API/Window/getComputedStyle) -- reading CSS custom property values
- [MDN: CSSStyleDeclaration.getPropertyValue()](https://developer.mozilla.org/en-US/docs/Web/API/CSSStyleDeclaration/getPropertyValue) -- accessing CSS variable values
- [MDN: Using CSS custom properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Cascading_variables/Using_custom_properties) -- var() in inline styles

### Secondary (MEDIUM confidence)
- [Piccalilli: Get a CSS Custom Property value with JavaScript](https://piccalil.li/blog/get-css-custom-property-value-with-javascript/) -- getComputedStyle pattern verification
- [David Walsh: CSS Variables JavaScript](https://davidwalsh.name/css-variables-javascript) -- get/set CSS variable patterns
- [Aleksandr Hovhannisyan: The Perfect Theme Switch](https://www.aleksandrhovhannisyan.com/blog/the-perfect-theme-switch/) -- flash prevention pattern
- [swyx: Avoiding Flash of Unthemed Code](https://www.swyx.io/avoid-fotc) -- inline script pattern
- [Rebecca M DePrey: Embracing Native Dark Mode with color-scheme](https://rebeccamdeprey.com/blog/embracing-native-dark-mode-with-the-css-color-scheme-property) -- color-scheme usage patterns
- [mamutlove: Theming with CSS in 2025](https://mamutlove.com/en/blog/theming-with-css-in-2025/) -- current state of CSS theming

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- localStorage, MutationObserver, getComputedStyle, color-scheme are all mature, well-documented web platform APIs
- Architecture: HIGH -- Flash prevention inline script is the established pattern used by every major theme system (Next.js, MUI, etc.); MutationObserver for attribute watching is standard
- Pitfalls: HIGH -- Identified through direct code audit of the actual codebase (all 134 hex values catalogued, all 13 BRANCH_COLORS usage sites located, all canvas operations identified)
- JS Migration mapping: HIGH -- Every hex value mapped to a specific semantic token with line-level context; mapping verified against Phase 1 CSS variable definitions

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (stable domain; Web APIs are frozen standards)
