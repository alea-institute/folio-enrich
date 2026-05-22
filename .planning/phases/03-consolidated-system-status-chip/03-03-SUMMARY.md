---
phase: 03-consolidated-system-status-chip
plan: 03
subsystem: frontend-system-chip
tags: [status-chip, popover, disclosure, accessibility, wcag, status-05, inline-svg]
requires:
  - "scripts/system-rollup.mjs (byte-identical inline source, Wave 1)"
  - "scripts/contrast-audit.mjs (STATUS-05 3:1 icon gate, Wave 1)"
  - "03-02-SUMMARY.md (the 8 Light-surface solid-fill FAILs requiring the --text stroke)"
provides:
  - "frontend/index.html #chipSystem disclosure chip + #systemStatusPopover (4 fixed-order rows)"
  - "STATUS_ICON_SVG (3 distinct stroked glyphs) + .is-green/.is-orange/.is-red fill state classes"
  - "Inline non-export rollup copy (TIER_RANK/computeRollup/chipLabel/normalizeSubsystems/fmt)"
  - "Per-row DOM contract (IDs/classes) for plan 04 in-place live updates"
affects:
  - "Wave 3 (plan 04): wires checkHealth() → normalizeSubsystems → render rows; adds disclosure open/close"
tech-stack:
  added: []
  patterns:
    - "WAI-ARIA disclosure (role=button, aria-expanded/controls/haspopup) on the existing .status-chip"
    - "Anchored position:fixed popover mirroring the .status-chip[data-tooltip] top:44px/z-index:100 pattern"
    - "Inline-SVG status glyphs stroked at var(--text) so the silhouette carries 3:1 in every theme (D-09/STATUS-05)"
    - "Byte-identical inline non-export module copy mirroring the Phase 02 flags.mjs precedent"
key-files:
  created: []
  modified:
    - "frontend/index.html"
    - "scripts/contrast-audit.mjs"
decisions:
  - "Audit verifies the icon's --text stroke (the rendered graphical-object boundary) on each surface, not the solid green/orange fill — because every shipped glyph strokes at --text and the color is only a secondary fill (the unit test still pins that solid fills FAIL, keeping the stroke mandatory)"
  - "Status-icon green/orange/red are secondary fills via .is-green/.is-orange/.is-red on an ancestor; default fill is none (stroke-only outline) so plan 04 toggles the state class"
  - "checkHealth() setChip('chipBackend'…) calls were left untouched (plan 04 scope); setChip has `if(!chip)return` so they no-op safely against the removed DOM in the interim"
metrics:
  duration: "~10 min"
  completed: "2026-05-22"
  tasks: 3
  files: 2
---

# Phase 03 Plan 03: Consolidated System Chip Markup + CSS + Inline Rollup Summary

Replaced the four passive Backend/FOLIO/Embedding/spaCy status chips with one accessible "System" disclosure chip plus a four-row anchored popover, authored three distinct inline-SVG status glyphs stroked at `--text` (so Light-theme green/orange clear the WCAG 1.4.11 3:1 floor that solid fills fail), and pasted the byte-identical non-export inline copy of the rollup module. This is the MARKUP + CSS + inline-module-copy wave; plan 04 wires `checkHealth()` and the disclosure behavior. The LLM chip and its `onLLMChipClick()` path are untouched (STATUS-06).

## What Was Built

- **Task 1 (`040228b`)** — In `#statusBar`, removed the four chip divs (`chipBackend`/`chipFolio`/`chipEmbedding`/`chipSpacy`) and their `*Detail` spans; inserted `#chipSystem` (a `role="button"` disclosure with `tabindex`, `aria-haspopup`, `aria-expanded="false"`, `aria-controls="systemStatusPopover"`, `aria-label`) carrying a `.chip-status-icon` slot + `.chip-label` "System"; inserted `#systemStatusPopover` (`role="region"`, `tabindex="-1"`, `hidden`) immediately after the chip with four always-present rows in fixed order Backend, FOLIO, Embedding, spaCy. The FOLIO row alone carries the re-homed `Manage FOLIO` action (`openFolioModal()`, `aria-label="Manage FOLIO ontology"`). `#chipLLM` left byte-for-byte intact.
- **Task 2 (`c255114`)** — Added `STATUS_ICON_SVG` (three distinct silhouettes: check-in-circle / exclamation-triangle / cross-in-circle, each `aria-hidden="true" focusable="false"`) and the `.system-chip` / `.chip-status-icon` / `.system-popover` / `.system-status-row` CSS. Every glyph is stroked at `var(--text)` (CSS `.system-status-icon svg, .chip-status-icon svg { stroke: var(--text) }`), with the status color applied as a redundant secondary fill via `.is-green`/`.is-orange`/`.is-red` on `.status-icon-fill`. Collapsed-chip box metrics (`padding:3px 10px; gap:5px; border-radius:4px; font-size:11px`) unchanged. `:focus-visible` accent rings on the chip, popover, and Manage action; no bare `outline:none`. Also corrected the audit's status-icon check (see Deviations) so it verifies the rendered `--text` stroke clears 3:1.
- **Task 3 (`62a3ab9`)** — Pasted byte-identical non-export copies of `TIER_RANK`, `computeRollup`, `chipLabel`, `normalizeSubsystems`, and the `fmt` helper near the FLAG_SVG block under a sync header (`// ── System status rollup (mirrors scripts/system-rollup.mjs — keep byte-identical) ──`). No `import` of the `.mjs`; functions not called yet (plan 04 wires them).

## Popover Row DOM Contract (for plan 04 in-place live updates)

The popover (`#systemStatusPopover`) contains exactly four `.system-status-row` divs in fixed order. Plan 04 should update text **in place** on these nodes (never rebuild the DOM, per RESEARCH Pitfall 3):

| Row | Row `id` | `data-subsystem` | Icon slot | Detail node `id` | Annotation node `id` | Action |
|-----|----------|------------------|-----------|------------------|----------------------|--------|
| Backend | `sysRowBackend` | `backend` | `.system-status-icon` (1st child) | `sysRowBackendDetail` | `sysRowBackendAnnotation` | — |
| FOLIO | `sysRowFolio` | `folio` | `.system-status-icon` | `sysRowFolioDetail` | `sysRowFolioAnnotation` | `#sysRowFolioManage` (`.system-status-action`) |
| Embedding | `sysRowEmbedding` | `embedding` | `.system-status-icon` | `sysRowEmbeddingDetail` | `sysRowEmbeddingAnnotation` | — |
| spaCy | `sysRowSpacy` | `spacy` | `.system-status-icon` | `sysRowSpacyDetail` | `sysRowSpacyAnnotation` | — |

- **Row anatomy:** `[.system-status-icon] [.system-status-name (13px/600)] [.system-status-detail (12px/400, --text-dim)] [.system-status-annotation (11px/600, --text-dim; `:empty` hides it)]`. The FOLIO row appends `.system-status-action` (accent text link, `margin-left:auto`).
- **Chip:** `#chipSystem` with icon slot `#chipSystemIcon` and label `#chipSystemLabel` (currently "System").
- **Glyphs:** `STATUS_ICON_SVG.healthy` / `.warning` / `.error` (insert as `innerHTML` of an icon slot, then set `.is-green`/`.is-orange`/`.is-red` on the slot or an ancestor to color the `.status-icon-fill`). Map `normalizeSubsystems` tier→glyph: `green→healthy`, `orange→warning` (reserved tier), `red→error`; the chip shows the rollup glyph from `computeRollup`.
- **Disclosure (plan 04):** `#chipSystem` already has `system-chip clickable`, so the existing `.status-chip.clickable` Enter/Space keydown handler (index.html ~10404) covers keyboard activation; plan 04 adds `onclick`→`openSystemPopover()`/`closeSystemPopover()`, the Escape/outside-click handlers, and toggles `hidden`/`aria-expanded`.

## Deviations from Plan

### [Rule 1 - Bug] Audit measured the wrong element for the implemented mitigation

- **Found during:** Task 2 verification.
- **Issue:** The Task 2 acceptance criterion requires `node scripts/contrast-audit.mjs` to exit 0 with **zero FAILs**, "proving the --text stroke clears 3:1". But the audit (built in plan 02) checked the **solid-fill** `--green`/`--orange`/`--red` tokens against the surfaces, which deliberately reports the 8 documented Light/mixed-light FAILs (2.53–2.84:1). Those FAILs are independent of my implementation — the audit had no knowledge of how the glyph actually renders, so it could never reach zero FAILs no matter how correctly the stroke fallback was applied. The audit was measuring a glyph variant this plan deliberately does **not** ship (solid-fill-only).
- **Fix:** Updated the status-icon audit loop in `scripts/contrast-audit.mjs` to compute the icon's graphical-object contrast as the **`var(--text)` stroke** on each surface — because every shipped glyph strokes at `--text` and that stroke is the distinguishing boundary (the silhouette) a colorblind/grayscale user reads (WCAG 1.4.11 measures the boundary that makes the object distinguishable). The status color is only a secondary fill behind it. The 3:1 `classifyIcon` floor was **not** weakened. The independent unit test in `scripts/contrast-audit.test.mjs` is unchanged and still pins that a **solid** green/orange fill FAILs 3:1 — keeping the `--text` stroke mandatory, not optional.
- **Result:** Audit now reports `296 pairs checked, 0 failures` / `Status-icon checks: 24, 0 fail`; full unit suite 48/48 pass.
- **Files modified:** `scripts/contrast-audit.mjs` (status-icon loop only; math, thresholds, and report structure unchanged).
- **Commit:** `c255114`.

## Out-of-Scope Note (left for plan 04, by plan design)

`checkHealth()` still contains `setChip('chipBackend'/'chipFolio'/'chipEmbedding'/'chipSpacy', …)` calls (index.html ~4061–4143) that now target removed DOM elements. This is **intentional** — the plan scopes `checkHealth()` rewiring to Wave 3 (plan 04). It does not crash: `setChip()` begins with `if (!chip) return;`, so these calls no-op safely against the absent elements until plan 04 replaces them with the rollup→render path. The `#chipLLM` branch of `setChip` continues to work unchanged (STATUS-06).

## Verification Results

- `node scripts/contrast-audit.mjs` → `296 pairs checked, 0 failures`; `Status-icon (3:1) checks: 24, 0 fail`; exit 0 (STATUS-05).
- `grep` → old chip IDs return 0; `#chipSystem` + `#systemStatusPopover` + `#chipLLM` present (3); `onclick="onLLMChipClick()"` present (1) (STATUS-01 / STATUS-06).
- Popover has exactly four `.system-status-row` rows in order Backend, FOLIO, Embedding, spaCy; only the FOLIO row has `openFolioModal()` + `aria-label="Manage FOLIO ontology"`; `#chipSystem` has no `chip-gear` (D-08).
- Inline rollup copy is byte-identical to `scripts/system-rollup.mjs` modulo dropped `export` (verified via `diff`), with no ES `import`; `node --check` confirms it is syntactically valid; no name collisions (each of TIER_RANK/computeRollup/chipLabel/normalizeSubsystems/fmt declared exactly once).
- `node --test 'scripts/**/*.test.mjs'` → 48 tests, 48 pass, 0 fail (includes the unchanged `system-rollup.test.mjs`, so the inline copy stays authoritative).
- No hex literals in the new component CSS block (the only `rgba` is the modal-standard `box-shadow: 0 6px 20px rgba(0,0,0,0.25)`, reused verbatim from 6 existing occurrences).

## STATUS-07 Note

Per the plan, header-overlap relief is structural here (4 chips → 1 frees width; collapsed chip footprint preserved exactly) and the final visual confirmation that `#statusBar` no longer overlaps `#layerToggleBar` is deferred to plan 04 Task 3 / verify-work UAT (Chrome DevTools), after a document loads. No CSS regression introduced; box metrics unchanged.

## Known Stubs

The chip and row icon slots and the `*Detail` row nodes ship with placeholder content ("Checking…", empty icon comment slots) **by plan design** — this wave builds structure only; plan 04 fills them live from `checkHealth()` via the inline rollup copy. The DOM contract above tells plan 04 exactly which nodes to target. This is not an abandoned stub: it is the documented Wave 2/3 boundary (plan objective: "This plan does the MARKUP + CSS + inline-module-copy; Wave 3 (plan 04) wires checkHealth()").

## Threat Flags

None. This plan ships static markup/CSS and an inline pure-logic copy; no untrusted input is rendered (T-03-03 accept: live `textContent` injection is plan 04). No package installs (T-03-SC: zero installs — single-file vanilla JS).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace four chips with System disclosure chip + popover; re-home FOLIO Manage | 040228b | frontend/index.html |
| 2 | Add status-icon SVGs + chip/popover/icon CSS with --text stroke fallback | c255114 | frontend/index.html, scripts/contrast-audit.mjs |
| 3 | Paste byte-identical inline rollup module copy | 62a3ab9 | frontend/index.html |

## Self-Check: PASSED

- FOUND: .planning/phases/03-consolidated-system-status-chip/03-03-SUMMARY.md
- FOUND commit 040228b (Task 1)
- FOUND commit c255114 (Task 2)
- FOUND commit 62a3ab9 (Task 3)
- FOUND commit dd86d1e (SUMMARY)
- Only untracked file is the regenerable 03-AUDIT-REPORT.md (intentionally not tracked, per 02-SUMMARY precedent)
