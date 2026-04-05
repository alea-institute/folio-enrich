# Phase 3: Accessibility & Component Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-05
**Phase:** 03-accessibility-component-polish
**Areas discussed:** Contrast audit approach, Branch color legibility, text-dim safety margin, Modal/tooltip edge cases

---

## Contrast Audit Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Automated script (Recommended) | Node.js script computes all token pair ratios. | |
| Manual Chrome DevTools | Use built-in contrast checker per element. | |
| Hybrid — script + manual | Script for tokens, manual for rendered mixed backgrounds. | ✓ |

**User's choice:** Hybrid

### Fix Direction

| Option | Description | Selected |
|--------|-------------|----------|
| Adjust foreground text (Recommended) | Darken text, backgrounds stay stable. | ✓ |
| Adjust background | Lighten/darken backgrounds. Risky cascade. | |
| Case-by-case | Claude picks per failure. | |

**User's choice:** Adjust foreground text

---

## Branch Color Legibility

| Option | Description | Selected |
|--------|-------------|----------|
| Adjust text color per tint (Recommended) | Darken text on failing branch tints. | ✓ |
| Lower opacity for failing branches | Reduce tint percentage. | |
| Global tint reduction per theme | Lower all tints in light mode. | |
| You decide | Claude picks. | |

**User's choice:** Adjust text color per tint

---

## text-dim Safety Margin

| Option | Description | Selected |
|--------|-------------|----------|
| 4.5 min, aim 5.5:1+ (Recommended) | 1.0 margin above AA. | ✓ |
| Strict AAA (7.0:1) | Maximally accessible. | |
| AA minimum (4.5:1) | Just pass, no margin. | |
| You decide | Claude picks. | |

**User's choice:** 4.5:1 minimum, aim for 5.5:1+

### Large Text Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Large-text threshold for headings (Recommended) | 3:1 for ≥18pt or ≥14pt bold. | ✓ |
| Body text threshold for everything | 4.5:1 everywhere. | |
| You decide | Claude picks per element. | |

**User's choice:** Use large-text threshold for headings

---

## Modal/Tooltip Edge Cases

| Option | Description | Selected |
|--------|-------------|----------|
| Verify + fix gaps (Recommended) | Audit per theme, fix what's broken. | ✓ |
| Full redesign | Redesign from scratch. | |
| You decide | Claude picks scope. | |

**User's choice:** Verify + fix gaps

---

## Claude's Discretion

- Exact adjusted values for failing colors
- Per-branch text overrides only where needed
- Whether to use color-mix() with --text or new --text-on-tint-* tokens

## Deferred Ideas

None
