# Phase 1: CSS Variable Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 01-css-variable-foundation
**Areas discussed:** Token naming strategy, Light theme palette, Branch color adaptation, Migration approach

---

## Token Naming Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Two-layer (Recommended) | Palette primitives (--gray-900) + semantic tokens (--btn-bg). Themes swap semantic layer. Industry standard. | ✓ |
| Flat semantic only | Keep current flat style, just add more. Simpler but themes redefine every value. | |
| Component-scoped | Per-component variables (--tooltip-bg, --modal-border). Most specific but many variables. | |

**User's choice:** Two-layer token system
**Notes:** None — clear pick

### Branch Variable Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Kebab-case branch names (Recommended) | --branch-litigation, --branch-corporate-law. Readable, matches FOLIO. | ✓ |
| Numbered (branch-01 through branch-26) | Compact but loses semantic meaning. | |
| You decide | Claude picks. | |

**User's choice:** Kebab-case branch names
**Notes:** None

---

## Light Theme Palette

| Option | Description | Selected |
|--------|-------------|----------|
| Cool gray (Recommended) | White with blue-gray undertones. Professional, matches dark theme personality. | ✓ |
| Warm neutral | Soft cream/warm gray. Document-like, reading feel. | |
| Pure white + neutral gray | Clean white, true gray. No color cast. | |

**User's choice:** Cool gray
**Notes:** None

### Light Mode Accent Color

| Option | Description | Selected |
|--------|-------------|----------|
| Darker blue (Recommended) | Shift to #2d5ee0 for WCAG compliance on white. Same hue family. | ✓ |
| Same blue everywhere | Keep #4a7cff, constrain usage to dark-enough backgrounds. | |
| You decide | Claude picks. | |

**User's choice:** Darker blue
**Notes:** #4a7cff fails WCAG on white (3.2:1), #2d5ee0 passes (5.1:1)

---

## Branch Color Adaptation

| Option | Description | Selected |
|--------|-------------|----------|
| Same hues, lower opacity (Recommended) | Keep same hue, reduce opacity to 8-12% on light backgrounds. | |
| Theme-specific branch colors | Entirely different values per theme. 26 × 3 = 78 values. Full control. | ✓ |
| Opacity via CSS variable | Single hue + --branch-opacity variable per theme. Minimal CSS. | |

**User's choice:** Theme-specific branch colors
**Notes:** User chose full per-theme control over the simpler opacity-only approach

### Branch Value Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Claude's discretion (Recommended) | Claude picks light-mode values maintaining hue identity + WCAG compliance. | ✓ |
| I'll review the palette | Claude proposes all 26 for approval before implementing. | |

**User's choice:** Claude's discretion
**Notes:** User will review in final result, not upfront

---

## Migration Approach

| Option | Description | Selected |
|--------|-------------|----------|
| All at once (Recommended) | Single pass: audit, define variables, replace all 876 occurrences. One commit. | ✓ |
| By component group | Convert in batches. Multiple smaller commits. | |
| You decide | Claude picks. | |

**User's choice:** All at once
**Notes:** No intermediate broken states preferred

### Verification Method

| Option | Description | Selected |
|--------|-------------|----------|
| Screenshot comparison (Recommended) | Before/after screenshots via Chrome DevTools MCP. Catches subtle shifts. | ✓ |
| Grep-only verification | Just verify zero hardcoded colors remain + app loads. | |
| You decide | Claude picks. | |

**User's choice:** Screenshot comparison
**Notes:** Backward compatibility (Mixed mode identical to current) is critical

---

## Claude's Discretion

- Light-mode branch color values — Claude picks WCAG-compliant values per theme
- Semantic token naming granularity for component-specific colors

## Deferred Ideas

None
