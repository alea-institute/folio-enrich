# Phase 1: CSS Variable Foundation - Research

**Researched:** 2026-04-02
**Domain:** CSS Custom Properties, Design Token Systems, Theme Switching
**Confidence:** HIGH

## Summary

Phase 1 converts all hardcoded CSS color values in `frontend/index.html` to CSS custom properties organized into a two-layer token system (palette primitives + semantic tokens), then defines complete variable sets for Dark, Light, and Mixed themes under `data-theme` attribute selectors.

The existing codebase has **541 hardcoded hex values** and **139 hardcoded rgba() values** across **~2,460 lines of inline CSS**, plus **190 hex values** and **~85 color-bearing inline style assignments** in the **~7,240 lines of JavaScript**. There are already **16 CSS variables** at `:root` with **164 var() usages**. The current "Mixed" layout uses scoped variable overrides on `.panel-right` and `.panel-detail` classes -- this pattern becomes the foundation for the Mixed theme implementation.

A critical complexity is the **three separate branch color systems** that must be unified: (1) 11 bright `--branch-*` CSS variables at `:root`, (2) 27 dark WCAG-safe colors in `BRANCH_COLORS` JS object, and (3) 26x4=104 `data-branch` CSS rules using those same dark colors with rgba() tints. Phase 1 creates CSS variables for all 26 branches per theme; Phase 2 will unify the JS object.

**Primary recommendation:** Use a two-layer token system with kebab-case naming. Define palette primitives as static values, semantic tokens as `var()` references to primitives, and theme selectors that remap only the semantic layer. Use `color-mix(in srgb, var(--branch-X), transparent Y%)` for branch tint backgrounds instead of the old rgb-components trick -- `color-mix()` has 92%+ browser support and is far cleaner.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Two-layer token system -- palette primitives (e.g., `--gray-900`, `--blue-500`) that never change, plus semantic tokens (e.g., `--bg`, `--surface`, `--accent`) that themes swap. Themes redefine the semantic layer only.
- **D-02:** Kebab-case branch names for the 26 FOLIO branch colors (e.g., `--branch-litigation`, `--branch-corporate-law`, `--branch-ip`). Readable, matches FOLIO ontology naming.
- **D-03:** Cool gray temperature -- white with blue-gray undertones. Values: `--bg: #ffffff`, `--surface: #f5f6fa`, `--surface2: #eceef4`, `--surface3: #e2e5ee`, `--border: #d0d4e0`, `--text: #1a1d27`, `--text-dim: #5c6070`. Professional, matches the dark theme's cool blue-gray personality.
- **D-04:** Darker blue accent in light mode -- shift from `#4a7cff` (fails WCAG on white at 3.2:1) to `#2d5ee0` (passes at 5.1:1). Same hue family, just darker for contrast compliance.
- **D-05:** Theme-specific branch colors -- define entirely different branch color values per theme (26 x 3 = 78 values). Not just opacity changes -- full per-theme control.
- **D-06:** Claude's discretion on light-mode branch values -- pick values that maintain hue identity and pass WCAG AA contrast. User reviews in final result, not upfront.
- **D-07:** All-at-once conversion -- single pass audit, define, replace all hardcoded colors. No incremental batches. One big commit avoids partial/mixed states.
- **D-08:** Before/after screenshot verification -- take screenshots before migration, then after, visually compare using Chrome DevTools MCP to confirm Mixed mode backward compatibility.

### Claude's Discretion
- Light-mode branch color values (D-06) -- Claude picks WCAG-compliant values per theme
- Semantic token naming for component-specific colors (e.g., `--tooltip-bg`, `--modal-border`) -- Claude decides granularity

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CSSF-01 | All hardcoded CSS color values converted to CSS custom properties | Color audit identifies 541 hex + 139 rgba in CSS, 190 hex + 5 rgba in JS. Token architecture section provides naming conventions and categorization strategy. |
| CSSF-02 | Two-layer token system implemented (palette primitives + semantic tokens) | Architecture Patterns section defines the exact layer structure, naming convention, and code examples for both layers. |
| CSSF-03 | `data-theme` attribute on `<html>` controls theme switching via CSS selectors | Architecture Patterns section covers `[data-theme]` selector pattern and specificity strategy. |
| CSSF-04 | Complete dark theme variable set defined under `[data-theme="dark"]` | Dark theme values already exist at `:root` -- they move into `[data-theme="dark"]` selector. Semantic token mapping documented. |
| CSSF-05 | Complete light theme variable set defined under `[data-theme="light"]` | User locked D-03/D-04 values. Component-specific tokens (modal, tooltip, etc.) derived from base light palette. |
| CSSF-06 | Mixed theme scopes dark variables globally with light overrides on `.panel-right` and `.panel-detail` | Architecture section documents the combined selector pattern: `[data-theme="mixed"]` at root + scoped overrides. Current `.panel-right`/`.panel-detail` override pattern is the exact template. |
| CSSF-07 | Branch color background opacity adapts per theme (lower opacity on light backgrounds) | Branch color section documents the `color-mix()` approach for per-theme tint opacity and the 26x3 variable matrix. |

</phase_requirements>

## Standard Stack

### Core
| Technology | Version | Purpose | Why Standard |
|------------|---------|---------|--------------|
| CSS Custom Properties | Level 1 (Baseline) | All color theming | 97%+ browser support, native cascade, no build step needed |
| `color-mix()` | CSS Color Level 5 | Branch background tints | 92%+ support, replaces verbose rgb-components trick, works with var() |
| `data-theme` attribute | HTML5 | Theme selector | Modern standard, clean CSS specificity, no class pollution |
| Vanilla JS | ES6+ | Theme init script in `<head>` | No dependencies, matches project constraint |

### Supporting
| Technology | Purpose | When to Use |
|------------|---------|-------------|
| `localStorage` | Theme persistence | Phase 2 -- not needed in Phase 1 CSS foundation |
| `prefers-color-scheme` | OS preference detection | Phase 2 -- not needed in Phase 1 |
| `color-scheme` CSS property | Native scrollbar/form theming | Phase 2 -- THSW-06 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `color-mix()` for tints | RGB components trick (`--color-rgb: R,G,B`) | Universal support but verbose -- requires duplicate variable for every color needing alpha. `color-mix()` at 92% is sufficient for this app's audience (legal professionals on modern browsers). |
| `color-mix()` for tints | CSS Relative Color Syntax (`rgb(from var(--x) r g b / 0.1)`) | Newer (89% support), more powerful but less browser coverage. Save for future enhancement. |
| `[data-theme]` attribute | `.theme-dark` / `.theme-light` classes | Classes work but data attributes are semantically cleaner and conventional for theme switching (used by Bootstrap 5.3, Tailwind, Radix). |
| Single-file inline CSS | External `.css` file | Would require changing project architecture. Constraint is single-file; all CSS stays inline in `<style>`. |

### No Installation Required
This phase adds zero dependencies. All work is pure CSS within the existing `<style>` block.

## Architecture Patterns

### Token System Structure

```
<style>
  /* ══════════ LAYER 1: PALETTE PRIMITIVES ══════════
     Raw color values. These NEVER change between themes.
     Named by hue + lightness step. */

  :root {
    /* Neutrals (dark) */
    --gray-950: #0f1117;
    --gray-900: #1a1d27;
    --gray-800: #242836;
    --gray-700: #2e3348;
    --gray-600: #8b8fa3;
    --gray-200: #e4e6f0;

    /* Neutrals (light) */
    --white: #ffffff;
    --cool-gray-50: #f5f6fa;
    --cool-gray-100: #eceef4;
    --cool-gray-150: #e2e5ee;
    --cool-gray-200: #d0d4e0;
    --cool-gray-800: #5c6070;
    --cool-gray-900: #1a1d27;

    /* Blues */
    --blue-400: #6c8cff;
    --blue-500: #4a5fa0;
    --blue-600: #2d5ee0;

    /* Status colors */
    --green-500: #4caf7c;
    --orange-500: #e8a54c;
    --red-500: #e05555;
    --cyan-500: #5ec4d4;
    --purple-500: #b07ee8;

    /* ... additional primitives as needed */
  }

  /* ══════════ LAYER 2: SEMANTIC TOKENS ══════════
     These reference primitives. Themes redefine ONLY this layer. */

  /* Dark theme (default / explicit) */
  :root,
  [data-theme="dark"] {
    --bg: var(--gray-950);
    --surface: var(--gray-900);
    --surface2: var(--gray-800);
    --surface3: var(--gray-700);
    --border: var(--gray-700);
    --text: var(--gray-200);
    --text-dim: var(--gray-600);
    --accent: var(--blue-400);
    --accent-dim: var(--blue-500);
    /* ... component tokens ... */
    /* ... branch colors ... */
  }

  /* Light theme */
  [data-theme="light"] {
    --bg: var(--white);
    --surface: var(--cool-gray-50);
    --surface2: var(--cool-gray-100);
    --surface3: var(--cool-gray-150);
    --border: var(--cool-gray-200);
    --text: var(--cool-gray-900);
    --text-dim: var(--cool-gray-800);
    --accent: var(--blue-600);
    /* ... */
  }

  /* Mixed theme: dark root + light panels */
  [data-theme="mixed"] {
    /* Same as dark at root level */
    --bg: var(--gray-950);
    --surface: var(--gray-900);
    /* ... same as dark ... */
  }
  [data-theme="mixed"] .panel-right,
  [data-theme="mixed"] .panel-detail {
    /* Override to light for right/detail panels */
    --bg: var(--white);
    --surface: var(--cool-gray-50);
    /* ... same as light ... */
  }
</style>
```

### Branch Color Variable Pattern

Each of the 26 branches gets a CSS variable per theme. The variable holds the solid color; tint backgrounds use `color-mix()`.

```css
/* Dark theme branch colors (existing bright values) */
[data-theme="dark"] {
  --branch-actor-player: #5ec4d4;
  --branch-area-of-law: #e8a54c;
  /* ... 26 total ... */
}

/* Light theme branch colors (darker for WCAG on white) */
[data-theme="light"] {
  --branch-actor-player: #1e6fa0;
  --branch-area-of-law: #1a5276;
  /* ... 26 total ... */
}

/* Usage in annotation spans */
.annotation-span[data-branch="Actor / Player"] {
  border-bottom-color: var(--branch-actor-player);
  background: color-mix(in srgb, var(--branch-actor-player) 12%, transparent);
}
.annotation-span[data-branch="Actor / Player"]:hover {
  background: color-mix(in srgb, var(--branch-actor-player) 22%, transparent);
}
```

This pattern **eliminates 104 branch-specific CSS rules** (26 branches x 4 states) down to **26 rules** with `color-mix()` + **26x3 variable definitions**. The clean-view overrides similarly simplify.

### Semantic Token Granularity

Based on auditing the ~166 unique hex colors and ~113 unique rgba values, the semantic tokens should be organized into these categories:

| Category | Example Tokens | Count Est. |
|----------|---------------|------------|
| **Core palette** | `--bg`, `--surface`, `--surface2`, `--surface3`, `--border`, `--text`, `--text-dim`, `--accent`, `--accent-dim` | 9 |
| **Status colors** | `--green`, `--orange`, `--red`, `--cyan`, `--purple` | 5 |
| **Highlights** | `--highlight`, `--highlight-confirmed`, `--highlight-preliminary`, `--highlight-rejected` | 4 |
| **Branch colors** | `--branch-actor-player` through `--branch-system-identifiers`, `--branch-default` | 27 |
| **Component: Tooltip** | `--tooltip-bg`, `--tooltip-border`, `--tooltip-text`, `--tooltip-shadow` | 4 |
| **Component: Modal** | `--modal-bg`, `--modal-border`, `--modal-text`, `--modal-text-dim`, `--modal-input-bg`, `--modal-input-border` | 6 |
| **Component: Graph** | `--graph-header-bg`, `--graph-header-text`, `--graph-header-border` | 3 |
| **Confidence tiers** | `--conf-high`, `--conf-mid`, `--conf-low`, `--conf-high-bg`, `--conf-mid-bg`, `--conf-low-bg` | 6 |
| **Feedback states** | `--feedback-positive`, `--feedback-positive-bg`, `--feedback-negative`, `--feedback-negative-bg` | 4 |
| **Individual colors** | `--individual-citation`, `--individual-entity` | 2 |
| **Property color** | `--property-underline` | 1 |
| **Layer chips** | `--layer-concepts`, `--layer-individuals`, `--layer-properties`, `--layer-pos` | 4 |
| **POS colors** | `--pos-noun`, `--pos-propn`, `--pos-verb`, `--pos-adj`, `--pos-adv` | 5 |
| **Misc UI** | `--scrollbar-thumb`, `--scrollbar-thumb-hover`, `--undo-toast-bg`, `--badge-dot` | 4+ |
| **Total** | | **~84 semantic + 27 branch = ~111 tokens** |

### Migration Strategy: All-at-Once (D-07)

The migration follows this sequence within a single commit:

1. **Screenshot** the current state (before)
2. **Add** `data-theme="mixed"` to `<html>` tag (no visual change yet)
3. **Define** palette primitives in `:root`
4. **Define** semantic tokens in `[data-theme="dark"]`, `[data-theme="light"]`, `[data-theme="mixed"]`
5. **Replace** all hardcoded hex/rgba values in CSS with `var()` references
6. **Replace** hardcoded colors in HTML inline styles with `var()` references
7. **Consolidate** the 104 branch `data-branch` rules into 26 rules using `color-mix()`
8. **Remove** the old `.panel-right` / `.panel-detail` scoped overrides (replaced by `[data-theme="mixed"]` selectors)
9. **Screenshot** the result and compare (after)

### Specificity Strategy

```
:root                              /* Primitives: specificity 0,0,1 */
:root, [data-theme="dark"]         /* Dark semantic: specificity 0,1,0 (attribute) */
[data-theme="light"]               /* Light semantic: specificity 0,1,0 */
[data-theme="mixed"]               /* Mixed root: specificity 0,1,0 */
[data-theme="mixed"] .panel-right  /* Mixed panel override: specificity 0,2,0 */
```

The attribute selector `[data-theme]` has specificity 0,1,0 (same as a class), which naturally overrides `:root` (0,0,1). The mixed panel overrides at 0,2,0 beat the root mixed at 0,1,0. This cascade is clean and predictable.

### Anti-Patterns to Avoid

- **Putting primitive values in theme selectors:** Primitives go in `:root` only. Theme selectors remap semantic tokens to primitives, never to raw hex values. This means every hardcoded color must first become a primitive, then get a semantic name.
- **Using `!important` for theme overrides:** The specificity strategy above makes `!important` unnecessary. The only existing `!important` usages are in `.clean-view` rules which serve a different purpose (overriding JS-applied inline styles).
- **Creating token explosion:** Not every unique hex value needs its own semantic token. Many hardcoded values are slight variations of the same concept (e.g., `#f0f0f5`, `#f0f0f4`, `#f5f5f8` are all "light hover background"). Collapse these into a single semantic token.
- **Duplicating variables across `.panel-right` and `.panel-detail`:** Currently these two selectors repeat identical variable blocks. In the new system, both are covered by a single combined selector: `[data-theme="mixed"] .panel-right, [data-theme="mixed"] .panel-detail`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Color transparency/tinting | Manual rgba() with separate `--color-rgb` variables | `color-mix(in srgb, var(--color) N%, transparent)` | Eliminates need for duplicate RGB-triplet variables; 92%+ browser support |
| Contrast ratio calculation | Manual hex math or JS contrast checkers at runtime | Pre-computed values verified with WebAIM Contrast Checker during development | WCAG compliance is a design-time concern, not runtime |
| Theme variable scoping | Custom JS to swap classes or inject stylesheets | `[data-theme]` CSS attribute selectors | Pure CSS, instant, no JS runtime cost, conventional pattern |
| Branch color repetition | 104 separate CSS rules (26 branches x 4 states) | CSS variables + `color-mix()` (26 rules total) | 4x reduction in CSS rules, single source of truth per branch |

**Key insight:** The current codebase has 3 separate sources of truth for branch colors (CSS `:root` vars, JS `BRANCH_COLORS` object, and CSS `data-branch` rules). Phase 1 creates the authoritative CSS variable source; Phase 2 will eliminate the JS duplication.

## Common Pitfalls

### Pitfall 1: Forgetting Colors in JS-Generated HTML
**What goes wrong:** All CSS hardcoded colors get converted but JS template literals still output `color:#6b6b80` in inline `style` attributes, which don't respond to theme changes.
**Why it happens:** The 190 hex values in JS are spread across ~85 lines of template literal HTML generation, easy to miss in a CSS-focused audit.
**How to avoid:** Phase 1 scope is CSS only (per the CONTEXT). However, hardcoded colors in HTML template literals and inline `style` attributes on static HTML elements should also be converted to use `var()` -- inline styles CAN reference CSS custom properties. For JS-generated HTML, convert `style="color:#6b6b80"` to `style="color:var(--text-dim)"`.
**Warning signs:** After conversion, grep for `#[0-9a-fA-F]` in the entire file. Any remaining hex values that aren't inside `:root` primitive definitions are missed conversions.

### Pitfall 2: Mixed Theme Backward Compatibility Breakage
**What goes wrong:** The Mixed theme looks different from the current application because scoped variables resolve differently or are missing.
**Why it happens:** The current `.panel-right` and `.panel-detail` overrides define 14-15 variables each. If the new `[data-theme="mixed"]` scoped overrides miss even one, that panel falls back to the dark theme value for that token.
**How to avoid:** The `[data-theme="mixed"] .panel-right` selector must define EVERY semantic token that differs between dark and light. Create a checklist: for each semantic token, verify the Mixed-mode scoped value matches the current `.panel-right` value.
**Warning signs:** Visual diff between before/after screenshots shows any color difference in right or detail panels.

### Pitfall 3: `color-mix()` Fallback Gap
**What goes wrong:** Users on older browsers (pre-Chrome 111, pre-Firefox 113, pre-Safari 16.2) see broken backgrounds on annotations.
**Why it happens:** `color-mix()` returns an invalid value on unsupported browsers, so the property is ignored entirely.
**How to avoid:** For the branch annotation backgrounds specifically, provide a fallback declaration before the `color-mix()` one:
```css
.annotation-span[data-branch="Actor / Player"] {
  background: rgba(94, 196, 212, 0.12); /* fallback */
  background: color-mix(in srgb, var(--branch-actor-player) 12%, transparent);
}
```
Given 92%+ support and the target audience (legal professionals on modern browsers), this is low risk but good practice.
**Warning signs:** Test in Safari 15 or older Chrome to verify graceful degradation.

### Pitfall 4: Inline Style Specificity Blocking var() Override
**What goes wrong:** Elements with JS-applied `style="color:#1a1a2e"` ignore theme changes because inline styles beat CSS variable definitions.
**Why it happens:** JS functions like `renderAnnotatedText()` set colors via inline styles that take specificity precedence.
**How to avoid:** Convert inline style color assignments to use `var()` references (which resolves correctly per cascade), or move the color assignment to a CSS class. Note: `style="color:var(--text)"` DOES work -- CSS custom properties resolve in inline styles.
**Warning signs:** Elements that don't change color when switching themes.

### Pitfall 5: Token Naming Collisions with Existing Variables
**What goes wrong:** Renaming or removing existing CSS variables like `--bg`, `--surface`, etc. breaks the 164 existing `var()` usages.
**Why it happens:** The new system needs the same token names but in a different scope.
**How to avoid:** Keep the exact same semantic token names (`--bg`, `--surface`, `--text`, etc.). The existing `:root` definitions become the `[data-theme="dark"]` definitions. The existing `var(--bg)` references work unchanged -- they just resolve through the theme selector instead of `:root`.
**Warning signs:** Any CSS error or unstyled element after migration.

### Pitfall 6: Collapse of Near-Duplicate Colors Changing Appearance
**What goes wrong:** Collapsing visually similar but intentionally different colors (e.g., `#f0f0f5` for hover, `#f5f5f8` for static background) into one token changes the visual weight of interactive states.
**Why it happens:** Overzealous deduplication during token creation.
**How to avoid:** Only collapse colors that serve the same semantic purpose. If two similar colors are used for "hover" vs "default" states of the same component, they need separate tokens (e.g., `--surface-hover` vs `--surface`).
**Warning signs:** Hover states that look identical to default states, or components that lose their visual hierarchy.

## Code Examples

### Example 1: Theme Selector Structure
```css
/* Palette primitives (never change) */
:root {
  --gray-950: #0f1117;
  --gray-900: #1a1d27;
  /* ... */
}

/* Dark theme semantic tokens */
[data-theme="dark"] {
  --bg: var(--gray-950);
  --surface: var(--gray-900);
  --text: #e4e6f0;
  --accent: #6c8cff;
  /* Branch colors for dark backgrounds (bright/vibrant) */
  --branch-actor-player: #5ec4d4;
  --branch-area-of-law: #e8a54c;
}

/* Light theme semantic tokens */
[data-theme="light"] {
  --bg: #ffffff;
  --surface: #f5f6fa;
  --text: #1a1d27;
  --accent: #2d5ee0;
  /* Branch colors for light backgrounds (darker for WCAG) */
  --branch-actor-player: #1e6fa0;
  --branch-area-of-law: #1a5276;
}

/* Mixed: dark root, light panels */
[data-theme="mixed"] {
  --bg: var(--gray-950);
  --surface: var(--gray-900);
  --text: #e4e6f0;
  --accent: #6c8cff;
  --branch-actor-player: #5ec4d4;
}
[data-theme="mixed"] .panel-right,
[data-theme="mixed"] .panel-detail {
  --bg: #ffffff;
  --surface: #f5f6fa;
  --text: #1a1d27;
  --accent: #2d5ee0;
  --branch-actor-player: #1e6fa0;
}
```

### Example 2: Branch Annotation with color-mix()
```css
/* Before: 4 separate rules per branch (normal, hover, clean-normal, clean-hover) */
.annotation-span[data-branch="Actor / Player"] {
  border-bottom-color: #1e6fa0;
  background: rgba(30,111,160,0.12);
}
.annotation-span[data-branch="Actor / Player"]:hover {
  background: rgba(30,111,160,0.22);
}

/* After: theme-aware with color-mix(), same rules for all themes */
.annotation-span[data-branch="Actor / Player"] {
  border-bottom-color: var(--branch-actor-player);
  background: color-mix(in srgb, var(--branch-actor-player) 12%, transparent);
}
.annotation-span[data-branch="Actor / Player"]:hover {
  background: color-mix(in srgb, var(--branch-actor-player) 22%, transparent);
}
```

### Example 3: Converting Inline Style Colors
```html
<!-- Before -->
<div style="font-size:12px;color:#6b6b80;margin-bottom:10px"></div>

<!-- After -->
<div style="font-size:12px;color:var(--text-dim);margin-bottom:10px"></div>
```

### Example 4: data-theme on HTML Element
```html
<!-- Phase 1: statically set to "mixed" for backward compatibility -->
<html lang="en" data-theme="mixed">
```

### Example 5: Component-Specific Token Usage
```css
/* Before: hardcoded modal colors */
.modal { background: #ffffff; color: #1a1a2e; border: 1px solid #d0d0da; }
.modal h3 { color: #1a1a2e; }

/* After: semantic tokens (modal always light in current design) */
.modal { background: var(--modal-bg); color: var(--modal-text); border: 1px solid var(--modal-border); }
.modal h3 { color: var(--modal-text); }

/* Token definitions */
[data-theme="dark"] {
  --modal-bg: #ffffff;       /* modals are always light-themed currently */
  --modal-text: #1a1a2e;
  --modal-border: #d0d0da;
}
[data-theme="light"] {
  --modal-bg: #ffffff;
  --modal-text: #1a1d27;
  --modal-border: #d0d4e0;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RGB components trick (`--color-rgb: R,G,B`) | `color-mix(in srgb, var(--color) N%, transparent)` | 2023 (Chrome 111+) | Eliminates duplicate variables, cleaner syntax |
| `.theme-dark` class toggling | `data-theme` attribute | 2022-2023 (Bootstrap 5.3) | Industry standard, semantic, better tooling support |
| Single-layer variables | Two-layer (primitive + semantic) | 2021-2023 | Enables theme switching without redefining every rule |
| Manual rgba for each alpha variant | CSS Relative Color Syntax | 2024 (Chrome 131+) | Most powerful but newer; `color-mix()` is safer choice today |

**Deprecated/outdated:**
- **`light-dark()` CSS function**: Only supports two modes; cannot express the three-mode (Dark/Light/Mixed) system required here. Explicitly out of scope per REQUIREMENTS.md.
- **View Transitions API**: Could animate theme switch, but out of scope per REQUIREMENTS.md (requires Safari flags).
- **`prefers-color-scheme` only approach**: Not sufficient alone -- users need explicit three-way toggle control.

## Open Questions

1. **Mixed Theme Modal Coloring**
   - What we know: Modals currently render with light-colored hardcoded values regardless of which panel they overlay. The settings modal, cascade modal, graph modal, and FOLIO modal all use white backgrounds.
   - What's unclear: Should modals in Dark theme switch to dark backgrounds, or remain light across all themes? The current design always renders modals light.
   - Recommendation: For Phase 1, make modals theme-aware (dark bg in dark mode, light bg in light mode, light bg in mixed mode since most modals open from right panel). This is the expected behavior for a theme system. Define `--modal-bg`, `--modal-text`, etc. per theme.

2. **Graph Modal (Always Dark?)**
   - What we know: The graph modal overlay uses dark colors (`#1a1d27` header, dark canvas background) even though it's a full-screen overlay not scoped to any panel.
   - What's unclear: Should the graph stay dark-themed in all modes for visual consistency with the dark canvas, or follow the active theme?
   - Recommendation: Keep graph modal dark-themed in all modes via component-specific tokens that don't change with themes. The dark canvas provides better contrast for the colorful node visualization.

3. **Undo Toast Coloring**
   - What we know: The undo toast uses a dark background (`#1a1a2e`) regardless of context.
   - What's unclear: Should toasts be theme-aware?
   - Recommendation: Keep dark in all themes. Toast overlays are conventionally dark (like snackbars in Material Design) for visibility.

4. **Exact Count of Semantic Tokens**
   - What we know: Estimate ~111 total tokens needed (84 semantic + 27 branch).
   - What's unclear: Final count depends on how aggressively near-duplicate colors are collapsed.
   - Recommendation: Start with the categorization in the Architecture section, collapse where colors serve the same semantic purpose, allow ~10% expansion for edge cases discovered during implementation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Visual regression via Chrome DevTools MCP screenshots + structural grep |
| Config file | None (no automated CSS test framework) |
| Quick run command | `grep -P '#[0-9a-fA-F]{3,8}' frontend/index.html \| grep -v ':root' \| grep -v '\/\*' \| wc -l` |
| Full suite command | `cd backend && .venv/bin/python -m pytest tests/ -v` (backend unaffected; run to confirm no regressions) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CSSF-01 | Zero hardcoded colors outside `:root` primitives | structural | `grep -cP '#[0-9a-fA-F]{3,8}' frontend/index.html` -- compare against expected count (only primitives in `:root`) | No automated test -- manual grep |
| CSSF-02 | Two-layer tokens present | structural | Verify `:root` has primitives, `[data-theme]` has semantic tokens -- manual inspection | No automated test |
| CSSF-03 | `data-theme` controls themes | visual | Screenshot with `data-theme="dark"`, `"light"`, `"mixed"` via Chrome DevTools MCP | Manual |
| CSSF-04 | Dark theme complete | visual | Screenshot with `data-theme="dark"`, verify all panels dark | Manual |
| CSSF-05 | Light theme complete | visual | Screenshot with `data-theme="light"`, verify all panels light | Manual |
| CSSF-06 | Mixed theme matches current | visual | Screenshot comparison: before (current) vs after (`data-theme="mixed"`) | Manual |
| CSSF-07 | Branch opacity adapts | visual | Compare branch annotation spans in light vs dark screenshots | Manual |

### Sampling Rate
- **Per task commit:** `grep -cP '#[0-9a-fA-F]{3,8}' frontend/index.html` (hardcoded count should decrease)
- **Per wave merge:** Chrome DevTools MCP screenshots of all three themes
- **Phase gate:** Zero hardcoded colors outside primitives + visual match of Mixed to current appearance

### Wave 0 Gaps
- None -- this is a CSS-only phase; existing backend test suite runs as a no-regression check but CSS validation is inherently visual and structural.

## Sources

### Primary (HIGH confidence)
- `frontend/index.html` lines 1-2463 -- direct CSS audit of all color values
- `frontend/index.html` lines 3139-3167 -- BRANCH_COLORS JS object audit
- [Can I use: color-mix()](https://caniuse.com/mdn-css_types_color_color-mix) -- 92.42% browser support verified
- [Can I use: CSS Relative Colors](https://caniuse.com/css-relative-colors) -- 89.57% browser support verified
- [MDN: color-mix()](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/color-mix) -- official documentation
- [MDN: CSS Relative Colors](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_colors/Relative_colors) -- official documentation

### Secondary (MEDIUM confidence)
- [Bootstrap 5.3 Color Modes](https://getbootstrap.com/docs/5.3/customize/color-modes/) -- industry standard for `data-theme` pattern
- [Penpot: Developer's Guide to Design Tokens](https://penpot.app/blog/the-developers-guide-to-design-tokens-and-css-variables/) -- two-layer token architecture patterns
- [Chrome for Developers: CSS color-mix()](https://developer.chrome.com/docs/css-ui/css-color-mix) -- usage patterns
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) -- WCAG contrast verification tool

### Tertiary (LOW confidence)
- [FrontendTools: CSS Variables Guide](https://www.frontendtools.tech/blog/css-variables-guide-design-tokens-theming-2025) -- general patterns, not authoritative
- [Aleksandr Hovhannisyan: The Perfect Theme Switch](https://www.aleksandrhovhannisyan.com/blog/the-perfect-theme-switch/) -- good patterns but individual blog

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- CSS Custom Properties and `color-mix()` are well-documented, widely supported browser standards
- Architecture: HIGH -- Two-layer token system is the established pattern used by Bootstrap, Tailwind, Radix, and every major design system
- Pitfalls: HIGH -- Identified through direct code audit of the actual codebase (not theoretical)
- Branch color strategy: MEDIUM -- The `color-mix()` consolidation is architecturally sound but the exact opacity percentages may need visual tuning during implementation

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (stable domain; CSS specs move slowly)
