# Phase 2: Theme Switching & JS Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 02-theme-switching-js-integration
**Areas discussed:** Toggle UI design, JS color migration strategy, Graph/canvas theming, Settings modal integration

---

## Toggle UI Design

| Option | Description | Selected |
|--------|-------------|----------|
| Icon cycle button (Recommended) | Single button cycling Dark→Light→Mixed. Moon/sun/split icons. Tooltip. | ✓ |
| Three-segment toggle | [D|L|M] grouped buttons. More explicit, more space. | |
| Dropdown selector | Click-to-reveal dropdown. Compact but extra click. | |

**User's choice:** Icon cycle button
**Notes:** None

---

## JS Color Migration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| getComputedStyle helper (Recommended) | `getThemeColor(varName)` reads CSS vars at runtime. Covers all contexts. | ✓ |
| Inline var() in templates | Use var() directly in style strings. Only works for inline styles. | |

**User's choice:** getComputedStyle helper

### BRANCH_COLORS Elimination

| Option | Description | Selected |
|--------|-------------|----------|
| Eliminate entirely (Recommended) | Delete object, use getThemeColor('branch-*'). Single source of truth. | ✓ |
| Keep as cache | Populate from CSS vars on load, refresh on theme switch. | |

**User's choice:** Eliminate entirely
**Notes:** None

---

## Graph/Canvas Theming

| Option | Description | Selected |
|--------|-------------|----------|
| Always dark canvas (Recommended) | Graph stays dark in all themes. Simpler. | |
| Theme-adaptive canvas | Canvas re-renders with theme-appropriate colors. | ✓ |

**User's choice:** Theme-adaptive canvas

### Re-render Timing

| Option | Description | Selected |
|--------|-------------|----------|
| Re-render on theme switch (Recommended) | MutationObserver watches data-theme changes. Seamless. | ✓ |
| Re-render on open only | Read colors when modal opens. Stale if theme changes while open. | |

**User's choice:** Re-render on theme switch
**Notes:** None

---

## Settings Modal Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Visual swatches (Recommended) | Three clickable mini-previews (dark/light/mixed rectangles). Active gets border. | ✓ |
| Radio buttons | Standard radio group. Less visual. | |
| Dropdown | Select dropdown. Most compact, least discoverable. | |

**User's choice:** Visual swatches
**Notes:** None

---

## Claude's Discretion

- Flash-prevention inline script details
- color-scheme CSS property values
- Toggle button icon characters/SVGs
- Settings swatch styling

## Deferred Ideas

None
