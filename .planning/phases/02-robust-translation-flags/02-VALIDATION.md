---
phase: 02
slug: robust-translation-flags
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `node:test` (built into Node, no install) for extracted flag logic; pytest for the existing backend suite |
| **Config file** | none — flag logic extracted to a testable `scripts/flags.mjs` (per RESEARCH §architecture) |
| **Quick run command** | `node --test test/` |
| **Full suite command** | `node --test test/ && (cd backend && .venv/bin/python -m pytest tests/ -q)` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `node --test test/`
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite green + manual UAT (below) complete
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

> Planner fills exact task IDs. The locale→flag/label/fallback logic must be extracted into a pure module (`scripts/flags.mjs`) so it is unit-testable without a browser.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | FLAG-01 | — | N/A | unit | `node --test test/flags.test.mjs` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | FLAG-03 | — | aria-label = "Language (Country)" via Intl.DisplayNames | unit | `node --test test/flags.test.mjs` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | FLAG-04 | — | unknown locale → country-code fallback string, never empty | unit | `node --test test/flags.test.mjs` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | FLAG-01 (D-03) | — | language-only locale maps he→IL/hi→IN/ja→JP/zh→CN/es→ES/fr→FR | unit | `node --test test/flags.test.mjs` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/flags.mjs` — extract pure locale→{svgKey, fallbackCode, label} logic from `localeToFlag` so it is testable in `node:test`.
- [ ] `test/flags.test.mjs` — `node:test` stubs covering FLAG-01 (all 12 countries resolve to an SVG key), FLAG-03 (label format), FLAG-04 (fallback), and D-03 (language-only mapping).

---

## Manual-Only Verifications

> FLAG-01 (OS rendering) and FLAG-02 (blocker resilience) are inherently browser/OS-level and cannot be asserted in `node:test` — they require manual UAT.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Flags render as graphics on Windows (no boxed "GB"/"ES") | FLAG-01 | OS font/emoji behavior; not observable in Node | Open the app on Windows/Chrome, open a concept with translations, confirm flag graphics render (not letter pairs). |
| Flags display with Privacy Badger enabled | FLAG-02 | Requires a real content blocker + browser | Enable Privacy Badger, reload, confirm every flag still displays; Network tab shows zero flag-related external requests. |
| Hairline border keeps white flags (JP/CN) visible in all 3 themes | FLAG-01/D-04 | Visual contrast judgement across themes | Toggle Dark/Light/Mixed; confirm JP/CN flags have a visible edge on each background. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
