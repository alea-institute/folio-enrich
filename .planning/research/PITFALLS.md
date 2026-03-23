# Domain Pitfalls: CSS Theme System

**Domain:** Multi-mode CSS theming (Dark/Light/Mixed) for a large single-file vanilla JS frontend
**Researched:** 2026-03-22
**Confidence:** HIGH -- based on direct codebase analysis of `frontend/index.html` (9,668 lines) and verified domain research

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: JS-Generated Inline Styles Immune to CSS Variable Switching

**What goes wrong:**
The codebase has ~124 instances of hardcoded hex colors injected via JavaScript template literals into inline `style` attributes (e.g., `style="color:#6b6b80"`, `style="background:#f6f6fa"`, `style="color:${branchColor}"` where `branchColor` comes from the JS `BRANCH_COLORS` object at line 3120). Inline styles have the highest specificity short of `!important`, so changing CSS variables at `:root` or `[data-theme]` has zero effect on them. After switching to Dark mode, tooltip text stays `#1a1a2e` (dark text on dark background = invisible), property cards keep `background: #f0f0f5` (light background on dark = jarring), and lineage error text uses `#991b1b` (dark red on dark = unreadable).

**Why it happens:**
The current design assumes all JS-rendered content lives inside the always-light right/detail panels. That assumption breaks the moment the right panels can also be dark (in Dark mode). The JS code never reads CSS variables -- it uses hardcoded hex values because the panels were always light.

Specific high-risk areas:
- **Tooltip builders** (lines 5273-5389): 15+ inline color assignments for individual/property tooltips
- **Ancestry trees** (lines 6891, 6958, 6992, 7076, 7325): inline `style` with `background:${branchColor}15` (hex + opacity suffix hack)
- **Pill renderers** (lines 5620, 5778, 5857): `style="color:${aColor};background:${aColor}18"`
- **Lineage trail** (lines 7823-7840): hardcoded `#1a1a2e`, `#3b64e0`, `#6b6b80`, `#991b1b`
- **See Also links** (line 3326): `background:#f6f6fa;border:1px solid #e0e0e8;color:#3a3a5c`
- **Summary sections** (lines 2718, 2722, 2726): `color:#6b6b80`

**How to avoid:**
1. Audit every JS template literal that injects `style="...color..."` or `style="...background..."`. Use grep pattern: `style=.*#[0-9a-fA-F]` and `color:\$\{|background:\$\{`.
2. Replace hardcoded hex values with CSS classes that reference variables, or create a `themeColor(name)` helper: `getComputedStyle(document.documentElement).getPropertyValue('--name').trim()`.
3. For `BRANCH_COLORS` usage (15+ call sites), add a `getBranchColor(branchName)` wrapper that reads from CSS variables so colors respond to theme changes.

**Warning signs:**
- Any `style="...#..."` in a JS string literal
- Any reference to `BRANCH_COLORS[...]` used as a direct `color:` value without variable indirection
- Tooltip content that looks correct in Mixed mode but is unreadable in Dark mode

**Phase to address:**
Phase 1 (Variable Extraction) -- every hardcoded color must be cataloged and converted before theme switching can work.

---

### Pitfall 2: FOUC / FART on Page Load

**What goes wrong:**
The page flashes the wrong theme for 50-200ms on load. If the user chose Dark mode but the CSS defaults to Mixed (the current default), the page renders Mixed, then JavaScript reads `localStorage`, then applies `data-theme="dark"` -- causing a visible flash of light panels snapping to dark. This is known as FART (Flash of inAccurate coloR Theme).

**Why it happens:**
CSS is parsed before JavaScript executes. If the theme preference is only in `localStorage` (client-side only), there is no way for CSS alone to know the preference. The page renders with whatever `:root` declares, then JS corrects it. On slow devices or with this large file (~9,700 lines of HTML/CSS/JS), the gap is perceptible.

As the CSS-Tricks article on FART notes: "If access to that data means running JavaScript, e.g. `localStorage.getItem('color-mode-preference')`, then you're in FART territory, because your JavaScript is very likely running after a page's first render."

**How to avoid:**
Place a synchronous, blocking `<script>` in the `<head>`, immediately before the `<style>` block:
```html
<script>
  (function() {
    var t = localStorage.getItem('folio-enrich-theme');
    if (!t) {
      t = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light'
        : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark'
        : 'mixed';
    }
    document.documentElement.setAttribute('data-theme', t);
  })();
</script>
```
This runs synchronously before first paint. The `data-theme` attribute is set before the browser processes CSS, so the correct theme variables apply on first render. The script must be tiny (no DOM queries beyond `documentElement`, no network calls) and must NOT be `defer` or `async`.

**Warning signs:**
- Flash of white/light when loading a page saved as Dark mode
- Flash of dark when loading a page saved as Light mode
- The `<script>` tag is placed after `<body>` or uses `defer`/`async`
- The script references `document.body` (not yet available in `<head>`)

**Phase to address:**
Phase 3 (Theme Toggle + Persistence) -- must be implemented simultaneously with localStorage persistence, not as a later fix.

---

### Pitfall 3: Mixed Mode CSS Specificity War

**What goes wrong:**
The existing codebase overrides CSS variables at the `.panel-right` and `.panel-detail` class level (lines 335-388). In Mixed mode, these overrides create light panels. But when adding `[data-theme="dark"]` and `[data-theme="light"]` selectors, the specificity math becomes treacherous. The current unconditional `.panel-right { --bg: #ffffff; ... }` rules (line 336) always apply regardless of theme. In Dark mode, `.panel-right` still overrides `--bg` to `#ffffff` because it was never scoped to Mixed-only. The right panel refuses to go dark.

If you try `[data-theme="dark"] { --bg: #0f1117 }` to fix it, `.panel-right { --bg: #ffffff }` still wins for elements inside `.panel-right` because CSS custom properties resolve from the nearest ancestor that defines them, and `.panel-right` is closer than `[data-theme]` on `<html>`. Adding `!important` to the theme selector just compounds the existing 70+ `!important` problem.

**Why it happens:**
The current system was never designed for three modes. The light-panel overrides are unconditional -- they always apply to `.panel-right` regardless of theme. Adding theme selectors requires restructuring the cascade so that panel-level overrides only apply in Mixed mode.

**How to avoid:**
Structure the CSS cascade in this exact order:
```css
/* 1. Dark palette (default -- works for [data-theme="dark"] and as fallback) */
:root { --bg: #0f1117; --text: #e4e6f0; ... }

/* 2. Light palette (when explicitly light) */
[data-theme="light"] { --bg: #ffffff; --text: #1a1a2e; ... }

/* 3. Mixed: panels override to light -- ONLY in mixed mode */
[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail { --bg: #ffffff; --text: #1a1a2e; ... }
```
The current unconditional `.panel-right { --bg: #ffffff }` rules at lines 336-354 MUST be wrapped inside `[data-theme="mixed"]`. This is the single most important structural change in the entire migration.

**Warning signs:**
- Right panel stays light even in Dark mode
- Left panel goes light even in Mixed mode
- `!important` creep to force overrides
- DevTools "Computed" tab shows the wrong variable winning

**Phase to address:**
Phase 2 (Theme Variable Architecture) -- the cascade structure must be designed correctly before any theme switching logic is built.

---

### Pitfall 4: 26 Branch Colors Fail WCAG AA on Wrong Backgrounds

**What goes wrong:**
The JS `BRANCH_COLORS` object (lines 3120-3148) contains 26 hex values chosen for legibility as text on white/light backgrounds (e.g., `'Area of Law': '#1a5276'`, `'Legal Authorities': '#8b1a1a'`). In Dark mode, these same colors become text on `#0f1117`. Many fail WCAG AA 4.5:1:
- `#1a5276` (Area of Law) on `#0f1117` = ~2.1:1 contrast -- hard failure
- `#6b5600` (Asset Type) on `#0f1117` = ~2.3:1 -- hard failure
- `#4a5568` (Data Format) on `#0f1117` = ~2.8:1 -- hard failure

Meanwhile, the CSS defines brighter branch colors (`--branch-actor: #5ec4d4`, `--branch-area-of-law: #e8a54c`) designed for dark backgrounds, but the JS template literals never reference these CSS variables -- they read from the static `BRANCH_COLORS` object.

**Why it happens:**
Two parallel, disconnected color systems: CSS variables (`--branch-*`) for CSS-styled elements, and the JS `BRANCH_COLORS` object for JS-generated HTML. They use entirely different color values designed for different background contexts.

**How to avoid:**
1. Unify into a single source of truth. Define all 26 branch colors as CSS variables with dark-mode and light-mode variants.
2. Create `getBranchColor(branchName)` that reads from `getComputedStyle` so JS always uses the current theme's branch color.
3. Each theme defines branch colors that pass 4.5:1 on that theme's background. This means different hex values per theme for each of the 26 branches -- 78 total color-on-background pairs to validate.
4. Automate contrast checks for all pairs.

**Warning signs:**
- Branch badges that look washed out or invisible in Dark mode
- `BRANCH_COLORS` object still uses hardcoded hex values after theme system is built
- Any branch color with contrast ratio < 4.5:1 against its theme's `--bg`

**Phase to address:**
Phase 1 (Color Audit) for identification, Phase 2 (Variable Architecture) for defining per-theme branch colors, Phase 4 (WCAG Validation) for verification.

---

### Pitfall 5: Canvas Minimap and SVG Graph Ignore Theme Changes

**What goes wrong:**
The graph minimap (line 8360) uses `ctx.fillStyle = 'rgba(59,100,224,0.4)'` and `ctx.strokeStyle = 'rgba(228,230,240,0.5)'` -- hardcoded RGBA values baked into the canvas rendering function. Canvas does not participate in CSS cascading; it is an imperative pixel buffer. After switching to Light mode, the minimap paints dark-themed colors on a now-light background.

Similarly, the graph has hardcoded CSS:
- `.graph-node.focus { background: #1e2a4a }` (line 697) -- dark-only
- `.graph-node.branch-root { border-color: #e05555 }` (line 698)
- `.graph-minimap { background: rgba(26,29,39,0.85) }` (line 705) -- dark semi-transparent
- `.graph-modal-legend { background: #1a1d27 }` (line 710) -- hardcoded dark
- `.dag-edge { stroke: #b0b0c0 }` (line 606) -- hardcoded gray
- Graph legend items (lines 3003-3007): inline `style="background:#3b64e0"`, `style="background:#1a1d27"`

**Why it happens:**
Canvas is a bitmap -- CSS variables do not flow into it. The canvas `_updateGraphMinimap()` function (lines 8338-8377) draws directly with hardcoded RGBA. The graph was built as a dark-only component.

**How to avoid:**
1. For canvas: Read theme colors from CSS variables at render time: `getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()`. Cache the result. Call the render function on theme change.
2. For SVG/graph CSS: Replace hardcoded colors with CSS variables.
3. For graph legend (lines 3003-3007): Replace inline `style` attributes with CSS classes.
4. Add a theme change listener that triggers `_updateGraphMinimap()` and graph node re-render.

**Warning signs:**
- Minimap looks "burned in" with wrong colors after theme switch
- Graph node `.focus` has dark background in Light mode
- Graph legend colors are wrong in any non-dark theme

**Phase to address:**
Phase 2 (Variable Architecture) for SVG/graph CSS conversion, Phase 3 (Theme Toggle) for canvas re-render hook.

---

### Pitfall 6: Modals Hardcoded to Light Theme

**What goes wrong:**
The modal system (lines 2015-2069) is entirely hardcoded to a light appearance:
- `.modal { background: #ffffff; color: #1a1a2e; border: 1px solid #d0d0da }` (lines 2016-2018)
- `.modal .form-group label { color: #4a4a60 }` (line 2038)
- `.modal select, input { background: #f5f5f8; color: #1a1a2e; border: 1px solid #c0c0cc }` (lines 2051-2053)
- `.modal button.secondary { border-color: #c0c0cc; color: #4a4a60 }` (lines 2063-2064)
- `.modal::-webkit-scrollbar-thumb { background: #c0c0cc }` (line 2034)

In Dark mode, a modal pops up as a jarring white rectangle on an otherwise dark UI. This is a usability failure: the exact reason users choose dark mode (avoid bright flashes) is violated by the most prominent UI overlay.

**Why it happens:**
Modals were written as self-contained light-theme components. They sit at z-index 2000, outside the panel hierarchy, and were styled independently of the variable system.

**How to avoid:**
Convert all modal styles to use CSS variables:
```css
.modal { background: var(--surface); border-color: var(--border); color: var(--text); }
.modal .form-group label { color: var(--text-dim); }
.modal select, .modal input { background: var(--surface2); color: var(--text); border-color: var(--border); }
```
Since modals are direct children of `<body>` (child of `<html data-theme="...">`) and not inside `.panel-right`, they naturally inherit root theme variables.

**Warning signs:**
- Modal background stays white in Dark mode
- "Settings" modal is especially jarring when the entire UI is dark
- Modal input fields have wrong background

**Phase to address:**
Phase 1 (Variable Extraction) -- modals are a contained, high-visibility conversion target.

---

### Pitfall 7: Tooltip Colors Assume Light Background Context

**What goes wrong:**
The concept tooltip (lines 1055-1639) uses 20+ hardcoded light-theme colors:
- `.tooltip-label { color: #1a1a2e }` (line 1083)
- `.tooltip-definition { color: #1a1a2e }` (line 1095)
- `.tooltip-synonyms { color: #555 }` (line 1096)
- `.tooltip-meta { color: #6b6b80 }` (line 1098)
- `.tooltip-iri a { color: #3b64e0 }` (line 1099)
- Confidence tiers: `#166534` green, `#92400e` amber, `#991b1b` red (lines 1092-1094)
- Lineage toggle: `background: #f7f8fb; border: #e8e9f0` (lines 1627-1628)
- Multi-pill: `background: #fff` (line 1603), `.multi-pill-label { color: #1a1a2e }` (line 1606)
- `.multi-text-pill { background: #f0f1f5 }` (line 1618)

Tooltips appear over the document text panel (left panel), which is dark in both Mixed and Dark modes. They currently work because they have their own white background, creating a "light island." But when theming, a design decision is required: should tooltips follow the theme or stay always-light?

**Why it happens:**
Tooltips were styled with their own hardcoded light palette, independent of the variable system. They were designed before theming was planned.

**How to avoid:**
1. **Design decision first:** Choose whether tooltips follow the theme or stay always-light. For annotation tools, always-light on dark content provides good visual separation. But in Light mode, a light tooltip on a light background needs a stronger shadow/border.
2. **If tooltips follow theme:** Convert all 20+ hardcoded colors to CSS variables. Tooltip confidence colors (`#166534`, `#92400e`, `#991b1b`) need dark-mode variants.
3. **If tooltips stay light:** Explicitly scope them with overriding CSS variables on `.concept-tooltip` that remain light regardless of theme. Add a comment explaining why.
4. Either way, verify contrast ratios for every tooltip text color against the tooltip background in every mode.

**Warning signs:**
- Tooltip text invisible or barely readable in any mode
- Tooltip blends into background in Light mode (no visual separation)
- Confidence tier colors fail contrast on tooltip background

**Phase to address:**
Phase 2 (Variable Architecture) for the scoping decision, Phase 4 (WCAG Validation) for contrast verification.

---

### Pitfall 8: `--text-dim` and `--accent` Already Marginal on Contrast

**What goes wrong:**
PROJECT.md notes that `--text-dim` (#8b8fa3) on `--bg` (#0f1117) is 5.0-5.2:1 -- passing WCAG AA but with negligible margin. `--accent` in light mode (#3b64e0 on #ffffff) is ~4.6:1 -- barely passing. When defining new theme palettes, even small aesthetic adjustments can push these below 4.5:1. The `--text-dim` value appears in ~128 locations (as `#6b6b80` in light panels, `#8b8fa3` in dark).

**Why it happens:**
Colors were chosen for visual appearance, not mathematical contrast compliance. The existing dark theme just barely passes, and a new light theme designed "by eye" will likely fail in several spots.

**How to avoid:**
1. Build a contrast validation matrix: every text color against every background it appears on, in every theme mode.
2. Set a minimum contrast floor of **5.0:1** (not just 4.5:1) to provide safety margin for font rendering differences across browsers and displays.
3. Automate contrast checks -- do not rely on manual eyeballing.
4. Pay special attention to `--text-dim` at small font sizes (< 14px) where 4.5:1 is required, not the 3:1 large-text threshold.

**Warning signs:**
- Any contrast ratio between 4.5:1 and 5.0:1 (marginal pass)
- `--text-dim` used as small text (font-size: 10px, 11px, 12px -- pervasive in this codebase)
- New light theme's `--accent` on white barely passes

**Phase to address:**
Phase 2 (Palette Design) must target 5.0:1 minimum; Phase 4 (WCAG Validation) for formal verification.

---

### Pitfall 9: Backward Compatibility Breakage in Mixed Mode

**What goes wrong:**
Mixed mode must produce pixel-identical output to the current codebase. But during refactoring to CSS variables, subtle differences creep in: color rounding in RGBA-to-variable conversion, inheritance changes when panel-scoped variables override root variables, and `!important` specificity shifts when restructuring the cascade.

The codebase has 70+ `!important` declarations (many are surgical fixes), plus rules like `.panel-right .panel-body p[style] { color: #6b6b80 !important; }` (line 361) that use `!important` to override inline styles. Moving this to a `[data-theme="mixed"] .panel-right .panel-body p[style]` selector changes its specificity context. The clean-view mode (lines 1377-1538) has 60+ `!important` overrides that interact with inline styles for 26 branch-specific selectors -- any cascade change breaks these.

**Why it happens:**
`!important` declarations create hidden dependencies. Each one was added to solve a specific specificity battle. Restructuring the cascade changes which battles need fighting.

**How to avoid:**
1. **Baseline first:** Take pixel-level screenshots of every UI state before starting: empty state, loaded document, tooltip open, modal open, graph open, each tab active, clean-view mode on/off, POS layer on/off.
2. **Diff at every phase:** After each implementation phase, re-take screenshots and diff against baseline.
3. **Preserve `!important` rules exactly** during variable extraction -- do not remove or modify them.
4. **Test clean-view mode** in all themes -- it has the densest `!important` interactions (lines 1410-1538: 26 branch-specific background overrides and their `:hover` counterparts).

**Warning signs:**
- "It looks the same" without pixel-diff verification
- `!important` count changes during refactoring
- Clean-view mode has any visual differences
- Branch-specific `data-branch` attribute selectors behave differently

**Phase to address:**
Phase 0 (before starting) for baseline screenshots; every subsequent phase for regression checking.

---

### Pitfall 10: Forgetting `color-scheme` Property for Native Elements

**What goes wrong:**
HTML form elements (`<input>`, `<select>`, `<textarea>`), scrollbars, and text selection highlights use browser-native rendering. Without the `color-scheme` CSS property, these render in the browser's default light style even when the app is in dark mode, creating jarring "white rectangles" inside dark panels.

The current codebase has custom scrollbar styling (lines 2211-2214) using `var(--border)` for the global scrollbar, but the modal scrollbar (line 2034) and panel scrollbars (lines 357, 385) use hardcoded `#c0c0cc`. Form inputs in modals (lines 2048-2053) use hardcoded light backgrounds.

**Why it happens:**
`color-scheme` is often forgotten because it is not a color property -- it is a meta-declaration that tells the browser how to render native UI elements. Without it, only custom-styled elements respond to theming.

**How to avoid:**
```css
[data-theme="dark"] { color-scheme: dark; }
[data-theme="light"] { color-scheme: light; }
[data-theme="mixed"] { color-scheme: dark; }
[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail { color-scheme: light; }
```

**Warning signs:**
- Native scrollbar remains light in Dark mode
- Text selection highlight is bright blue on dark background
- `<select>` dropdown has white background in Dark mode

**Phase to address:**
Phase 2 (Variable Architecture) -- add alongside the theme variable definitions.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Leaving some inline `style="#hex"` in JS template literals unconverted | Faster initial delivery | Those elements break in non-default themes; each one is a future bug report | Never -- these are the highest-priority conversion targets |
| Using `!important` to force theme colors over inline styles | Quick fix for specificity battles | Compounds the existing 70+ `!important` problem; makes future CSS changes fragile | Only as last resort for backward-compat with existing `!important` rules already in place |
| Keeping `BRANCH_COLORS` as a static JS object with hardcoded hex values | No refactoring of 15+ call sites | Branch colors cannot respond to theme changes | Only temporarily, if a full re-render on theme switch updates all elements |
| Hardcoding canvas colors with fallback defaults | Canvas works immediately | Canvas never themes correctly; looks wrong in every non-dark theme | Never -- the render function is ~20 lines; converting it is trivial |
| Skipping `prefers-color-scheme` detection | Simpler initial logic | New users get Mixed mode even if OS is set to Dark; poor first impression | Acceptable if added within the same milestone |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Calling `getComputedStyle()` per element during rendering loops | Jank during annotation rendering (hundreds of spans) | Cache `getComputedStyle()` once per render cycle; read all needed variables in a single call | > 200 annotation spans with branch colors |
| Re-rendering canvas minimap on every CSS variable change during transition | Visible redraw flicker on theme toggle | Batch: set `data-theme` attribute, then re-render canvas once via `requestAnimationFrame` | Any theme switch while graph is visible |
| Animating CSS variable transitions on `:root` | Full-page style recalculation on every animation frame (all elements re-resolve all variables) | Never animate root-level CSS variables; use `transition: background 0.15s, color 0.15s` on specific element selectors only | Any transition applied to `:root` or `html` |
| Re-running `getComputedStyle` for each of 26 `BRANCH_COLORS` lookups | 26 DOM lookups per tooltip/pill render | Cache branch colors in a JS object; invalidate on theme change | > 5 tooltips or pill renders per second |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Theme toggle with no visual feedback | User clicks, nothing visibly happens, clicks again confusedly | Instant visual feedback: toggle icon changes immediately; page transitions smoothly (< 200ms) |
| Three-way toggle confusion (Dark/Light/Mixed) | Users do not understand what "Mixed" means | Label it clearly ("Split: dark sidebar, light content") and use a recognizable icon for each mode |
| OS preference overrides explicit user choice | User chose Light but OS is Dark; on next visit, gets Dark | Saved user choice must always take precedence; only use `prefers-color-scheme` for first-visit default |
| Theme toggle hidden in settings modal only | Users cannot find it; violates discoverability principle | Add a visible toggle button in the header bar AND keep it in settings modal |
| Graph/canvas does not update on theme switch | User switches theme, graph stays in old colors | Re-render canvas and update graph node classes in the theme change handler |
| Theme transition affects document text selection | Selection highlight color becomes unreadable during 200ms transition | Set `color-scheme` per theme so native selection colors adapt; or use `::selection` CSS |

## "Looks Done But Isn't" Checklist

- [ ] **Tooltip contrast:** All 20+ tooltip text colors pass 4.5:1 against tooltip background in all three themes
- [ ] **Branch color accessibility:** All 26 branch colors pass 4.5:1 against their background in Dark, Light, and Mixed modes (78 pairs total)
- [ ] **Clean-view mode:** The 60+ `!important` overrides in clean-view (lines 1377-1538) work correctly in all three themes
- [ ] **Graph minimap canvas:** Canvas re-renders with theme-appropriate colors after switch -- toggle with graph open and verify
- [ ] **POS legend swatches:** The 5 POS colors at lines 2514-2518 use inline `style="background:#..."` -- verify visible in all themes
- [ ] **Graph legend:** The 4 legend items at lines 3003-3007 use inline hardcoded colors -- verify converted
- [ ] **Modal scrollbar:** Scrollbar thumbs (lines 2034, 357, 385) use hardcoded `#c0c0cc` -- verify they match theme
- [ ] **See Also links:** `renderFolioReference()` at line 3326 generates links with hardcoded light-theme inline styles
- [ ] **Individual/Property tooltips:** Builders at lines 5273-5389 inject 15+ hardcoded inline colors
- [ ] **Ancestry tree headers:** Branch headers (line 6891) inject `background:${branchColor}15` (hex + opacity hack) -- verify in Dark mode
- [ ] **Multi-tab persistence:** Open two tabs, change theme in one, verify the other updates on focus
- [ ] **prefers-color-scheme:** New user with OS set to Dark sees Dark mode (not Mixed)
- [ ] **FOUC prevention:** Hard refresh (Ctrl+Shift+R) with each saved theme shows no flash
- [ ] **HTML export:** Standalone export format not broken by theme variables (uses its own styles)
- [ ] **`color-scheme` property:** Native form elements, scrollbars, and selection highlights match theme

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Missed hardcoded colors (P1, P6, P7) | LOW | Grep for hex patterns, add missing variable references -- mechanical fix per instance |
| FOUC not prevented (P2) | LOW | Add 5-line inline script to `<head>` -- trivial fix if caught early |
| Specificity cascade broken (P3) | MEDIUM | Restructure cascade order; may require reorganizing 50+ CSS rules and re-testing all three modes |
| Branch colors fail WCAG (P4) | MEDIUM | Create per-theme color mapping; requires design review for 78 color+background pairs |
| Canvas not themed (P5) | LOW | Read CSS variables in render function and add theme change listener -- ~15 lines of change |
| Mixed mode backward compat broken (P9) | HIGH | Pixel-diff debugging across all UI states; may require reverting changes and re-applying carefully |
| `!important` cascade war (P3, P9) | HIGH | Untangling specificity requires understanding all 70+ `!important` declarations and their original purpose; risk of regression |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| JS inline hardcoded colors (P1) | Phase 1: Variable Extraction | Grep shows zero hardcoded hex values in JS template literal `style` attributes |
| FOUC/FART (P2) | Phase 3: Theme Toggle | Hard refresh with each theme saved shows no flash (test on Slow 3G throttle) |
| CSS specificity war (P3) | Phase 2: Variable Architecture | DevTools "Computed" tab shows correct variable for `.panel-right --bg` in all three modes |
| Branch color WCAG (P4) | Phase 2: Palette Design + Phase 4: Validation | Automated contrast check passes for all 26 colors in all 3 themes |
| Canvas/SVG ignored (P5) | Phase 2 + Phase 3 | Toggle theme with graph open; minimap and nodes update correctly |
| Modals hardcoded (P6) | Phase 1: Variable Extraction | Open Settings modal in Dark mode; all colors match theme |
| Tooltip scoping (P7) | Phase 2: Variable Architecture | Open tooltip in Dark mode; content is readable with correct contrast |
| Marginal contrast ratios (P8) | Phase 2: Palette Design + Phase 4: Validation | No text-on-background pair has ratio < 5.0:1 |
| Mixed mode regression (P9) | All Phases | Pixel-diff Mixed mode screenshots match pre-migration baseline |
| Missing `color-scheme` (P10) | Phase 2: Variable Architecture | Native `<select>` and scrollbar match theme in all modes |

## Sources

- [Flash of inAccurate coloR Theme (FART) -- CSS-Tricks](https://css-tricks.com/flash-of-inaccurate-color-theme-fart/) -- FOUC/FART failure modes and the localStorage timing problem
- [Passing Your CSS Theme to Canvas -- Aaron Gustafson](https://www.aaron-gustafson.com/notebook/passing-your-css-theme-to-canvas/) -- getComputedStyle pattern for canvas theming
- [WCAG AA Contrast Guide 2025 -- AllAccessible](https://www.allaccessible.org/blog/color-contrast-accessibility-wcag-guide-2025) -- 4.5:1 and 3:1 thresholds, common failures
- [Dark Mode Done Right -- Mohit Phogat (Feb 2026)](https://medium.com/@mohitphogat/dark-mode-done-right-and-why-most-apps-get-it-wrong-a75f90aab30a) -- Common dark mode implementation mistakes
- [Complete Accessibility Guide for Dark Mode -- Greeden (Feb 2026)](https://blog.greeden.me/en/2026/02/23/complete-accessibility-guide-for-dark-mode-and-high-contrast-color-design-contrast-validation-respecting-os-settings-icons-images-and-focus-visibility-wcag-2-1-aa/) -- Focus visibility, icon contrast, SVG theming in dark mode
- [Offering Dark Mode Doesn't Satisfy WCAG -- BOIA](https://www.boia.org/blog/offering-a-dark-mode-doesnt-satisfy-wcag-color-contrast-requirements) -- Each theme mode must independently pass WCAG
- [SVG Dark Mode with currentColor -- Hidde de Vries](https://hidde.blog/making-single-color-svg-icons-work-in-dark-mode/) -- SVG fill/stroke theming patterns
- [Dark Mode in CSS Complete Guide -- CSS-Tricks](https://css-tricks.com/a-complete-guide-to-dark-mode-on-the-web/) -- Specificity conflicts with mixed theme selectors
- [CSS Custom Properties for Theming -- Ronald Svilcins (Mar 2025)](https://ronaldsvilcins.com/2025/03/30/a-practical-guide-to-css-custom-properties-for-theming/) -- Variable scoping, fallback patterns, performance
- [MDN: color-scheme property](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/color-scheme) -- Native element theming
- Direct codebase analysis: `frontend/index.html` lines 1-9668 -- all line number references verified
