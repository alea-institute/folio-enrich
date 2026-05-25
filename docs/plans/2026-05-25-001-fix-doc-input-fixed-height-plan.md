---
title: Keep Document Input box at a fixed height (no auto-grow on prefill/paste)
type: fix
status: completed
date: 2026-05-25
---

# 🐛 Keep Document Input box at a fixed height (no auto-grow on prefill/paste)

Originated from `/ce-brainstorm` (2026-05-25, dialogue — no doc; went straight to plan per Phase 0).
**Locked decisions:** fixed default ≈120px (current empty-state height); content beyond it scrolls
inside; users still expand manually via the **existing** drag handle; a manually-dragged height
persisting is acceptable.

## Problem

In the Document Input panel (`frontend/index.html`), clicking a prefilled workflow chip (Litigation,
M&A, Motion, …) or pasting/loading text makes the `#docInput` textarea **auto-grow to fit the content**,
pushing the Rich Enrichment / Quick Start buttons down the page. The box should stay a fixed, calm size
by default and only change height when the user drags the resize handle.

## Root cause (verified)

- `frontend/index.html:1267-1281` — the **generic `textarea`** rule sets
  `min-height:120px; max-height:60vh; resize:vertical;` and **`field-sizing: content;`** (line 1280).
  `field-sizing: content` is what auto-sizes the box to its content (between 120px and 60vh). This is
  the driver on modern browsers (Chrome).
- `frontend/index.html:11320-11335` — a JS **fallback** IIFE attaches an `input` auto-resize **only when
  `field-sizing` is unsupported**, exposing `ta._autoResize`. It's invoked at three value-setting sites:
  cache-restore (`:4224`), `loadSample()` (`:10959`), `clearAll()` (`:10967`).

## Proposed change (target `#docInput` only)

> ⚠ The `textarea` rule is **shared**. Other textareas intentionally auto-grow and MUST be left alone:
> tooltip-note (`:2146-2156`, own `field-sizing:content`+`resize:none`), feedback (`:9445`),
> detail-notes (`:1108-1113`). Scope every change to the `#docInput` id — do **not** edit the generic rule.

**1. CSS — add a `#docInput` override** (e.g. just after the generic `textarea` rule):

```css
/* frontend/index.html — Document Input stays a fixed size; manual drag still works */
#docInput {
  field-sizing: fixed;   /* stop content-driven auto-grow (overrides the shared rule) */
  height: 120px;         /* explicit default; inherited min-height:120px also enforces this */
  overflow-y: auto;      /* long content scrolls inside the box */
}
```
- Inherited `resize: vertical` → the **existing drag handle stays**.
- Inherited `max-height: 60vh` → manual drag is still capped at 60vh (fine); `min-height:120px` → can't drag below the default.

**2. JS — remove the auto-resize fallback** for `#docInput` (`:11320-11335`): delete the IIFE so old
browsers also keep a fixed height. With it gone, `ta._autoResize` is never defined, so the three guarded
calls become no-ops — remove them too for tidiness:
- `:4224` `if (ta._autoResize) ta._autoResize();` (cache restore)
- `:10959` `if (ta._autoResize) ta._autoResize();` (`loadSample`)
- `:10967` `if (ta._autoResize) ta._autoResize();` (`clearAll`)

## Acceptance Criteria

- [x] Clicking any prefilled chip (Litigation, M&A, Motion, Order, …) does **not** change the box height; buttons below don't shift. *(loadSample → 120px; screenshot confirms buttons unshifted.)*
- [x] Pasting / typing a long document keeps the box at ~120px; overflow **scrolls inside** the box. *(long paste → height 120, scrollHeight 2104, scrolls:true.)*
- [x] Generating a synthetic doc and cache restore on reload also keep ~120px. *(all `_autoResize` calls removed; `field-sizing:fixed` applies to every value-set path.)*
- [x] The **drag handle still works** — computed `resize: vertical` retained (120px → ~60vh).
- [x] Empty state looks unchanged (~120px, placeholder visible). *(heightEmpty = 120.)*
- [x] **No regression** to other textareas — change is `#docInput`-scoped + a docInput-only IIFE removal; shared `textarea` rule untouched.
- [x] Verified in Chrome DevTools at http://localhost:8731.

## Notes / minor open item

- **Clear button height:** with the fix, a manually-dragged height **persists** through prefills and Clear
  (inline drag height isn't reset). Brainstorm decision = acceptable. *Optional* nicety (not required):
  have `clearAll()` also clear any inline `height` so Clear returns the box to the 120px default.
- No backend, dependency, security, or data impact — pure frontend CSS/JS. No external research needed.

## Sources

- Origin: `/ce-brainstorm` dialogue 2026-05-25 (decisions above).
- Code: generic textarea rule `frontend/index.html:1267-1281`; auto-resize IIFE `:11320-11335`;
  `_autoResize` call sites `:4224`, `:10959`, `:10967`; value-setting paths `loadSample` `:10954`,
  `clearAll` `:10962`, synthetic generate `:10916`, cache restore `:4221`.
