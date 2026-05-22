---
phase: 03-consolidated-system-status-chip
plan: 02
subsystem: accessibility-tooling
tags: [wcag, contrast-audit, status-icon, status-05, node-test]
requires:
  - scripts/contrast-audit.mjs (existing WCAG audit + exported helpers)
provides:
  - "STATUS-05 deterministic gate: status-icon 3:1 graphical-object audit"
  - "Corrected audit report path (Phase 03 dir)"
  - "Regression-pinned contrast facts for the --text stroke fallback"
affects:
  - "Wave 2/3 frontend work — must stroke Light-theme status glyphs at --text"
tech-stack:
  added: []
  patterns:
    - "Node built-in test runner (node:test), zero-dependency"
    - "WCAG 1.4.11 graphical-object 3:1 floor distinct from text 4.5/3.0"
key-files:
  created: []
  modified:
    - scripts/contrast-audit.mjs
    - scripts/contrast-audit.test.mjs
decisions:
  - "Status-icon contrast audited at a 3:1 floor (classifyIcon), never weakened to hide the documented Light-theme FAILs."
  - "Generated audit report (03-AUDIT-REPORT.md) left untracked — regenerable build output; no audit report was ever tracked in this repo."
metrics:
  duration: ~12 min
  completed: 2026-05-22
  tasks: 3
  files: 2
  commits: 3
---

# Phase 03 Plan 02: Status-Icon WCAG Audit Gate Summary

Extended the zero-dependency WCAG audit to catch the STATUS-05 risk — solid `--green`/`--orange` status icons fail the 3:1 graphical-object floor in the Light theme — and pinned the computed ratios so the `--text` stroke fallback cannot regress.

## What Was Built

- **Task 1 (`d92f666`):** Fixed the stale `reportPath` in `scripts/contrast-audit.mjs` from the non-existent `03-accessibility-component-polish` dir to the real `03-consolidated-system-status-chip` dir. Removes the runtime path error when `runAudit()` writes its markdown report.
- **Task 2 (`58bb80a`):** Added `STATUS_ICON_TOKENS = ['--green','--orange','--red']` × `STATUS_ICON_BG_TOKENS = ['--surface2','--surface3']` audit loop with a new `classifyIcon()` applying a strict 3:1 floor (WCAG 1.4.11), distinct from the text 4.5/3.0 thresholds. New report section, console FAIL list (with "stroke at --text in Wave 3" guidance), and a STATUS-05 recommendation surface the failures.
- **Task 3 (`5f1492a`):** Added a STATUS-05 section to `scripts/contrast-audit.test.mjs` pinning the exact v1.0 hex literals — `--text` stroke clears 3:1; solid green/orange fail 3:1 on `--surface2`/`--surface3`.

## Status-Icon Pairs That FAIL as Solid Fills (Wave 3 MUST stroke these at --text)

| Theme       | Icon Color | Surface          | Ratio   | Status |
|-------------|-----------|------------------|---------|--------|
| light       | --green   | --surface2 (chip)    | 2.84:1 | FAIL  |
| light       | --orange  | --surface2 (chip)    | 2.75:1 | FAIL  |
| light       | --green   | --surface3 (popover) | 2.62:1 | FAIL  |
| light       | --orange  | --surface3 (popover) | 2.53:1 | FAIL  |
| mixed-light | --green   | --surface2 (chip)    | 2.84:1 | FAIL  |
| mixed-light | --orange  | --surface2 (chip)    | 2.75:1 | FAIL  |
| mixed-light | --green   | --surface3 (popover) | 2.62:1 | FAIL  |
| mixed-light | --orange  | --surface3 (popover) | 2.53:1 | FAIL  |

All FAILs are Light-surface green/orange (8 total). `--red` (all themes) and Dark/Mixed green/orange already clear 3:1. **Wave 3 resolution:** stroke each status glyph at `var(--text)` (Light `--text` #1a1d27 → ≥13:1) and use the status color only as a secondary fill — the shape carries the contrast in every theme.

## Verification Results

- `node scripts/contrast-audit.mjs` — runs, writes report to the Phase 03 dir, reports 296 pairs / 8 failures, lists the 8 Light-surface icon FAILs.
- `node --test scripts/contrast-audit.test.mjs scripts/flags.test.mjs` — 27 pass, 0 fail.
- `grep -c "03-accessibility-component-polish" scripts/contrast-audit.mjs` — returns 0.

## Deviations from Plan

### [Rule 1 - Bug] Directory-form test invocation: Node 25 semantics differ from the plan's assumption

- **Found during:** Task 1 verification.
- **Issue:** The plan's must-have ("`node --test scripts/` (directory form) no longer fails because of the stale report path") assumed `node --test <dir>` discovers test files inside the directory. On the installed runtime (**Node v25.2.1**), `node --test scripts/` instead tries to *run* `scripts` as a module and fails with `MODULE_NOT_FOUND` — a path-resolution error entirely unrelated to the report path. The report-path fix does not (and cannot) change this Node behavior.
- **Root cause analysis:** The named-file form (`node --test scripts/contrast-audit.test.mjs`) already passed before the path fix, because the test only imports pure helpers and never calls `runAudit()`. So the stale report path was never the cause of any directory-form failure on this Node version — it would only error at `runAudit()` write time (the actual bug the path fix corrects).
- **Resolution:** The report-path fix is still correct and required (acceptance criteria met: grep returns 0, audit writes to Phase 03 dir without a path error). The intended "directory discovery" behavior is achieved on Node 25 via the glob form **`node --test 'scripts/**/*.test.mjs'`**, which discovers and runs all test files and exits 0 (27 pass, 0 fail).
- **Files modified:** none beyond the planned `scripts/contrast-audit.mjs` change.
- **Action for Wave 3 / CI:** use `node --test 'scripts/**/*.test.mjs'` (or list test files explicitly) for the full-suite gate, not the bare directory form, on Node ≥ 22's stricter `--test <path>` semantics.

### [Rule 3 - Blocking] mixed-light theme also surfaces icon FAILs (expected, documented)

- **Found during:** Task 2.
- **Note:** The audit's `mixed-light` pseudo-theme (Mixed mode's light-panel overrides) inherits the Light `--green`/`--orange`/surface tokens, so it correctly reports the same 4 FAILs as `light`. This is correct coverage, not a defect — Wave 3's stroke fallback covers both. Documented here so the FAIL count of 8 (not 4) is expected.

## Generated-Artifact Note

`node scripts/contrast-audit.mjs` writes `.planning/phases/03-consolidated-system-status-chip/03-AUDIT-REPORT.md`. This file is **deterministically regenerable** and was left untracked — no audit report has ever been tracked in this repo (the prior `03-accessibility-component-polish` report path never existed). Regenerate any time with `node scripts/contrast-audit.mjs`.

## TDD Gate Compliance

Task 3 is `tdd="true"` but pins the contract of an already-shipped pure function (`contrastRatio`), so it is a regression-pinning test, not a new-behavior RED→GREEN build. The GREEN implementation (`contrastRatio`) shipped in v1.0. A single `test(...)` commit (`5f1492a`) is the correct artifact; there is no new feature commit gated behind it. No fail-fast violation: the assertions pass against the existing correct math, which is the intended invariant.

## Known Stubs

None.

## Threat Flags

None — zero-dependency local audit/test script, no network, no untrusted input. Confirms threat register T-03-02 (accept) and T-03-SC (zero installs).

## Self-Check: PASSED

- FOUND: scripts/contrast-audit.mjs (modified — STATUS_ICON_TOKENS, classifyIcon, audit loop, report section)
- FOUND: scripts/contrast-audit.test.mjs (modified — STATUS-05 section, 4 assertions)
- FOUND commit d92f666 (Task 1)
- FOUND commit 58bb80a (Task 2)
- FOUND commit 5f1492a (Task 3)
