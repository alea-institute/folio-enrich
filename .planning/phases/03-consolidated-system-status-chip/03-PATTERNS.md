# Phase 03: Consolidated System Status Chip - Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 5 (1 modify + 1 create + 1 create + 1 modify + 1 modify)
**Analogs found:** 5 / 5 (every file has a strong in-repo analog)

> Single-file vanilla JS, no build step, no new dependencies, three-mode CSS-variable theme (Dark/Light/Mixed). The discipline this phase rewards is **reuse and refactor**, not invent — every needed primitive already exists in `frontend/index.html` or in the Phase 02 `scripts/` precedent.

---

## File Classification

| New/Modified File | Action | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `frontend/index.html` | MODIFY | component (UI markup + CSS + presentation JS) | request-response (polls `/health`, `/health/detail`) | itself — existing `.status-chip` markup, `setChip()`/`checkHealth()`, FOLIO modal `.folio-status-row`, inline `FLAG_SVG` block | exact (self-refactor) |
| `scripts/system-rollup.mjs` | CREATE | utility (pure exported logic module) | transform (health JSON → rollup/label) | `scripts/flags.mjs` | exact |
| `scripts/system-rollup.test.mjs` | CREATE | test (Node built-in runner) | n/a | `scripts/flags.test.mjs` | exact |
| `scripts/contrast-audit.mjs` | MODIFY | utility (zero-dep WCAG audit) | file-I/O (reads HTML, writes report) | itself — existing audit loops | exact (self-extend) |
| `scripts/contrast-audit.test.mjs` | MODIFY | test (Node built-in runner) | n/a | itself + `scripts/flags.test.mjs` | exact |

---

## Critical Cross-File Pattern: the "byte-identical sibling module" (Phase 02 precedent)

This is the single most important pattern for the planner to internalize. Phase 02 did **NOT** import `scripts/flags.mjs` into `index.html` as an ES module. The single-file/no-build constraint forbids that. Instead:

1. The pure logic lives in `scripts/flags.mjs` as an **`export`ed** module — this is what `scripts/flags.test.mjs` imports and unit-tests.
2. The **same logic is duplicated inline** into `frontend/index.html` (no `export`/`import`), guarded by a header comment ordering the two copies to stay byte-identical.

**`frontend/index.html:10297-10354`** — the inline duplicate, with its provenance/sync header:
```javascript
// ── Translation flags (inline SVG; mirrors scripts/flags.mjs — keep byte-identical) ──
// ...vendoring rules...
const FLAG_SVG = { /* same map as flags.mjs, but no `export` keyword */ };
const LANG_TO_COUNTRY = { he: 'il', /* ... */ };          // mirrors flags.mjs
function localeToCountry(locale) { /* identical body */ }
function localeLabel(locale) { /* identical body */ }
function flagMarkup(locale) { /* identical body */ }
```

**`scripts/flags.mjs:1-9, 18, 67`** — the exported authoritative copy:
```javascript
// Pure, testable module mirroring the style of scripts/contrast-audit.mjs.
// The same FLAG_SVG map + helpers are inlined into frontend/index.html
// (single-file frontend, no build step) — keep the two byte-identical so
// these unit tests stay authoritative.
export const FLAG_SVG = { /* ... */ };
export function localeToCountry(locale) { /* ... */ }
```

**Apply to `scripts/system-rollup.mjs` ↔ `frontend/index.html`:** author `normalizeSubsystems()`, `computeRollup()`, `chipLabel()` as `export`ed pure functions in `scripts/system-rollup.mjs`, then paste the identical (non-`export`) bodies into `index.html`'s `<script>` near the other presentation helpers, with a header comment: `// ── System status rollup (mirrors scripts/system-rollup.mjs — keep byte-identical) ──`. The `.test.mjs` imports only the `scripts/` copy.

---

## Pattern Assignments

### `scripts/system-rollup.mjs` (utility, transform) — CREATE

**Analog:** `scripts/flags.mjs`

**Module header + provenance comment** (mirror `flags.mjs:1-9`):
```javascript
// Pure subsystem-health rollup logic for the consolidated "System" status chip.
//
// Pure, testable module mirroring the style of scripts/flags.mjs.
// normalizeSubsystems()/computeRollup()/chipLabel() are inlined into
// frontend/index.html (single-file frontend, no build step) — keep the two
// byte-identical so these unit tests stay authoritative.
```

**Export style** (mirror `flags.mjs:18, 45, 67, 90` — top-level `export const`/`export function`, no default export):
```javascript
export const TIER_RANK = { green: 0, orange: 1, red: 2 };
export function normalizeSubsystems(detail) { /* ... */ }
export function computeRollup(subsystems) { /* ... */ }
export function chipLabel(rollup) { /* ... */ }
```

**Core transform pattern** — copy the rollup/label bodies verbatim from RESEARCH.md § Pattern 3 (`03-RESEARCH.md:229-251`). The D-05/D-06 Standby/Update→green mapping belongs in `normalizeSubsystems` (one place), NOT in `computeRollup`:
```javascript
// computeRollup: worst-of-four, red > orange > green; "+N" = other non-green beyond the worst
export function computeRollup(subsystems) {
  let worst = { name: null, tier: 'green' };
  let failCount = 0;
  for (const s of subsystems) {
    if (TIER_RANK[s.tier] > TIER_RANK['green']) failCount++;
    if (TIER_RANK[s.tier] > TIER_RANK[worst.tier]) worst = s;
  }
  const overflow = Math.max(0, failCount - 1);
  return { tier: worst.tier, worstName: worst.name, overflow };
}
export function chipLabel(rollup) {
  if (rollup.tier === 'green') return 'System';                // D-10
  let label = `System: ${rollup.worstName}`;                   // D-11
  if (rollup.overflow > 0) label += ` +${rollup.overflow}`;    // D-11
  return label;
}
```

**`normalizeSubsystems` contract** — maps raw `/health/detail` JSON to 4 ordered rows `[{key,name,tier,statusWord,metric,annotation,action?}]`, LLM EXCLUDED. The exact backend status enums (verified in `backend/app/api/routes/health.py:42,49,51,61,66,68,99,105,133,137`): every subsystem returns `status: "ready" | "not_loaded" | "error"`; FOLIO additionally nests `update_status.{update_in_progress, update_available, last_update_at, concepts_before, concepts_after}`. Encode D-05 (`not_loaded`→green) and D-06 (update flags→green) here. Source the metric/annotation strings from the Metric Preservation Map (`03-RESEARCH.md:352-368`) and the Copywriting Contract (`03-UI-SPEC.md:159-176`).

**Self-contained helper pattern** (mirror `flags.mjs:50-59`): if `normalizeSubsystems` needs `.toLocaleString()`-style formatting or escaping, keep helpers inline in the module so `node:test` stays standalone (no DOM, no imports beyond `node:` built-ins).

---

### `scripts/system-rollup.test.mjs` (test) — CREATE

**Analog:** `scripts/flags.test.mjs`

**Imports + framework pattern** (copy `flags.test.mjs:1-9` exactly — Node built-in test runner, no framework install):
```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  TIER_RANK,
  normalizeSubsystems,
  computeRollup,
  chipLabel,
} from './system-rollup.mjs';
```

**Test-naming + requirement-tagging pattern** (mirror `flags.test.mjs:11,42,55,63` — section banner comments, requirement IDs in titles, one behavior per `test()`):
```javascript
// ── computeRollup: worst-of-four + quiet green (STATUS-02/03) ──────────────
test('STATUS-02: all-green subsystems roll up to green "System"', () => {
  const r = computeRollup([{name:'Backend',tier:'green'}, {name:'FOLIO',tier:'green'},
                           {name:'Embedding',tier:'green'}, {name:'spaCy',tier:'green'}]);
  assert.equal(r.tier, 'green');
  assert.equal(chipLabel(r), 'System');
});

test('STATUS-03: single error names the failing subsystem', () => {
  const r = computeRollup([{name:'Backend',tier:'green'}, {name:'spaCy',tier:'red'}]);
  assert.equal(chipLabel(r), 'System: spaCy');
});

test('STATUS-03: multiple failures show worst + "+N" overflow', () => { /* ... */ });
```

**D-05/D-06 normalize assertions** (mirror the `flags.test.mjs:26-39` "D-03" mapping tests — assert the locked decision directly):
```javascript
test('D-05: FOLIO not_loaded normalizes to green (Standby annotation)', () => {
  const [folio] = normalizeSubsystems({ folio_ontology: { status: 'not_loaded' } })
    .filter(s => s.key === 'folio');
  assert.equal(folio.tier, 'green');
  assert.match(folio.annotation, /Standby/);
});
test('D-06: FOLIO update_available stays green', () => { /* ... */ });
```

---

### `frontend/index.html` (component, request-response) — MODIFY

**Analog:** itself. Four edit clusters; the LLM path (`chipLLM`, `onLLMChipClick()`, `updateOllamaChip()`, the `d.llm` branch) is a HARD no-touch boundary (STATUS-06).

#### (a) Markup — replace 4 chips + add popover (`index.html:2960-2980`)

Current four-chip block to replace (keep `chipLLM` at `:2981-2986` untouched):
```html
<div class="status-bar" id="statusBar">
  <div class="status-chip" id="chipBackend" data-tooltip="Checking...">
    <span class="chip-dot gray"></span>
    <span class="chip-label">Backend</span>
    <span class="chip-detail" id="chipBackendDetail">...</span>
  </div>
  <div class="status-chip clickable" id="chipFolio" ... onclick="openFolioModal()" tabindex="0" role="button" aria-label="Manage FOLIO ontology">
    ...<span class="chip-gear">&#9881;</span>
  </div>
  ... chipEmbedding, chipSpacy ...
```

Replace with the disclosure chip + popover from `03-RESEARCH.md:173-187` (the `role="button"` + `aria-expanded`/`aria-controls` disclosure pattern, popover `role="region"` placed immediately after the chip in source order). Re-home the FOLIO `onclick="openFolioModal()"` + gear affordance into a "Manage FOLIO" action inside the popover's FOLIO row (D-08) — do NOT lose it.

#### (b) CSS — extend `.status-chip` + add popover/icon styles (`index.html:536-584`, `1270-1296`)

`.status-chip` box metrics to preserve verbatim (D-12 — header density must not change so freed width holds):
```css
.status-chip {
  display: flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 4px;
  background: var(--surface2); border: 1px solid var(--border);
  font-size: 11px; color: var(--text-dim); white-space: nowrap;
}
.status-chip:hover { border-color: var(--accent-dim); }
```

Fixed-position overlay pattern to mirror for the popover (`index.html:570-583` — the `data-tooltip` already does `position: fixed; top: 44px; z-index: 100` in this exact header):
```css
.status-chip[data-tooltip]:hover::after {
  content: attr(data-tooltip);
  position: fixed; top: 44px;
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 4px; padding: 4px 8px; font-size: 11px;
  color: var(--text); white-space: nowrap; z-index: 100; pointer-events: none;
}
```

Clickable/focus pattern to reuse for the chip's interactive + accent treatment (`index.html:1267, 1270-1280`):
```css
textarea:focus { outline: none; border-color: var(--accent); }          /* accent focus-ring precedent */
.status-chip.clickable { cursor: pointer; }
.status-chip.clickable:hover {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}
```

Per-row status pattern to mirror for the 4 popover rows (`index.html:1284-1296`):
```css
.folio-status-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 16px; padding: 10px 14px;
  background: var(--surface); border-radius: 8px;
}
.folio-status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.folio-status-dot.green { background: var(--feedback-positive); }
.folio-status-text { font-size: 14px; font-weight: 600; color: var(--modal-text); }
```
> Note: popover rows use `var(--surface3)` background (UI-SPEC), not `.folio-status-row`'s `var(--surface)` — copy the flex/gap/padding rhythm, swap the surface token. Use `gap: 8px; padding: 10px 14px` per UI-SPEC § Component Layout Contract.

Status icons replace `.chip-dot` color-only dots (`index.html:554-564`). Render inline SVG glyphs (check / triangle-bang / cross-circle) per `03-RESEARCH.md:322-350`, with `var(--text)` stroke for the guaranteed-3:1 outline + status-color fill (Pitfall 1 — Light-theme green/orange fail 3:1 as solid fills).

#### (c) JS — refactor `checkHealth()`, keep `setChip()` for LLM (`index.html:4021-4130`)

`setChip()` (`:4021-4036`) — **KEEP**; still used by `chipLLM` + Ollama. Note its `textContent` discipline (V5 output-encoding, never `innerHTML` for backend `message` strings):
```javascript
function setChip(id, dotColor, detail, tooltip) {
  const chip = document.getElementById(id);
  if (!chip) return;
  const dot = chip.querySelector('.chip-dot');
  dot.className = 'chip-dot ' + dotColor;
  const detailEl = document.getElementById(id + 'Detail');
  if (detailEl) { detailEl.textContent = detail; detailEl.style.display = detail ? '' : 'none'; }
  chip.setAttribute('data-tooltip', tooltip);
  if (id === 'chipLLM' && dotColor === 'green') hideLlmBanner();
}
```

`checkHealth()` (`:4038-4130`) — refactor the FOLIO/Embedding/spaCy + backend branches to: `const subsystems = normalizeSubsystems(d, backendUp); renderSystemChip(computeRollup(subsystems)); renderPopoverRows(subsystems);`. Leave the `d.llm` branch (`:4100-4118`, the `await updateOllamaChip()` call + `setChip('chipLLM', ...)`) byte-for-byte intact. Two existing behaviors that MUST survive the refactor:
- The backend-down fallback (`:4044-4050`) — drives the chip red + all rows offline.
- The FOLIO completed-update toast using `_lastFolioUpdateAt` (`:4074-4081`) — preserve verbatim.

Polling cadence is unchanged (`setInterval(checkHealth, 10000)` at `:4011`); the popover must update rows **in place** when open (D-03), never tear-down/rebuild (Pitfall 3).

#### (d) JS — extend Escape handler + chip keydown (`index.html:10388-10411`)

Escape handler to extend with a System-popover branch (`:10388-10401`):
```javascript
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const folioModal = document.getElementById('folioModal');
    if (folioModal && folioModal.classList.contains('visible')) { closeFolioModal(); return; }
    const graphModal = document.getElementById('graphModal');
    if (graphModal.classList.contains('visible')) { closeGraphModal(); }
  }
});
```
Add a `#systemStatusPopover`-open branch (close it on Escape) ahead of the modal checks, OR follow the research's `_systemPopoverKeydown` listener approach (`03-RESEARCH.md:200-225`) — both are acceptable; extending this single handler keeps Escape logic in one place (Don't-Hand-Roll table).

Chip keydown (Enter/Space) — already correct, just ensure the new System chip matches the selector (`:10404-10411`):
```javascript
document.querySelectorAll('.status-chip.clickable').forEach(chip => {
  chip.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chip.click(); }
  });
});
```
Give the System chip the `clickable` class (or add `system-chip` to this selector) so it inherits Enter/Space activation for free.

#### (e) Inline rollup module duplicate (the byte-identical sibling)

Paste the non-`export` bodies of `normalizeSubsystems`/`computeRollup`/`chipLabel` into the `<script>` near the existing `FLAG_SVG` block (`:10297`), with a sync header comment. This mirrors exactly how `flags.mjs` is duplicated at `:10297-10354`.

---

### `scripts/contrast-audit.mjs` (utility, file-I/O) — MODIFY

**Analog:** itself.

**Two required changes (both flagged in RESEARCH Pitfall 2, `03-RESEARCH.md:298-302`):**

1. **Fix the stale report path** (`contrast-audit.mjs:200`) — currently points at a non-existent dir, which makes `node --test scripts/` fail when it imports the module (verified: directory-form test run fails; named-file run passes):
```javascript
const reportPath = path.join(projectRoot, '.planning/phases/03-accessibility-component-polish/03-AUDIT-REPORT.md');
// → should target the Phase 03 dir: .planning/phases/03-consolidated-system-status-chip/03-AUDIT-REPORT.md
```

2. **Add a status-icon 3:1 graphical-object check.** The script today only audits `TEXT_TOKENS = ['--text','--text-dim','--accent']` against `BG_TOKENS` at the 4.5/3.0 text thresholds (`:99-100, 234-250`); it has NO `--green/--orange/--red`-as-graphical-object check. Mirror the existing text-on-bg loop (`:234-250`), but use `[--green,--orange,--red]` foregrounds against `[--surface2,--surface3]` at a **3:1** floor:
```javascript
// existing loop to mirror (note the resolveVariable + contrastRatio + classify trio):
for (const bg of BG_TOKENS) {
  const bgHex = resolveVariable(bg, tmap, paletteMap); if (!bgHex) continue;
  for (const fg of TEXT_TOKENS) {
    const fgHex = resolveVariable(fg, tmap, paletteMap); if (!fgHex) continue;
    const ratio = contrastRatio(fgHex, bgHex);
    const status = classify(ratio);
    results.push({ theme, fg, bg, fgHex, bgHex, ratio, status });
  }
}
```
Add a parallel `STATUS_ICON_TOKENS = ['--green','--orange','--red']` × `['--surface2','--surface3']` loop with a `>= 3.0` pass test. Already-exported helpers `hexToRgb`, `contrastRatio`, `resolveVariable`, `classify` (`:42-48, 79-93, 111-115`) are reusable as-is — the unit test imports them.

**Run command:** `node scripts/contrast-audit.mjs` (the `import.meta.url === process.argv[1]` guard at `:296-298` runs it only when invoked directly).

---

### `scripts/contrast-audit.test.mjs` (test) — MODIFY

**Analog:** itself + `scripts/flags.test.mjs`.

**Existing import + assertion style to extend** (`contrast-audit.test.mjs:1-10, 29-37`):
```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hexToRgb, relativeLuminance, contrastRatio, mixColors,
         parseCssVariables, resolveVariable } from './contrast-audit.mjs';

test('contrastRatio of white vs black is 21', () => {
  const ratio = contrastRatio('#ffffff', '#000000');
  assert.ok(Math.abs(ratio - 21) < 0.1, `expected 21, got ${ratio}`);
});
```

**Add status-icon 3:1 assertions** for the failing-in-Light pairs the research computed (`03-RESEARCH.md:294`): assert that the chosen icon rendering (`var(--text)` stroke) clears 3:1 on `--surface2`/`--surface3` in all three themes, and document that a solid green/orange fill in Light would fail:
```javascript
// STATUS-05: status-icon stroke must clear the 3:1 graphical-object floor in every theme
test('STATUS-05: --text icon stroke ≥ 3:1 on Light --surface2 (green/orange would fail as solid)', () => {
  // Light --text #1a1d27 on --surface2 #eceef4 → ~13:1; solid --green #16a34a → 2.84:1 (FAIL)
  assert.ok(contrastRatio('#1a1d27', '#eceef4') >= 3.0);
  assert.ok(contrastRatio('#16a34a', '#eceef4') < 3.0); // documents why the stroke fallback is mandatory
});
```
Use the exact hex literals from the v1.0 token tables in `03-UI-SPEC.md:72-77` / `03-RESEARCH.md:294` so the test pins the documented ratios.

---

## Shared Patterns

### Pattern: Pure-logic module + byte-identical inline copy (no-build testability)
**Source:** `scripts/flags.mjs` ↔ `frontend/index.html:10297-10354`
**Apply to:** `scripts/system-rollup.mjs` ↔ `frontend/index.html`
The `.mjs` is the testable source of truth; the inline copy keeps the single-file frontend working with no build step. Header comment enforces the sync contract. Tests import only the `scripts/` copy.

### Pattern: Node built-in test runner (zero framework install)
**Source:** `scripts/flags.test.mjs:1-9`, `scripts/contrast-audit.test.mjs:1-10`
**Apply to:** `scripts/system-rollup.test.mjs`, `scripts/contrast-audit.test.mjs`
`import { test } from 'node:test'; import assert from 'node:assert/strict';`. Section-banner comments, requirement IDs in test titles, one behavior per `test()`. **Run named files** (`node --test scripts/system-rollup.test.mjs scripts/flags.test.mjs scripts/contrast-audit.test.mjs`) — see Gotcha below.

### Pattern: Theme-aware CSS variables only (no hex literals in component CSS)
**Source:** `frontend/index.html:536-584` (`.status-chip`), `1284-1296` (`.folio-status-row`), `03-UI-SPEC.md:67-93`
**Apply to:** all new chip/popover/icon CSS
Reuse `--surface2/--surface3/--border/--text/--text-dim/--accent/--accent-dim/--green/--orange/--red`. Hex literals appear ONLY in the `:root`/theme token blocks and in the audit/test files.

### Pattern: `textContent` for backend-sourced strings (V5 output encoding)
**Source:** `frontend/index.html:4028` (`setChip` uses `detailEl.textContent`)
**Apply to:** every popover row rendering `f.message`/`e.message`/`s.message`/provider/version
Never `innerHTML` with interpolated backend strings (DOM-XSS). Use `textContent`/safe DOM APIs.

### Pattern: Fixed-position overlay anchored to the header
**Source:** `frontend/index.html:570-583` (`data-tooltip` `position: fixed; top: 44px; z-index: 100`)
**Apply to:** `#systemStatusPopover` (D-01 — avoids header reflow)

### Pattern: Reuse existing keyboard/Escape plumbing
**Source:** `frontend/index.html:10388-10411` (Escape handler + `.status-chip.clickable` Enter/Space)
**Apply to:** System chip open/close — extend, don't duplicate (Don't-Hand-Roll table, `03-RESEARCH.md:261-273`).

---

## No Analog Found

None — every file in scope has a strong in-repo analog. The only genuinely new logic is the pure `computeRollup`/`normalizeSubsystems`/`chipLabel` trio, and even that follows the `scripts/flags.mjs` shape exactly. The accessible-disclosure popover markup/JS has no prior in-repo instance, but RESEARCH.md provides ready-to-copy code (`03-RESEARCH.md:173-225`) grounded in the WAI-ARIA disclosure pattern; the styling/positioning reuses the `data-tooltip` and `.folio-status-row` analogs above.

---

## Gotchas for the Planner / Executor

1. **`node --test scripts/` (directory form) currently FAILS** — not because of a test, but because importing `contrast-audit.mjs` triggers its top-level... actually its `runAudit()` only runs under the direct-invoke guard, yet the directory-form run fails today (verified). Run **named files**: `node --test scripts/system-rollup.test.mjs scripts/flags.test.mjs scripts/contrast-audit.test.mjs`. Fixing the stale report path in `contrast-audit.mjs:200` (creating/targeting an existing dir) is the likely fix that also lets the directory form pass — verify after the path fix.
2. **LLM is a hard boundary (STATUS-06).** Do not touch `chipLLM` markup (`:2981-2986`), `onLLMChipClick()` (`:5031`), `updateOllamaChip()`, the `d.llm` branch (`:4100-4118`), or the `setChip('chipLLM', ...)` calls in the Ollama path (`:5016-5026`). Exclude LLM from `normalizeSubsystems`.
3. **Keep `setChip()` (`:4021`).** LLM + Ollama still call it. Add new render functions; don't replace it.
4. **D-05/D-06 mapping lives in `normalizeSubsystems` only.** Standby/Update affect a row's `annotation`, never its `tier`. `computeRollup` stays a dumb worst-of-four reducer.
5. **No external references to the old chip IDs** outside `index.html` (verified via grep across `*.py`/`*.mjs`/`*.js`). Safe to remove `chipBackend`/`chipFolio`/`chipEmbedding`/`chipSpacy` once `checkHealth()` is refactored.
6. **Preserve the FOLIO update toast** (`_lastFolioUpdateAt`, `:4074-4081`) through the refactor.

---

## Metadata

**Analog search scope:** `scripts/` (flags.mjs, flags.test.mjs, contrast-audit.mjs, contrast-audit.test.mjs), `frontend/index.html` (markup/CSS/JS), `backend/app/api/routes/health.py` (response shape only — backend unchanged this phase).
**Files scanned:** 6 read in full or in targeted ranges; grep across `*.py`/`*.mjs`/`*.js` for chip-ID references.
**Backend confirmation:** `/health` returns `{status:"ok"}`; `/health/detail` returns `folio_ontology`/`embedding`/`spacy`/`llm` with `status ∈ {ready, not_loaded, error}` and FOLIO `update_status` (`health.py:42-139`). No backend changes needed.
**Pattern extraction date:** 2026-05-22
