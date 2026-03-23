# Research Summary: FOLIO Enrich Theme System

**Domain:** Multi-mode CSS theming for a single-file vanilla JS legal document annotation tool
**Researched:** 2026-03-22
**Overall confidence:** HIGH

## Executive Summary

The CSS theming ecosystem in 2025-2026 has fully standardized on the `data-theme` attribute + CSS custom properties pattern. Every major framework (Bootstrap 5.3, Tailwind, Bulma) uses this approach. The newer `light-dark()` CSS function, while elegant, is unsuitable here because it only supports two modes (light/dark) and cannot express the Mixed mode (dark-left, light-right panels) that is this project's differentiator.

The codebase is well-positioned for this migration. It already uses 17+ CSS custom properties at `:root` and already overrides them on `.panel-right` and `.panel-detail` to create the current mixed dark/light layout. The primary work is: (1) auditing and converting ~690 hardcoded color references to CSS variables, (2) organizing those variables under `[data-theme]` selectors, and (3) adding the switching infrastructure (localStorage, flash-prevention script, toggle UI).

The biggest risk is Pitfall 1: hardcoded colors surviving the migration. With ~2,456 lines of CSS and ~7,000 lines of JS containing color references, a systematic grep-and-categorize approach is essential. The second risk is inline styles applied by JavaScript (BRANCH_COLORS object, dynamic annotation coloring) which override CSS variable-based theming due to specificity.

No new dependencies are needed. This is pure CSS + vanilla JS. The `color-scheme` CSS property provides free native theming of form controls and scrollbars. A ~30-line inline contrast validation function replaces external accessibility tools for development-time WCAG AA verification.

## Key Findings

**Stack:** `data-theme` attribute on `<html>` + CSS custom properties + `localStorage` + inline flash-prevention script + `prefers-color-scheme` detection. No new dependencies. Do NOT use `light-dark()` (two-mode limitation) or OKLCH (orthogonal to theming).

**Architecture:** Two-layer token system (raw palette + semantic tokens), scoped variable overrides for Mixed mode, ThemeManager singleton for JS orchestration, cached `getComputedStyle` for canvas colors.

**Critical pitfall:** Hardcoded colors surviving the audit (~690 references to find and convert). Secondary: inline JS styles overriding CSS variables.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Foundation: Color Audit and Variable System** - Must come first because every other phase depends on all colors being CSS variables. This is the highest-effort phase.
   - Addresses: Hardcoded color conversion, two-layer token architecture
   - Avoids: Pitfall 1 (orphaned hardcoded colors) by being systematic and thorough

2. **Theme Definitions and Switching** - Define the three `[data-theme]` variable sets and implement the switching mechanism (toggle, localStorage, flash prevention).
   - Addresses: Dark/Light/Mixed mode CSS, ThemeManager JS, header toggle, settings modal
   - Avoids: Pitfall 4 (flash-prevention script placement), Pitfall 7 (localStorage key collision)

3. **Mixed Mode and Panel Scoping** - Formalize the existing dark-left/light-right layout under `[data-theme="mixed"]` with proper scoped variable overrides.
   - Addresses: Panel-scoped variables, `color-scheme` property per panel region
   - Avoids: Pitfall 3 (specificity wars in mixed mode)

4. **Edge Cases and Polish** - Canvas theming, scrollbar theming, modal/tooltip theming, branch color contrast validation.
   - Addresses: Canvas getComputedStyle, scrollbar-color, modal inheritance, WCAG AA validation
   - Avoids: Pitfall 5 (branch colors on light backgrounds), Pitfall 8 (canvas not redrawing)

5. **Accessibility Verification** - Validate all foreground/background pairs across all three modes meet WCAG AA (4.5:1 normal, 3:1 large).
   - Addresses: Inline contrast checker, branch color audit (26 colors x 2 backgrounds)
   - Avoids: Pitfall 5 (branch colors failing on light backgrounds)

**Phase ordering rationale:**
- Phase 1 (audit) unblocks Phase 2 (definitions) -- cannot define theme variables until all colors are variables
- Phase 2 (switching) unblocks Phase 3 (mixed mode) -- mixed mode is a specific theme that requires the switching infrastructure
- Phase 3 (mixed mode) proves backward compatibility -- must verify mixed mode matches current UI before shipping
- Phase 4 (edge cases) and Phase 5 (accessibility) can be parallelized -- they are independent

**Research flags for phases:**
- Phase 1: Likely needs deeper analysis (the ~690 color reference audit is mechanical but large)
- Phase 2: Standard patterns, unlikely to need additional research
- Phase 3: The existing `.panel-right` / `.panel-detail` overrides are already a working prototype of this phase
- Phase 4: Canvas theming is well-documented; scrollbar theming via `color-scheme` is straightforward
- Phase 5: WCAG contrast formula is a W3C standard; the inline checker is ~30 lines

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `data-theme` + CSS custom properties is the universal standard. Verified via MDN, Bootstrap 5.3, Tailwind, multiple independent sources. |
| Features | HIGH | Table stakes features (dark, light, persistence, flash prevention) are well-defined. Mixed mode is unique but architecturally simple. |
| Architecture | HIGH | Two-layer token system and scoped overrides are documented patterns. The codebase already uses scoped variable overrides on `.panel-right`. |
| Pitfalls | HIGH | All pitfalls are verified from real-world implementations. The hardcoded color audit risk is quantifiable (~690 references). |
| Contrast validation | HIGH | WCAG luminance formula is a W3C standard (G17/G18 techniques). The inline JS implementation is ~30 lines with no dependencies. |

## Gaps to Address

- **Exact count of colors needing conversion**: The ~690 count includes all regex matches (hex, rgba, named colors). Some are intentional (`transparent`, `inherit`, `currentColor`). The actual conversion count may be lower. Phase 1 execution will produce the exact number.
- **Branch color contrast on light backgrounds**: 26 branch colors need individual testing against `#ffffff`. Some may need per-theme variants (darker shades for light backgrounds). This can only be determined empirically during Phase 5.
- **Modal z-index and theme inheritance**: Modals currently use hardcoded dark colors. The exact number of modal-specific color overrides needed will be determined during Phase 4.
