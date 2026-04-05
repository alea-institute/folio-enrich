---
phase: 2
slug: theme-switching-js-integration
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend regression), structural grep/awk (frontend) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && .venv/bin/python -m pytest tests/ -q --tb=line` |
| **Full suite command** | `cd backend && .venv/bin/python -m pytest tests/ -v` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && .venv/bin/python -m pytest tests/ -q --tb=line`
- **After every plan wave:** Run full suite + visual verification via Chrome DevTools screenshots
- **Before `/gsd:verify-work`:** Full suite must be green + visual theme toggle test
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | THSW-01,02,03,04,05,06,JSIT-02 | structural | `grep -c 'function setTheme' frontend/index.html` | N/A | ⬜ pending |
| 02-01-02 | 01 | 1 | THSW-01,02 | visual | Screenshot comparison of toggle + settings | N/A | ⬜ pending |
| 02-02-01 | 02 | 2 | JSIT-01,03 | structural | `grep -c 'BRANCH_COLORS' frontend/index.html` returns 0 | N/A | ⬜ pending |
| 02-02-02 | 02 | 2 | JSIT-01,02,03 | visual | Theme toggle with enriched document | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*None — this phase modifies existing code patterns. No new test infrastructure needed. The frontend has no automated JS test framework; all verifications are structural (grep/awk) and visual (screenshot).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Theme toggle cycles correctly | THSW-01 | Visual + interaction | Click toggle, verify Dark→Light→Mixed→Dark cycle |
| Settings swatches update theme | THSW-02 | Visual + interaction | Open settings, click each swatch, verify theme changes |
| No flash on reload | THSW-04 | Timing-sensitive visual | Set theme, reload page, verify no wrong-theme flash |
| OS preference default | THSW-05 | Requires clearing localStorage | Clear storage, reload, verify matches OS preference |
| Canvas re-renders on theme switch | JSIT-02 | Visual canvas inspection | Open graph, switch themes, verify colors update |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-05
