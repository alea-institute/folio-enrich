---
phase: 1
slug: css-variable-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend), Chrome DevTools MCP (frontend visual) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && .venv/bin/python -m pytest tests/ -q --tb=line` |
| **Full suite command** | `cd backend && .venv/bin/python -m pytest tests/ -v` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && .venv/bin/python -m pytest tests/ -q --tb=line`
- **After every plan wave:** Run full suite + screenshot comparison
- **Before `/gsd:verify-work`:** Full suite must be green + visual verification
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | CSSF-01 | grep | `grep -c '#[0-9a-fA-F]' frontend/index.html` (CSS section only) | N/A | ⬜ pending |
| 01-01-02 | 01 | 1 | CSSF-02 | grep | `grep -c 'var(--' frontend/index.html` | N/A | ⬜ pending |
| 01-02-01 | 02 | 1 | CSSF-03 | grep | `grep 'data-theme' frontend/index.html` | N/A | ⬜ pending |
| 01-02-02 | 02 | 1 | CSSF-04 | grep | `grep 'data-theme="dark"' frontend/index.html` | N/A | ⬜ pending |
| 01-02-03 | 02 | 1 | CSSF-05 | grep | `grep 'data-theme="light"' frontend/index.html` | N/A | ⬜ pending |
| 01-02-04 | 02 | 1 | CSSF-06 | grep | `grep 'data-theme="mixed"' frontend/index.html` | N/A | ⬜ pending |
| 01-03-01 | 03 | 2 | CSSF-07 | visual | Screenshot comparison of branch spans | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* Backend tests verify pipeline logic; CSS variable migration is verified via grep and visual screenshot comparison.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mixed mode visual identity | CSSF-06 | Visual comparison of before/after screenshots | Take screenshot before migration, compare after. Must be pixel-identical |
| Branch color legibility | CSSF-07 | Requires human judgment on color legibility | View annotation spans with multiple branch colors in all 3 themes |
| Theme switching instant | Success Criteria #2 | Requires switching `data-theme` attribute in browser | Use Chrome DevTools to toggle `data-theme` and verify instant color change |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
