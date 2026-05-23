---
quick_id: 260522-uot
description: Consolidate Nouns/Verbs/Individuals layer toggles under one Annotations disclosure chip; keep spaCy Parts of Speech overlay separate
date: 2026-05-23
status: complete
tags: [layer-toggles, disclosure, popover, accessibility, header-ux]
key-files:
  created: []
  modified:
    - frontend/index.html
commits:
  - "166b115 — Task 1: markup + CSS (Annotations chip + popover, three rows)"
  - "9369907 — Task 2: disclosure JS (open/close/toggle, keyboard, Escape, outside-click) + active-count summary"
---

# Quick Task 260522-uot: Consolidate layer toggles into an "Annotations" chip

Collapsed the three standalone header layer toggles (Nouns / Verbs / Individuals) into one
"Annotations ▾" click-to-expand disclosure chip, mirroring the Phase 03 System chip pattern
verbatim. The spaCy "Parts of Speech" overlay chip + `#posLegend` were left as their own
separate control (per the user's locked IA choice — these are distinct annotation layers, not
grammatical parts of speech).

## Locked decision (user UAT choice)

Of three options presented, the user chose: **group only Nouns/Verbs/Individuals under one
"Annotations" umbrella chip; keep "Parts of Speech" separate.** Header result:
`[System] [LLM] [Annotations ▾] [Parts of Speech]`. Rationale: "Nouns"/"Verbs" are the app's
friendly names for FOLIO Classes/Properties, not grammatical POS, and "Parts of Speech" already
means a distinct spaCy overlay — so folding them under that label would conflate three layers.

## What was built

- **Task 1 (`166b115`)** — Replaced the three standalone `.layer-chip` spans with a
  `#chipAnnotations` disclosure chip (`status-chip clickable`, `aria-haspopup`/`aria-expanded`/
  `aria-controls`, a `▾` caret that rotates 180° when open) plus an anchored `#annotationsPopover`
  holding the three rows. The rows remain `.layer-chip[data-layer="concepts|properties|individuals"]`
  with their original `onclick="toggleLayer(...)"`, so `toggleLayer()` semantics and the
  `_syncViewMode`/`_restoreViewPrefs` `querySelectorAll('.layer-chip[data-layer]')` sync keep
  working untouched. The divider, `data-layer="pos"` chip, and `#posLegend` are out of scope.
- **Task 2 (`9369907`)** — Wired `openAnnotationsPopover`/`closeAnnotationsPopover(restoreFocus)`/
  `toggleAnnotationsPopover` mirroring the System chip disclosure, including the WR-01 fix
  (outside-click passes `restoreFocus=false` so focus stays where the user clicked) and the WR-04
  fix (left-anchor to the chip + `max-width: calc(100vw - 16px)`). Added `renderAnnotationsSummary()`
  (called at load and at the end of `toggleLayer`) that shows "Annotations" when all three are on or
  "Annotations (N/3)" when some are off, via `textContent` only. It ignores `pos`.

## UAT (verified live via Chrome DevTools at localhost:8731, document loaded)

- Header reads `[System] [LLM] [Annotations ▾] [Parts of Speech]`; no standalone Nouns/Verbs/Individuals chips remain.
- Popover opens anchored under the chip with three rows (colored dot + name + active state).
- Toggling "Nouns" off hid all 17 `.annotation-span` nodes; popover stayed open; label updated "Annotations" → "Annotations (2/3)" → back. In-place, no DOM teardown, no focus theft (D-03 parity).
- Keyboard: Enter/Space open; Escape closes and restores focus to the chip; `:focus-visible` rings present.
- Outside-click closes without stealing focus.
- "Parts of Speech" still toggles the spaCy overlay + legend, independent of the popover.

## Note (not a regression)

Nouns/Verbs/Individuals reset to ON on every page reload — this is **pre-existing intentional
behavior**: `_restoreViewPrefs` (frontend/index.html ~7267-7270, untouched by this task)
force-enables `concepts`/`properties`/`individuals` as "core layers always active on load" and
re-saves localStorage. Only the POS layer's state persists across reloads. Within a session,
toggles work and persist to `localStorage('activeLayers')`. Making the three persist across
reloads would be a separate, out-of-scope change.

## Scope / threats

- frontend/index.html only. No backend changes, no new dependencies (single-file vanilla JS).
- No untrusted input rendered (summary uses `textContent`).
