---
phase: 03-consolidated-system-status-chip
verified: 2026-05-22T00:00:00Z
status: human_needed
score: 5/5 roadmap success criteria verified (automated)
overrides_applied: 1
overrides:
  - must_have: "Status icons are inline SVG with three distinct silhouettes (check / triangle / cross), stroked at --text so they clear 3:1 in every theme — a real status icon, never a color-only dot (D-09)"
    reason: "D-09 was formally revised at UAT (product owner direction). Flat filled dots matching the LLM/layer .chip-dot circles replaced the stroked silhouettes. WCAG 1.4.11 is preserved via deeper --status-dot-* shades on light surfaces (unit-tested and audit-verified, 0 failures). WCAG 1.4.1 is preserved because every popover row carries a status word and the collapsed chip names the failing subsystem in text. Documented in 03-04-SUMMARY.md under 'D-09 REVISED at UAT'."
    accepted_by: "product owner (UAT)"
    accepted_at: "2026-05-22T00:00:00Z"
human_verification:
  - test: "STATUS-02 quiet-green: fresh page load at http://localhost:8731/ shows a single green chip labeled 'System' in the header (not four separate chips)"
    expected: "One 'System' chip visible in the status bar with a green dot; no Backend/FOLIO/Embedding/spaCy chips present; chip shows green state; FOLIO/Embedding rows show 'Standby — loads on first use' but chip remains green"
    why_human: "Visual rendering, exact header layout, and correct aria-expanded=false initial state cannot be confirmed by grep; requires browser observation at the live :8731 origin where /health is reachable"
  - test: "STATUS-03 degraded: in browser console override fetch for /health/detail to return spacy.status:'error'; observe chip label and popover"
    expected: "Chip shows red dot + label 'System: spaCy'; adding a second failure (e.g. folio_ontology.status:'error') updates label to 'System: spaCy +1' (or 'System: FOLIO +1' depending on worst-first order); all popover rows visible"
    why_human: "Requires live mock of /health/detail response and visual confirmation of label update; not verifiable by static analysis"
  - test: "STATUS-04 popover metrics: click the System chip to expand; confirm all four rows show meaningful metrics"
    expected: "Backend: 'Running'; FOLIO: '{N} concepts, {M} labels indexed'; Embedding: '{provider}, {K} vectors indexed'; spaCy: 'spaCy {version} — EntityRuler ready'; FOLIO row shows 'Manage FOLIO' button"
    why_human: "Metric content comes from live /health/detail response and requires visual confirmation in the expanded popover"
  - test: "STATUS-05 keyboard accessibility: navigate to the System chip with Tab, press Enter to open the popover, press Escape to close; confirm focus management"
    expected: "Enter opens the popover and moves focus into it; Escape closes the popover and returns focus to the chip; Tab navigates through popover rows; outside-click closes the popover"
    why_human: "Focus management, keyboard events, and screen-reader behavior cannot be confirmed by static code analysis; requires interactive browser testing"
  - test: "STATUS-06 LLM chip: confirm the LLM chip remains separate and clickable, opening the LLM configuration UI"
    expected: "LLM chip still appears in the header to the right of the System chip; clicking it opens the LLM configuration modal; the chip shows its current LLM provider state"
    why_human: "Requires visual confirmation that the LLM chip is present in the live UI and its click behavior works"
  - test: "STATUS-07 no overlap: load a document to make the layer chips (Nouns/Verbs/Individuals/POS) appear; confirm no overlap between the status bar and the layer toggle bar"
    expected: "At normal desktop width, the status bar right edge and layer toggle bar left edge do not overlap; a visible gap exists between them; header layout is clean"
    why_human: "Pixel-level overlap detection requires visual inspection in the browser at a specific viewport width; the structural fix (4→1 chip reduction, min-width:0 on status-bar) is in place but visual outcome requires browser confirmation"
  - test: "STATUS-05 dot rendering in Light theme: switch to Light theme and observe the status indicator dots"
    expected: "Green and red dots on the System chip and in the popover rows are clearly visible with sufficient contrast against the light surface; dots match the size and style of the amber LLM dot (6px flat filled circles)"
    why_human: "Visual contrast and size matching of the flat dots in the Light theme requires visual inspection; the audit proves the CSS token math but not the rendered appearance"
---

# Phase 03: Consolidated System Status Chip — Verification Report

**Phase Goal:** Collapse Backend / FOLIO / Embedding / spaCy into one accessible "System" chip with worst-status rollup and click-to-expand detail.
**Verified:** 2026-05-22
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All five roadmap success criteria are verified by code evidence and automated test results. The phase goal is achieved in the codebase. Seven human verification items (browser-based) remain, consistent with the `checkpoint:human-verify` gate in plan 04 Task 3.

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Single "System" chip replaces the four Backend/FOLIO/Embedding/spaCy chips; quiet green when all subsystems healthy | VERIFIED | `grep -c 'id="chipBackend"\|id="chipFolio"\|id="chipEmbedding"\|id="chipSpacy"' frontend/index.html` → 0; `#chipSystem` markup with `aria-expanded="false"` confirmed at line 3059; `normalizeSubsystems` all-green → `computeRollup` returns `{tier:'green'}` → `chipLabel` returns `"System"` (unit-tested, 50/50 pass) |
| 2 | Worst-status rollup (red > orange > green) names the failing subsystem when any subsystem is degraded or errored | VERIFIED | `computeRollup` + `chipLabel` with `TIER_RANK={green:0,orange:1,red:2}` unit-tested across all failure combinations (STATUS-03 tests in `system-rollup.test.mjs`); `renderSystemChip` wired to `computeRollup(normalizeSubsystems(d, backendUp))` in `checkHealth()` at index.html:4280-4282 |
| 3 | User can click/expand the chip to reveal per-subsystem detail, preserving today's metrics | VERIFIED | `#systemStatusPopover` exists with four always-present rows (`sysRowBackend`, `sysRowFolio`, `sysRowEmbedding`, `sysRowSpacy`); `openSystemPopover`/`closeSystemPopover`/`toggleSystemPopover` implemented; `renderPopoverRows` writes metric/annotation via `textContent`; metric strings verified unit-tested (STATUS-04 assertions in `system-rollup.test.mjs`) |
| 4 | Status perceived via icon + text (not color alone); WCAG AA; keyboard- and screen-reader-accessible | VERIFIED (automated portion) | Contrast audit: `node scripts/contrast-audit.mjs` → 290 pairs, 0 failures, 18 icon checks (3:1 floor), 0 fail; `--status-dot-*` tokens: light theme uses deeper shades (#15803d/#b45309/#dc2626) unit-tested to clear 3:1; `aria-label` on chip updated with chipLabel text; `role="button"`, `tabindex="0"`, `aria-haspopup`, `aria-expanded`, `aria-controls` on #chipSystem; `focus-visible` rings on chip/popover/Manage action (lines 1310, 1343, 1375); Escape handler at line 10728; Enter/Space via `.status-chip.clickable` keydown at line 10744; status not color-only: every row has text, chip names failing subsystem. Human browser verification still needed (see below) |
| 5 | LLM chip remains separate and actionable; header status chips no longer overlap layer chips | VERIFIED (structural) | `grep` confirms `id="chipLLM"`, `onclick="onLLMChipClick()"`, `.chip-gear` present unchanged; `setChip`/`updateOllamaChip()` preserved in `checkHealth()` at lines 4269, 4303-4315; STATUS-07: `.status-bar` has `flex-shrink:1; min-width:0` at line 543; 4→1 reduction frees width structurally; visual gap measurement requires browser (human verification item) |

**Score: 5/5 roadmap truths verified (automated evidence; browser confirmation items in human_verification section)**

### D-09 Override Note

Plan 03 (`03-03-PLAN.md`) specified three distinct stroked silhouettes (check/triangle/cross). This was formally revised during live UAT at the product owner's direction. The shipped implementation uses flat filled dots matching the LLM/layer `.chip-dot` circles. WCAG compliance is preserved differently — via deeper `--status-dot-*` shades on light surfaces (unit-tested) and text-based status discrimination (statusWord + chip label). This deviation is intentional and documented; it is applied as an override (counted PASSED, not FAILED).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/system-rollup.mjs` | Pure exported normalizeSubsystems/computeRollup/chipLabel | VERIFIED | Exists, 138 lines; exports TIER_RANK, computeRollup, chipLabel, normalizeSubsystems; no DOM, no default export; commit chain e643410→e231728→2908406 |
| `scripts/system-rollup.test.mjs` | Node built-in tests for STATUS-02/03/04/06, D-05/06/07/08 | VERIFIED | Exists, 233 lines; 23 tests all pass; imports from `./system-rollup.mjs`; STATUS-02/03/04/06 and D-05/06/07/08 in test titles |
| `scripts/contrast-audit.mjs` | Status-icon 3:1 graphical-object audit + corrected report path | VERIFIED | Contains `STATUS_ICON_TOKENS = ['--status-dot-green','--status-dot-orange','--status-dot-red']`, `classifyIcon()` at 3:1 floor, report path at line 230 points to `03-consolidated-system-status-chip`; 0 of old path string remaining |
| `scripts/contrast-audit.test.mjs` | STATUS-05 assertions for status-dot contrast ratios | VERIFIED | Exists; 6 STATUS-05 tests pinning #15803d/#b45309/#dc2626 pass ≥3:1 and #16a34a/#d97706 fail <3:1 on #eceef4/#e2e5ee |
| `frontend/index.html` (chip markup) | System disclosure chip + popover with four rows | VERIFIED | `#chipSystem` with `role="button"`, `tabindex="0"`, `aria-haspopup="true"`, `aria-expanded="false"`, `aria-controls="systemStatusPopover"`; `#systemStatusPopover` with `role="region"`, `tabindex="-1"`, `hidden`; four rows in order Backend/FOLIO/Embedding/spaCy; FOLIO row has `openFolioModal()` + `aria-label="Manage FOLIO ontology"` |
| `frontend/index.html` (JS: render functions) | renderSystemChip/renderPopoverRows/openSystemPopover/closeSystemPopover | VERIFIED | All four functions present; `renderPopoverRows` uses `textContent` only for metric/annotation strings; `_setStatusIcon` uses `innerHTML` only for static `STATUS_ICON_SVG` constants; `data-glyph` idempotent check prevents DOM teardown |
| `frontend/index.html` (inline rollup) | Byte-identical non-export copy of rollup module | VERIFIED | Sync header at line 10490; `TIER_RANK`, `computeRollup`, `chipLabel`, `fmt`, `normalizeSubsystems` all present without `export` keyword; function bodies match `scripts/system-rollup.mjs` signatures exactly |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `#chipSystem` | `#systemStatusPopover` | `aria-controls="systemStatusPopover"` | VERIFIED | Confirmed at index.html:3061 |
| `index.html checkHealth()` | `normalizeSubsystems → computeRollup → renderSystemChip` | Call chain | VERIFIED | `normalizeSubsystems(d, backendUp)` → `computeRollup(subsystems)` → `renderSystemChip(rollup)` and `renderPopoverRows(subsystems)` at lines 4280-4282; backend-down path at lines 4266-4268 |
| `#chipSystem click/keydown` | `toggleSystemPopover` | Click listener + existing `.status-chip.clickable` Enter/Space handler | VERIFIED | `chipSystem.addEventListener('click', toggleSystemPopover)` at line 10759; Escape branch at line 10728; Enter/Space via existing keydown handler at line 10744 |
| `scripts/system-rollup.test.mjs` | `scripts/system-rollup.mjs` | ES import | VERIFIED | `from './system-rollup.mjs'` at line 8 |
| `frontend/index.html` inline copy | `scripts/system-rollup.mjs` | Byte-identical sync | VERIFIED | Function bodies match; only `export` prefix differs |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `renderSystemChip` | `rollup` (from `computeRollup`) | `checkHealth()` → `fetch('/health/detail')` → `normalizeSubsystems(d, true)` | Yes — live /health/detail response | FLOWING |
| `renderPopoverRows` | `subsystems` array | Same as above; `s.metric` / `s.annotation` from `normalizeSubsystems` | Yes — real backend data mapped to row strings | FLOWING |
| `renderPopoverRows` row text | `detailEl.textContent = s.metric` | `normalizeSubsystems` maps `d.folio_ontology.concepts` + `d.folio_ontology.labels_indexed` + `d.embedding.provider` + `d.embedding.index_size` + `d.spacy.version` | Yes — all metric fields read from /health/detail JSON | FLOWING |
| Backend-down path | `normalizeSubsystems(null, false)` | `/health` fetch fail → catch block | Yes — static "Offline" strings appropriate for backend-down state | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite: 50 tests pass | `node --test 'scripts/**/*.test.mjs'` | 50 pass, 0 fail, exit 0 | PASS |
| Contrast audit: 0 failures | `node scripts/contrast-audit.mjs` | 290 pairs, 0 failures; 18 icon checks, 0 fail | PASS |
| Old chip IDs removed | `grep -c 'id="chipBackend"\|id="chipFolio"\|id="chipEmbedding"\|id="chipSpacy"' frontend/index.html` | 0 | PASS |
| New chip IDs present | `grep -c 'id="chipSystem"\|id="systemStatusPopover"\|id="chipLLM"' frontend/index.html` | 3 | PASS |
| LLM exclusion in rollup module | `grep -c "detail\.llm\|d\.llm" scripts/system-rollup.mjs` | 0 | PASS |
| No export keyword on inline functions | `grep -E "^export function\|^export const" frontend/index.html` | 0 results | PASS |
| renderPopoverRows uses textContent | `renderPopoverRows` function body contains `textContent` with no `innerHTML` of message strings | Confirmed at lines 4199-4202 | PASS |
| FOLIO completed-update toast preserved | `grep -n "_lastFolioUpdateAt\|_showInfoToast" frontend/index.html` | Both present in checkHealth() at lines 4289-4295 | PASS |
| setChip() and LLM branch preserved | `grep "setChip\|updateOllamaChip" frontend/index.html` | Both present; LLM branch at lines 4303-4315 unchanged | PASS |
| setInterval cadence unchanged | `grep -n "setInterval.*checkHealth"` | Line 4126: `setInterval(checkHealth, 10000)` — unchanged | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|---------|
| STATUS-01 | 03-03, 03-04 | Single "System" chip replaces four subsystem chips | SATISFIED | Old chip IDs return 0 from grep; `#chipSystem` + `#systemStatusPopover` exist; `renderPopoverRows` drives four rows |
| STATUS-02 | 03-01 | Quiet green when all subsystems healthy | SATISFIED | `computeRollup` all-green → `{tier:'green'}`; `chipLabel` → `"System"`; unit-tested STATUS-02 |
| STATUS-03 | 03-01, 03-04 | Worst-status rollup names failing subsystem with +N overflow | SATISFIED | `TIER_RANK`, `computeRollup`, `chipLabel` unit-tested; wired in `checkHealth()` |
| STATUS-04 | 03-04 | Expandable detail with preserved metrics | SATISFIED | `#systemStatusPopover` with four rows; `renderPopoverRows` with metric `textContent`; metric strings unit-tested |
| STATUS-05 | 03-02, 03-03, 03-04 | Status via icon+text, WCAG AA, keyboard/SR accessible | SATISFIED (automated); HUMAN NEEDED (browser) | Audit: 0 failures, 18 icon checks; unit tests pin contrast ratios; ARIA attributes confirmed; browser verification for keyboard/focus behavior |
| STATUS-06 | 03-01, 03-04 | LLM chip separate and unchanged | SATISFIED | `#chipLLM`, `onLLMChipClick()`, `chip-gear` unchanged; `setChip`/`updateOllamaChip()` preserved; LLM excluded from rollup (grep → 0) |
| STATUS-07 | 03-03, 03-04 | Header chips no longer overlap layer chips | SATISFIED (structural); HUMAN NEEDED (visual) | 4→1 reduction frees width; `.status-bar { flex-shrink:1; min-width:0 }`; UAT reports 16px gap at 1221px desktop; requires visual browser confirmation |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/index.html` | 3062 | `<!-- inline SVG rollup glyph (plan 04) -->` comment in `#chipSystemIcon` slot | Info | Harmless static HTML comment; slot is populated at runtime by `_setStatusIcon` (plan 04 delivered this); comment is accurate documentation of design intent |
| `frontend/index.html` | 3070-3093 | `<!-- inline SVG status glyph (plan 04) -->` comments in row icon slots | Info | Same as above; populated at runtime by `renderPopoverRows` → `_setStatusIcon`; correct |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file. No unreferenced debt markers. No stub anti-patterns in the render path — initial placeholder text (`Checking…`) in row detail nodes is overwritten on first `checkHealth()` poll, which is correct behavior.

### Inline `innerHTML` for STATUS_ICON_SVG — Not a DOM-XSS Risk

`_setStatusIcon` uses `slot.innerHTML = STATUS_ICON_SVG[glyph]` at line 4171. `STATUS_ICON_SVG` is a hardcoded constant (three flat dot SVGs, no untrusted string interpolation). This is not an anti-pattern — it is the documented, safe pattern and is explicitly noted in a comment at line 4159: "static constant — no untrusted input". All backend-sourced strings (`s.metric`, `s.annotation`) go through `textContent`.

### Human Verification Required

#### 1. STATUS-02 Quiet Green State

**Test:** Open http://localhost:8731/ (same-origin backend) in Chrome. Observe the header.
**Expected:** A single green "System" chip visible in the status bar; no separate Backend/FOLIO/Embedding/spaCy chips; chip shows green dot and "System" label; popover is collapsed (aria-expanded=false).
**Why human:** Visual rendering, chip count, and aria-expanded initial state require browser observation.

#### 2. STATUS-03 Degraded State

**Test:** In the browser console, override `fetch` to intercept `/health/detail` and return `spacy.status:'error'`; wait for the next 10s poll.
**Expected:** Chip switches to red dot + "System: spaCy"; adding a second failure updates to "System: spaCy +1" (or similar with overflow count); popover shows red icon on the spaCy row.
**Why human:** Requires live mock injection and visual confirmation of label update.

#### 3. STATUS-04 Popover Metrics

**Test:** Click the System chip to expand the popover; read all four rows.
**Expected:** Backend: "Running"; FOLIO: "{N} concepts, {M} labels indexed"; Embedding: "{provider}, {K} vectors indexed"; spaCy: "spaCy {version} — EntityRuler ready"; FOLIO row has "Manage FOLIO" button that opens the FOLIO modal.
**Why human:** Live /health/detail data required; popover interaction requires browser.

#### 4. STATUS-05 Keyboard Accessibility

**Test:** Keyboard-only navigation: Tab to System chip → Enter to open → Tab through popover → Escape to close.
**Expected:** Focus moves into popover on open; Escape closes and returns focus to chip; no focus trap; outside-click closes.
**Why human:** Focus order, focus movement, and keyboard event behavior require interactive browser testing.

#### 5. STATUS-06 LLM Chip Integrity

**Test:** Verify the LLM chip is visible in the header, to the right of the System chip, and clicking it opens the LLM configuration modal.
**Expected:** LLM chip present; click opens modal; chip shows current provider state.
**Why human:** Visual confirmation of LLM chip presence and modal trigger.

#### 6. STATUS-07 No Header Overlap

**Test:** Load a document (to populate layer chips); observe whether the status bar and layer toggle bar overlap at normal desktop width.
**Expected:** Visible gap between the status bar right edge and layer toggle bar left edge; no overlap. SUMMARY reports 16px gap at 1221px desktop.
**Why human:** Pixel-level overlap requires visual browser inspection; the structural fix is in place but the visual outcome needs confirmation.

#### 7. STATUS-05 Light Theme Dot Visibility

**Test:** Switch to Light theme; observe the status indicator dots on the System chip and in the popover.
**Expected:** Green/orange/red dots are clearly visible against the light surface (#15803d / #b45309 / #dc2626 shades); dots match the 6px size of the amber LLM dot.
**Why human:** Visual dot appearance and size parity in Light theme require browser observation; math is verified by the audit.

### Gaps Summary

No blocking gaps found. All automated checks pass (50/50 tests, 0 contrast audit failures). The seven human verification items listed above are a natural consequence of the `checkpoint:human-verify` gate in plan 04 Task 3, which was conducted live by the product owner across Dark/Light/Mixed themes (documented in `03-04-SUMMARY.md` with all 7 STATUS requirements marked PASS). The human_verification section surfaces those items for independent re-confirmation.

---

_Verified: 2026-05-22_
_Verifier: Claude (gsd-verifier)_
