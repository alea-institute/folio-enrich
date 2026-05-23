---
phase: 03-consolidated-system-status-chip
plan: 04
subsystem: frontend-system-chip
tags: [status-chip, checkhealth, disclosure, accessibility, wcag, status-01, status-03, status-04, status-05, status-06, status-07, uat]
requires:
  - "frontend/index.html #chipSystem + #systemStatusPopover + inline rollup copy (Wave 2, plan 03)"
  - "scripts/system-rollup.mjs (rollup contract, Wave 1)"
  - "scripts/contrast-audit.mjs (STATUS-05 icon gate, Wave 1)"
provides:
  - "checkHealth() → normalizeSubsystems → computeRollup → renderSystemChip/renderPopoverRows (live one-chip rollup)"
  - "Accessible disclosure: openSystemPopover/closeSystemPopover/toggleSystemPopover (D-04 ARIA + focus management)"
  - "Flat status dots (UAT-revised D-09): theme-aware --status-dot-* tokens, all 6px to match the LLM/layer .chip-dot"
affects:
  - "Phase 03 complete — consolidated System status chip is live and metric-complete"
tech-stack:
  added: []
  patterns:
    - "WAI-ARIA non-modal disclosure: aria-expanded toggle, click+Enter/Space open, Escape/outside-click/re-activation close, focus-in-on-open + restore-on-close, no focus trap"
    - "Deferred (setTimeout 0) outside-click listener so the opening click does not self-close (Pitfall 5)"
    - "Idempotent in-place row updates via data-glyph (no DOM teardown / no focus theft while open — D-03)"
    - "All backend strings rendered via textContent (DOM-XSS mitigation, T-03-04)"
    - "Flat filled status dots clearing WCAG 3:1 via deeper light-theme shades (1.4.11) + text labels (1.4.1)"
key-files:
  created: []
  modified:
    - "frontend/index.html"
    - "scripts/contrast-audit.mjs"
    - "scripts/contrast-audit.test.mjs"
decisions:
  - "D-09 REVISED at UAT: the original three distinct stroked silhouettes (check/triangle/cross with a --text ring) read as heavy 'success badges' clashing with the simple LLM/layer .chip-dot circles. Replaced with flat filled dots matching those circles, per direct user UAT feedback."
  - "WCAG preserved without the shape glyphs: light themes use deeper --status-dot-* shades (green-700 #15803d / orange-700 #b45309 / red-600 #dc2626) so the solid dot clears 3:1 (1.4.11); dark/mixed keep the bright 500s. Status is never color-only — every popover row carries text (Running/Standby/error) and the chip names the failing subsystem (\"System: spaCy +1\"), satisfying 1.4.1."
  - "Contrast audit now measures the dot FILL (the rendered graphical object) over dark/light/mixed × surface2/surface3; NOT 'mixed-light', because the System chip/popover render on the mixed theme's dark chrome (header + surface3=gray-700), never the light content panels."
  - "All header status/layer dots normalized to 6px (System chip + popover dots were 9px/10.5px, layer dots 7px) to match the 6px amber LLM dot — second UAT pass."
  - "STATUS-07 resolved structurally: the 4→1 chip reduction frees header width — measured statusBar right edge 385px vs layerToggleBar left edge 401px (16px gap) at 1221px desktop with a document loaded; no flex-wrap fallback needed."
metrics:
  duration: "~30 min (incl. 2 UAT fix iterations)"
  completed: "2026-05-22"
  tasks: 3
  files: 3
---

# Phase 03 Plan 04: Wire System Chip to Live Health + Accessible Disclosure Summary

Wired the consolidated System chip to live `/health/detail` data and shipped the accessible disclosure behavior, then refined the status-indicator visual through two rounds of UAT against the deployed DEV environment. `checkHealth()` now drives one chip + four live rows from the rollup functions; the `d.llm`/Ollama branch, `setChip()`, and the FOLIO completed-update toast are byte-for-byte intact (STATUS-06). All seven STATUS requirements were verified live across Dark/Light/Mixed via Chrome DevTools.

## What Was Built

- **Task 1 (`b4143eb`)** — Refactored `checkHealth()` so the four subsystem branches feed `normalizeSubsystems → computeRollup → renderSystemChip / renderPopoverRows`. Backend-down routes through the same red rollup path (fallback preserved). `renderSystemChip`/`renderPopoverRows` update the chip glyph/label and the four rows **in place** via `textContent` (DOM-XSS mitigated, T-03-04); only the static `STATUS_ICON_SVG` constants use `innerHTML`. Idempotent glyph swap (`data-glyph`) avoids DOM teardown/focus theft on live polls (D-03). The `d.llm`/`updateOllamaChip()` branch, `setChip()`, and `_lastFolioUpdateAt` FOLIO toast left untouched (STATUS-06).
- **Task 2 (`97ca89f`)** — `openSystemPopover`/`closeSystemPopover`/`toggleSystemPopover` implement the D-04 disclosure contract: open via click + Enter/Space (reuses the existing `.status-chip.clickable` keydown handler — no duplicate listener); close on Escape (new branch ahead of the modal checks), outside-click (deferred `setTimeout(0)` listener, Pitfall 5), and re-activation; focus moves into the popover region on open and restores to `#chipSystem` on close; no focus trap (non-modal).
- **Task 3 — Manual UAT (gate passed)** — Verified live across Dark/Light/Mixed at `http://localhost:8731/` (same-origin backend) via Chrome DevTools MCP. All 7 STATUS requirements confirmed (table below). Two visual refinements were applied from UAT feedback (see UAT Iterations).

## UAT Iterations (Task 3)

1. **Flat status dots — D-09 revision (`2320770`).** The original check/triangle/cross glyphs with a `--text` stroke ring read as heavy "success badges" next to the flat amber LLM dot and blue/purple layer dots. Replaced all three tier glyphs with flat filled circles matching the `.chip-dot` style. To keep WCAG AA without the shape silhouettes, introduced theme-aware `--status-dot-*` tokens: light themes use deeper shades (green-700 `#15803d` 4.32:1 / orange-700 `#b45309` 4.33:1 / red-600 `#dc2626` 4.16:1 on `--surface2`) so the solid fill clears 3:1 (1.4.11); dark/mixed keep the bright 500s. The contrast audit was updated to measure the dot fill (not the `--text` stroke), and its tests now pin the deeper shades pass and that the lighter green-600/orange-600 would fail. Status remains non-color-only via row text + chip label (1.4.1).
2. **6px dot normalization (`e565126`).** The green System dots (chip 9px, popover rows 10.5px) and blue/purple layer dots (7px) were larger than the 6px amber LLM dot. Shrank the System icon SVGs to 8px (circle `r=6` in the 16-unit viewBox renders a 6px dot) and the layer `.chip-dot` to 6px so every header status/layer dot is a uniform 6px.

## STATUS Requirement Verification (live, Chrome DevTools)

| Req | What was verified | Result |
|-----|-------------------|--------|
| STATUS-01 | One "System" chip + four-row anchored popover; all metrics present | PASS |
| STATUS-02 | Quiet-green at rest: chip reads "System" (green), `aria-expanded=false`; FOLIO/Embedding "Standby" stay green | PASS |
| STATUS-03 | Worst-of-four rollup: `spacy.status=error` → "System: spaCy"; +2nd failure → "System: Embedding +1" (mocked /health/detail) | PASS |
| STATUS-04 | Popover preserves all metrics (18,326 concepts / 68,412 labels / vectors indexed / spaCy 3.8.x / EntityRuler ready); FOLIO "Manage" opens existing modal | PASS |
| STATUS-05 | Keyboard open (click + Enter/Space), Escape/outside-click/re-activation close, focus-in-on-open + restore-to-chip; dots clear 3:1; status conveyed by text too | PASS |
| STATUS-06 | LLM/Ollama chip separate and untouched; `setChip`/`updateOllamaChip()` byte-for-byte intact | PASS |
| STATUS-07 | After a document loads, `#statusBar` (right 385px) and `#layerToggleBar` (left 401px) have a 16px gap at 1221px desktop — no overlap; no flex-wrap fallback needed (D-12) | PASS |

## Deviations from Plan

### [UAT feedback] D-09 status-icon design revised from shape glyphs to flat color dots

- **Found during:** Task 3 manual UAT on DEV.
- **Issue:** The locked D-09 decision specified three distinct stroked silhouettes (check/triangle/cross) so status is distinguishable by FORM, not color alone. In practice the stroked glyphs read as heavy badges visually inconsistent with the adjacent flat LLM/layer dots; the product owner directed they be made simple colored dots like the amber/blue circles.
- **Resolution:** Replaced the glyphs with flat filled dots. WCAG 1.4.11 (3:1 graphical-object contrast) is preserved by using deeper status-dot shades on light surfaces (verified by the audit + unit tests). WCAG 1.4.1 (use of color) is preserved because every popover row carries a status word/text and the collapsed chip names the failing subsystem in text — color is redundant, not the sole signal. The colorblind-distinction goal of D-09 is now served by text rather than icon shape.
- **Follow-up available (not requested):** a distinct shape (e.g. an `×`) could be reintroduced for the red/error tier only while keeping healthy as a plain dot, if a stronger at-a-glance degraded signal is later desired.
- **Files modified:** `frontend/index.html`, `scripts/contrast-audit.mjs`, `scripts/contrast-audit.test.mjs`.
- **Commits:** `2320770`, `e565126`.

## Verification Results

- `node --test 'scripts/**/*.test.mjs'` → 50 tests, 50 pass, 0 fail (system-rollup 23, contrast-audit incl. revised STATUS-05 assertions, flags regression).
- `node scripts/contrast-audit.mjs` → `290 pairs checked, 0 failures`; `Status-icon (3:1 graphical-object) checks: 18, 0 fail` (3 themes × 2 surfaces × 3 status-dot tokens), exit 0.
- Live Chrome DevTools UAT at `http://localhost:8731/`: all 7 STATUS requirements PASS across Dark/Light/Mixed; degraded states exercised by mocking `/health/detail`; live recovery (degraded→healthy) confirmed in place (D-03).
- All header status/layer dots measured 6×6px (amber LLM, blue layer, green chip, green popover) after normalization.
- STATUS-06 boundary: `#chipLLM` markup and the `d.llm`/`updateOllamaChip()`/`setChip()` code paths unchanged in the diff.

## Note on the dev API origin

`API = window.location.origin`. The frontend is production-equivalent only when served same-origin with the backend (`http://localhost:8731/`, which FastAPI serves). Opening the standalone dev static server (`:8732`) makes `/health` 404 and the chip correctly shows its backend-down fallback ("System: Backend +3") — this is correct behavior, not a defect. UAT was therefore performed at `:8731`.

## Threat Flags

None new. Backend strings render via `textContent` (T-03-04 mitigated). No package installs (single-file vanilla JS). The disclosure adds no untrusted-input rendering.

## Tasks Completed

| Task | Name | Commit(s) | Files |
|------|------|-----------|-------|
| 1 | Refactor checkHealth() → rollup → render chip + four live rows | b4143eb | frontend/index.html |
| 2 | Accessible disclosure open/close + focus management (D-04) | 97ca89f | frontend/index.html |
| 3 | Manual UAT (Dark/Light/Mixed) + 2 visual refinements | 2320770, e565126 | frontend/index.html, scripts/contrast-audit.mjs, scripts/contrast-audit.test.mjs |

## Self-Check: PASSED

- FOUND: .planning/phases/03-consolidated-system-status-chip/03-04-SUMMARY.md
- FOUND commit b4143eb (Task 1), 97ca89f (Task 2)
- FOUND commit 2320770 (UAT flat dots), e565126 (UAT dot size)
- All 7 STATUS requirements verified live; 50/50 tests pass; audit 0 failures
- Only untracked file is the regenerable 03-AUDIT-REPORT.md (intentionally not tracked, per 02/03 precedent)
