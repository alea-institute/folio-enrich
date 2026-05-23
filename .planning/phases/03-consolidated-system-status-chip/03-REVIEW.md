---
phase: 03-consolidated-system-status-chip
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - frontend/index.html
  - scripts/system-rollup.mjs
  - scripts/system-rollup.test.mjs
  - scripts/contrast-audit.mjs
  - scripts/contrast-audit.test.mjs
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: resolved
resolution:
  warnings_fixed: "WR-01, WR-02, WR-03, WR-04 — commit 3ce8c19"
  info_deferred: "5 info items left as documented (incl. the intentional flat-dot/color-only D-09 UAT revision); no behavior impact"
---

> **Resolution (2026-05-22, commit `3ce8c19`):** All 4 warnings fixed and verified live via Chrome DevTools.
> - **WR-01** — `closeSystemPopover(restoreFocus=true)`; outside-click passes `false` so focus stays where the user clicked (WCAG 2.4.3); Escape/re-activation still restore to the chip.
> - **WR-02/WR-03** — "Manage FOLIO" now closes the popover before opening the modal, so it no longer sits open behind the modal and a single Escape dismisses the modal.
> - **WR-04** — popover left edge anchored to the chip in `openSystemPopover()` + `max-width: calc(100vw - 16px)` so it cannot misalign or overflow a narrow viewport.
> - **Info (5)** — left as documented; the "icon is color-only" item is the intentional flat-dot D-09 UAT revision (WCAG 1.4.11 via deeper shades, 1.4.1 via text labels).

# Phase 3: Code Review Report

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 03 consolidated System status chip: the pure rollup module
(`scripts/system-rollup.mjs`), its inline byte-identical copy in
`frontend/index.html`, the extended WCAG contrast audit
(`scripts/contrast-audit.mjs`), and the chip's `checkHealth()` wiring plus the
accessible disclosure (`renderSystemChip` / `renderPopoverRows` /
`openSystemPopover` / `closeSystemPopover`).

Verified facts:
- All 35 unit tests pass (`node --test scripts/system-rollup.test.mjs scripts/contrast-audit.test.mjs`).
- The inline rollup copy in `index.html` (lines 10497-10615) is byte-identical
  to `scripts/system-rollup.mjs` (lines 18-137) after stripping the `export`
  keyword, as the contract requires.
- No duplicate top-level identifier declarations were introduced (`TIER_RANK`,
  `computeRollup`, `chipLabel`, `fmt`, `normalizeSubsystems`, `STATUS_ICON_SVG`
  each declared once). `init()` at line 10783 runs after all `const`
  declarations, so there is no temporal-dead-zone hazard despite `checkHealth`
  referencing the rollup helpers from line ~4266.
- The DOM-XSS discipline is sound: all backend strings reach the DOM via
  `textContent`; `innerHTML` is only assigned the static `STATUS_ICON_SVG`
  constant.

No security vulnerabilities or crash/data-loss bugs were found. The defects
below are interaction/accessibility correctness issues and quality problems.

## Warnings

### WR-01: Outside-click close steals focus back to the chip

**File:** `frontend/index.html:4231-4233` (closeSystemPopover)
**Issue:** `closeSystemPopover()` unconditionally calls `chip.focus()` at the
end, but it is invoked for *all* close paths — Escape, re-activation, AND the
deferred outside-click handler. When a user dismisses the popover by clicking
somewhere else on the page (e.g., into the document textarea or another chip),
focus is yanked back to the System chip away from where the user just clicked.
Focus restoration is correct for keyboard-initiated dismissal (Escape /
re-activation) but is a focus-stealing defect for pointer-initiated outside
clicks (WCAG 2.4.3 focus order / general UX).
**Fix:** Restore focus only when the close was keyboard-initiated. Pass an
intent flag, e.g.:
```js
function closeSystemPopover(restoreFocus = true) {
  // ... existing hide + listener teardown ...
  if (restoreFocus && chip) chip.focus();
}
// Escape handler + toggle: closeSystemPopover()  // restore
// outside-click handler:    closeSystemPopover(false)  // do not steal focus
```

### WR-02: "Manage FOLIO" leaves the popover open behind the modal

**File:** `frontend/index.html:3088-3089` (sysRowFolioManage button) and `4226`
(outside-click containment check)
**Issue:** The FOLIO "Manage" button lives inside the popover and fires
`openFolioModal()`. Because the click target is inside `pop`, the outside-click
handler's `pop.contains(e.target)` guard skips `closeSystemPopover()`, so the
FOLIO modal opens *while the System popover stays open*. The popover (z-index
100) and the modal then coexist, and pressing Escape (see WR-03) closes the
popover first rather than the modal the user is looking at. The disclosure
should collapse when its action navigates the user elsewhere.
**Fix:** Close the popover in the Manage handler before opening the modal:
```html
<button ... onclick="closeSystemPopover(false); openFolioModal()">Manage FOLIO</button>
```
or wrap in a small function that closes the popover then opens the modal.

### WR-03: Escape requires two presses when popover and a modal are both open

**File:** `frontend/index.html:10727-10730`
**Issue:** The Escape handler returns early after closing the System popover:
```js
if (_systemPopoverOpen) { closeSystemPopover(); return; }
```
Combined with WR-02 (the popover can remain open underneath the FOLIO modal),
a user who opens the modal via "Manage FOLIO" and then presses Escape closes
the *popover* (invisible behind the modal) and must press Escape a second time
to dismiss the modal they are actually looking at. The early `return` makes the
first keystroke appear to do nothing.
**Fix:** Fixing WR-02 (closing the popover when Manage is clicked) removes the
overlap so this ordering is no longer reachable. If the dual-open state can
arise by other paths, prefer closing the topmost-visible layer (modal) first.

### WR-04: Anchored popover has no horizontal anchor and may misalign with the chip

**File:** `frontend/index.html:1331-1341` (.system-popover)
**Issue:** `.system-popover` uses `position: fixed; top: 44px` with no `left`/
`right`/`inset`. For a fixed-positioned *sibling element* (not a pseudo-element
like the tooltip it claims to mirror), `left:auto` resolves to the element's
static in-flow position. The popover is the second child of the flex
`.status-bar`, so its static x-position depends on the System chip's width and
the surrounding flex layout — it is not guaranteed to sit directly beneath the
System chip, and on narrow viewports the 240px-min panel can overflow the
viewport edge with no clamping. The `.status-chip[data-tooltip]` pattern it
cites works because a `::after` pseudo-element is positioned relative to its
generating box; a real sibling element does not get that anchoring for free.
**Fix:** Anchor explicitly to the chip — e.g. set `left` from JS in
`openSystemPopover()` using `chip.getBoundingClientRect()`, or wrap chip +
popover in a `position: relative` container and use `position: absolute; left: 0`.
Verify placement visually in dark/light/mixed themes and at a narrow width.

## Info

### IN-01: `statusWord` is computed for every row but never rendered

**File:** `frontend/index.html:10548-10609` (normalizeSubsystems) and
`4194-4204` (renderPopoverRows)
**Issue:** Every row object carries a `statusWord` ("Running" / "Ready" /
"Standby" / "Error" / "Offline"), and the row-shape comment cites it as the
STATUS-05 "text, not color alone" signal. But `renderPopoverRows` only writes
`metric` and `annotation` — `statusWord` is never displayed. WCAG 1.4.1 is
still satisfied because `metric` carries text, but `statusWord` is dead data in
the render path and the comment is misleading about which field conveys status.
**Fix:** Either render `statusWord` in a row element, or update the comment to
state that `metric` (not `statusWord`) is the displayed status text. Note the
field cannot simply be deleted without breaking the byte-identical contract with
`system-rollup.mjs` and its tests.

### IN-02: All three status glyphs are visually identical, so the icon is color-only

**File:** `frontend/index.html:10646-10650` (STATUS_ICON_SVG)
**Issue:** `healthy`, `warning`, and `error` map to byte-identical SVG (the same
`<circle r="6">`); only the fill color differs via `.is-green/.is-orange/.is-red`.
The render comment claims "the glyph silhouette ... carries the signal
(STATUS-05)", but the silhouette is identical across tiers — only color
differentiates the icon itself. The component as a whole still meets WCAG 1.4.1
via the row `metric` text and the chip label ("System: spaCy +1"), so this is
not a blocker, but the silhouette-carries-signal comment is inaccurate.
**Fix:** Either correct the comment to state that color (icon) + text (row/label)
together satisfy 1.4.1, or differentiate the glyphs (e.g., distinct shapes per
tier) if shape-level redundancy is actually desired.

### IN-03: `_setStatusIcon` rewrites identical innerHTML on every tier change

**File:** `frontend/index.html:4169-4172`
**Issue:** The `slot.dataset.glyph !== glyph` guard keys on the glyph *name*
(healthy/warning/error), but all three names produce identical SVG markup
(IN-02). So any green↔orange↔red transition triggers an `innerHTML` rewrite that
replaces the circle with a byte-identical circle. Harmless (no untrusted input,
no focus inside the SVG), but the idempotency optimization the comment advertises
does not actually avoid the rewrite across tier changes.
**Fix:** Since the markup is constant, the fill class alone conveys the tier;
the `innerHTML` assignment only needs to run once (when the slot is empty).
Guard on `if (!slot.dataset.glyph)` for the initial paint, or accept the no-op
rewrite and drop the misleading comment.

### IN-04: `hexToRgb` silently pads/truncates malformed hex instead of failing

**File:** `scripts/contrast-audit.mjs:12-22`
**Issue:** For inputs that are neither 3 nor 6 hex chars, `h.padEnd(6,'0').slice(0,6)`
silently coerces (e.g., a 4-char string becomes a different color, non-hex chars
yield `NaN` channels). `resolveVariable` currently only returns `#`-prefixed
values so malformed input is unlikely in practice, but the function would mask
rather than surface a bad token if the upstream guard ever loosens. Dev-tool
scope, low severity.
**Fix:** Validate with `/^#?[0-9a-f]{3}([0-9a-f]{3})?$/i` and throw (or return
null and skip) on mismatch so a malformed CSS token is caught rather than
audited as a wrong color.

### IN-05: Branch-tint blend fraction is a hardcoded magic number

**File:** `scripts/contrast-audit.mjs:329`
**Issue:** `mixColors(branchHex, bgHex, 0.12)` hardcodes the 12% tint. If the
actual CSS branch-tint opacity ever changes, the audit silently measures the
wrong effective background and could pass/fail incorrectly. Documented in the
test comment but still a free-floating constant in the audit loop.
**Fix:** Hoist to a named constant (e.g. `const BRANCH_TINT_FRACTION = 0.12;`)
with a comment pointing at the CSS declaration it must track, so the coupling is
explicit.

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
