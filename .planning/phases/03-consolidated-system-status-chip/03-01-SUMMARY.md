---
phase: 03-consolidated-system-status-chip
plan: 01
subsystem: frontend-status-rollup
tags: [status-chip, rollup, tdd, accessibility, wcag]
requires:
  - "scripts/flags.mjs (export-style + node:test analog precedent)"
  - "backend /health/detail response shape (read-only)"
provides:
  - "scripts/system-rollup.mjs — pure exported normalizeSubsystems / computeRollup / chipLabel"
  - "TIER_RANK + the byte-identical-ready rollup contract for Wave 2 inline copy"
affects:
  - "Wave 2 (paste byte-identical non-export copy into frontend/index.html)"
  - "Wave 3 (render rows; enforce textContent DOM-XSS mitigation)"
tech-stack:
  added: []
  patterns:
    - "Pure exported ESM module mirroring scripts/flags.mjs (no DOM, no non-node imports, no default export)"
    - "node:test + node:assert/strict unit coverage (no test-framework install)"
    - "Single-place D-05/D-06 tier mapping in normalizeSubsystems; computeRollup is tier-agnostic"
key-files:
  created:
    - "scripts/system-rollup.mjs"
    - "scripts/system-rollup.test.mjs"
  modified: []
decisions:
  - "backendUp=false maps ALL four rows to red; Backend reads 'Offline — cannot reach backend', dependents read 'Backend offline' (mirrors index.html:4044-4050; 'gray' is not a rollup tier so red is used)"
  - "normalizeSubsystems row shape is { key, name, tier, statusWord, metric, annotation?, action? }"
  - "FOLIO row alone carries action: 'manage-folio' (D-08); no other row has an action key"
metrics:
  duration: "~2 min"
  completed: "2026-05-22"
  tasks: 3
  files: 2
  tests: 44
---

# Phase 03 Plan 01: System Status Rollup Logic Summary

Pure, exported, unit-tested status-rollup module (`scripts/system-rollup.mjs`) that is the single source of truth for the consolidated System chip: worst-of-four rollup (STATUS-03), quiet-green-at-rest mapping (STATUS-02 / D-05 / D-06), and the "System" / "System: {Subsystem} +N" chip labels (D-10 / D-11). LLM is excluded from the rollup (STATUS-06).

## What Was Built

- **`scripts/system-rollup.mjs`** — four exports, no default export, no DOM, no imports beyond inline helpers:
  - `TIER_RANK = { green: 0, orange: 1, red: 2 }` (D-07).
  - `computeRollup(subsystems)` → `{ tier, worstName, overflow }`; `overflow = max(0, failCount - 1)`. Tier-agnostic about Standby/Update (those are mapped upstream).
  - `chipLabel(rollup)` → `"System"` when green (D-10), else `"System: {worstName}"` plus ` +{overflow}` when overflow > 0 (D-11).
  - `normalizeSubsystems(detail, backendUp)` → fixed-order 4-row array. Encodes D-05 (`not_loaded` → green + Standby annotation) and D-06 (`update_available`/`update_in_progress` → green + Update/Updating annotation) in ONE place; `error` → red; LLM never read.
- **`scripts/system-rollup.test.mjs`** — 23 tests (node:test) covering STATUS-02/03/04/06, D-05/06/07/08, worst-of-four ranking, overflow counting, metric preservation, and the backend-down path. Combined with flags + contrast-audit suites: 44 tests pass.

## normalizeSubsystems Row Contract (for Wave 2/3)

Returns exactly 4 rows in fixed order: Backend, FOLIO, Embedding, spaCy. Each row:

| Field | Type | Notes |
|-------|------|-------|
| `key` | string | `'backend' \| 'folio' \| 'embedding' \| 'spacy'` (lowercase, stable) |
| `name` | string | `'Backend' \| 'FOLIO' \| 'Embedding' \| 'spaCy'` (display) |
| `tier` | string | `'green' \| 'red'` — Standby/Update stay green (D-05/D-06) |
| `statusWord` | string | terse word: Running / Ready / Standby / Error / Offline (STATUS-05 text-not-color) |
| `metric` | string | preserved metric string (STATUS-04), verbatim from Metric Preservation Map |
| `annotation` | string? | informational sub-line (Standby / Update available / Updating…); absent when none |
| `action` | string? | `'manage-folio'` on FOLIO row ONLY (D-08); absent on all other rows |

Exact metric strings (verbatim, copy into the inline copy):
- Backend ready: `"Running"`; Backend offline: `"Offline — cannot reach backend"`.
- FOLIO ready: `"{concepts} concepts, {labels_indexed} labels indexed"` (both `.toLocaleString()`); standby/offline metric: `"Standby — loads on first use"` / `"Backend offline"`; error: `"FOLIO error — {message}"`.
- Embedding ready: `"{provider}, {index_size} vectors indexed"`; standby: `"Standby — loads on first use"`; error: `"Embedding error — {message}"`.
- spaCy ready: `"spaCy {version} — EntityRuler ready"`; error: `"spaCy error — {message}"`.

Annotations: FOLIO `update_in_progress` → `"Updating…"`; `update_available` → `"Update available"`; `not_loaded` (FOLIO + Embedding) → `"Standby — loads on first use"`.

### backendUp handling decision (recorded for Wave 2/3)

`normalizeSubsystems(detail, backendUp)` takes a second boolean. The current `index.html` shows a "gray ---" placeholder when `/health` is unreachable, but `gray` is not one of the rollup tiers in `TIER_RANK`. Decision: when `backendUp === false`, ALL four rows are returned at `tier: 'red'` with `statusWord: 'Offline'`; Backend's metric is `"Offline — cannot reach backend"` and the dependents' metric is `"Backend offline"`. This makes the chip roll up to red and name Backend as the worst subsystem, which is the correct user signal when the backend is unreachable. Wave 2/3 should call `normalizeSubsystems(detail, /health-ok)` — pass `false` from the `catch` branch that currently runs index.html:4044-4050, `true` otherwise.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Failing tests for computeRollup + chipLabel (RED) | e643410 | scripts/system-rollup.test.mjs |
| 2 | Implement computeRollup + chipLabel (GREEN) | e231728 | scripts/system-rollup.mjs |
| 3 | normalizeSubsystems with D-05/D-06 mapping (RED→GREEN) | 2908406 | scripts/system-rollup.mjs, scripts/system-rollup.test.mjs |

## TDD Gate Compliance

Plan type is `tdd`. Gate sequence satisfied:
1. RED — `test(03-01)` commit e643410 (computeRollup/chipLabel tests fail; module absent).
2. GREEN — `feat(03-01)` commit e231728 (computeRollup/chipLabel pass).
3. RED→GREEN — `feat(03-01)` commit 2908406 (normalizeSubsystems tests written failing first against a throwing placeholder, then implemented to pass).
No REFACTOR commit was needed (implementation matched the RESEARCH contract on first pass).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] normalizeSubsystems placeholder added in Task 2 so the named import resolves**
- **Found during:** Task 2
- **Issue:** `scripts/system-rollup.test.mjs` (written in Task 1) imports `{ TIER_RANK, normalizeSubsystems, computeRollup, chipLabel }` at module top. ESM resolves all named imports at load time, so the Task 2 acceptance criterion (`node --test scripts/system-rollup.test.mjs` exits 0) was impossible while `normalizeSubsystems` was undefined — the whole test module failed to load with a missing-named-export error, not a normal test failure.
- **Fix:** Added a throwing `normalizeSubsystems` placeholder in Task 2 so the import resolves and the computeRollup/chipLabel tests run GREEN. Task 3 then wrote the real normalizeSubsystems tests (RED against the placeholder) and replaced the placeholder with the full implementation (GREEN), preserving the TDD cycle.
- **Files modified:** scripts/system-rollup.mjs
- **Commit:** e231728 (placeholder), 2908406 (real implementation)

**2. [Rule 3 - Blocking] Reworded a comment to satisfy the STATUS-06 grep acceptance criterion**
- **Found during:** Task 3
- **Issue:** Task 3 acceptance requires `grep -c "detail\.llm\|d\.llm" scripts/system-rollup.mjs` to return 0. A documentation comment literally read "this function never reads `detail.llm`", which the grep counted as a match (returned 1) even though no code reads the LLM field.
- **Fix:** Reworded the comment to "this function never reads the LLM subsystem". Grep now returns 0; the code never read the LLM field at any point.
- **Files modified:** scripts/system-rollup.mjs
- **Commit:** 2908406

## Verification

- `node --test scripts/system-rollup.test.mjs scripts/flags.test.mjs scripts/contrast-audit.test.mjs` → 44 tests, 44 pass, 0 fail, exit 0.
- `scripts/system-rollup.mjs` exports exactly TIER_RANK, computeRollup, chipLabel, normalizeSubsystems (4 exports, no default, no DOM, no non-inline imports).
- `grep -c "detail\.llm\|d\.llm" scripts/system-rollup.mjs` → 0 (STATUS-06 exclusion).
- normalizeSubsystems returns exactly 4 rows in fixed order Backend/FOLIO/Embedding/spaCy with no llm key.

## Known Stubs

None. The Task 2 throwing placeholder was fully replaced in Task 3; no stub remains in the shipped module.

## Self-Check: PASSED

- FOUND: scripts/system-rollup.mjs
- FOUND: scripts/system-rollup.test.mjs
- FOUND commit: e643410
- FOUND commit: e231728
- FOUND commit: 2908406
