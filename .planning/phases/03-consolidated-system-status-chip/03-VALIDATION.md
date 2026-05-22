---
phase: 03
slug: consolidated-system-status-chip
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` § Validation Architecture. Frontend-only phase (single-file vanilla JS, no build step); pure status logic is extracted into an importable `.mjs` so it can be unit-tested with Node's built-in runner. UI/accessibility behaviors are verified by automated contrast audit + manual UAT across the three themes.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node built-in test runner (`node --test`, existing `scripts/*.test.mjs` precedent, e.g. Phase 02's `scripts/flags.test.mjs`) + manual UAT via Chrome DevTools MCP |
| **Config file** | none — test files are `scripts/*.test.mjs` run via `node --test scripts/` |
| **Quick run command** | `node --test scripts/` |
| **Full suite command** | `node --test scripts/` + `node scripts/contrast-audit.mjs` + `cd backend && .venv/bin/python -m pytest tests/ -v` (backend unchanged — regression guard) |
| **Estimated runtime** | ~10–15 seconds (node tests + audit; backend suite separate) |

---

## Sampling Rate

- **After every task commit:** Run `node --test scripts/` (rollup + contrast unit tests) — < 5 s
- **After every plan wave:** Run `node scripts/contrast-audit.mjs` (zero FAILs incl. new status-icon pairs) + `node --test scripts/`
- **Before `/gsd:verify-work`:** Full suite green + manual UAT checklist complete across Dark / Light / Mixed
- **Max feedback latency:** 5 seconds (unit), ~15 seconds (full)

---

## Per-Task Verification Map

> Task IDs are assigned during planning; rows below map requirements → test type. The planner MUST attach each row's automated command (or manual-UAT reference) to the task(s) that satisfy the requirement.

| Plan/Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-----------|-------------|-----------------|-----------|-------------------|-------------|--------|
| Wave 0 | STATUS-02, STATUS-03 | N/A | unit | `node --test scripts/system-rollup.test.mjs` | ❌ W0 | ⬜ pending |
| Wave 0 | STATUS-05 (icon ≥3:1, all themes) | N/A | unit | `node --test scripts/contrast-audit.test.mjs` | ⚠️ extend | ⬜ pending |
| Wave 0/1 | STATUS-05 (popover body ≥4.5:1; report path correct) | N/A | automated | `node scripts/contrast-audit.mjs` | ✅ extend+fix path | ⬜ pending |
| Wave 1 | STATUS-01, STATUS-04 | render values via `textContent`, never `innerHTML` of `/health/detail` message strings (DOM-XSS) | manual UAT | Chrome DevTools MCP (checklist below) | n/a | ⬜ pending |
| Wave 1 | STATUS-05 (keyboard + SR) | N/A | manual UAT | Chrome DevTools MCP + keyboard/SR | n/a | ⬜ pending |
| Wave 1 | STATUS-06 (LLM chip untouched) | N/A | manual UAT | Chrome DevTools MCP | n/a | ⬜ pending |
| Wave 1 | STATUS-07 (no header overlap) | N/A | manual UAT | Chrome DevTools MCP across widths | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/system-rollup.mjs` — extract pure, exported `normalizeSubsystems()` (Standby/Update→green per D-05/D-06), `computeRollup()` (worst-of-four red>orange>green), and `chipLabel()` ("System" / "System: {Subsystem} +N"). Imported by `index.html` via `<script type="module">` to avoid logic drift (mirrors Phase 02's `scripts/flags.mjs`).
- [ ] `scripts/system-rollup.test.mjs` — unit tests for the three pure functions; covers STATUS-02, STATUS-03.
- [ ] Extend `scripts/contrast-audit.mjs` — add status-icon-as-graphical-object 3:1 checks for green/orange/red on `--surface2`/`--surface3` across all three themes (current audit only covers `--text`/`--text-dim`/`--accent` foregrounds — a coverage gap that would falsely report 0 FAILs); **fix the stale report path** (`contrast-audit.mjs:~200` writes to `03-accessibility-component-polish/`).
- [ ] `scripts/contrast-audit.test.mjs` — assert the new status-icon pairs pass 3:1 (and that Light-theme green/orange require the `--text` stroke fallback — see Manual-Only note).
- [ ] No framework install needed (Node built-in test runner already in use).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Quiet-green at rest | STATUS-02 | Visual + live backend state | Fresh load → chip shows check icon + "System" (green); popover lists 4 rows; FOLIO/Embedding read "Standby — loads on first use" but chip stays green |
| Expand + metric preservation | STATUS-01, STATUS-04 | Visual + interaction | Click and Enter/Space both open; all of today's metrics present (concepts loaded, labels indexed, vectors indexed, spaCy version, provider); FOLIO row "Manage FOLIO" opens the existing modal unchanged (D-08) |
| Worst-status + naming + overflow | STATUS-03 | Requires degraded state | Mock `/health/detail` with `spacy.status:"error"` → chip red, label "System: spaCy"; add a 2nd failure → "System: spaCy +1"; popover names all failures |
| Live update while open | D-03 | Timing/interaction | With popover open, let a poll change FOLIO Standby→ready → row + rollup update in place; focus not stolen; no screen-reader spam |
| Keyboard + screen-reader access | STATUS-05 | Assistive-tech behavior | Keyboard-only open/navigate/close (Enter/Space/Escape/outside-click/Tab); focus moves into popover on open, restores to chip on close; SR announces label + expanded state + each row "{Subsystem}: {status}, {metric}"; status conveyed by icon shape + word (not color alone) |
| Icon contrast in Light theme | STATUS-05 | Computed FAIL must be visually confirmed | `node scripts/contrast-audit.mjs` → zero FAILs; visually confirm green/orange icons in **Light theme** specifically use the `--text` stroke (Pitfall 1 — they fail 3:1 without it) |
| LLM chip unchanged | STATUS-06 | Regression check | LLM chip still separate, still configures via `onLLMChipClick()` |
| No header overlap | STATUS-07 | Layout, post-document-load | After a document loads (layer chips visible once `headerControls` shows), `#statusBar` does not overlap `#layerToggleBar` at normal desktop widths |

---

## Validation Sign-Off

- [ ] All tasks have an `<automated>` verify or a Wave 0 dependency (pure logic) / documented manual-UAT reference (UI/a11y)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`system-rollup.mjs` + tests; contrast-audit status-icon extension + path fix)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (unit) / ~15s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
