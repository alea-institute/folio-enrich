---
phase: 02-robust-translation-flags
plan: 01
subsystem: ui
tags: [flags, svg, intl-displaynames, accessibility, vanilla-js, node-test]

# Dependency graph
requires:
  - phase: 01
    provides: theme switching infrastructure (var(--border), var(--surface3), var(--text-dim) tokens used by the flag box + fallback pill)
provides:
  - Pure testable scripts/flags.mjs module (FLAG_SVG map of 12 inline SVGs, localeToCountry, localeLabel, flagMarkup)
  - Inline-SVG translation flags in frontend/index.html replacing the emoji codepoint generator
  - Theme-aware 16x12 bordered flag box + styled country-code fallback pill
  - "Language (Country)" aria-label/title on every flag via Intl.DisplayNames
affects: [translation-pill rendering, concept detail panel, future locale/flag work]

# Tech tracking
tech-stack:
  added: [lipis/flag-icons vendored SVGs (MIT, author-time only — no runtime dependency)]
  patterns:
    - "Vendored inline SVG allowlist (FLAG_SVG const) — zero external requests, survives content blockers"
    - "Pure logic extracted to scripts/*.mjs + node:test, then inlined byte-identically into the single-file frontend so unit tests stay authoritative"
    - "Intl.DisplayNames for locale->label composition with try/catch + lang fallback"

key-files:
  created:
    - scripts/flags.mjs
    - scripts/flags.test.mjs
    - LICENSES/flag-icons-LICENSE.txt
  modified:
    - frontend/index.html

key-decisions:
  - "Vendor 10 flag-icons 4x3 SVGs verbatim (ids stripped/namespaced); author trimmed stripe-only ES/MX variants to avoid ~166 KB coat-of-arms emblems invisible at 16px (D-01b)"
  - "Resolve LANG_TO_COUNTRY (he->il, hi->in, ja->jp, zh->cn, es->es, fr->fr) BEFORE the BUNDLED check so language-only locales pick a representative flag (D-03, fixes 'HE'->blank)"
  - "Theme-aware 1px var(--border) hairline keeps white-heavy JP/CN flags visible on light/mixed themes (D-04)"

patterns-established:
  - "Pattern 1: Inline-SVG allowlist for graphics that must render offline / under content blockers"
  - "Pattern 2: mjs module is source of truth; frontend inlines a byte-identical copy (no build step)"

requirements-completed: [FLAG-01, FLAG-02, FLAG-03, FLAG-04]

# Metrics
duration: ~4min (Tasks 1-2 execution span)
completed: 2026-05-22
---

# Phase 02 Plan 01: Robust Translation Flags Summary

**Replaced the emoji-codepoint `localeToFlag` (boxed "GB"/"HE" letters on Windows, blank under Privacy Badger) with self-contained inline-SVG flags vendored from lipis/flag-icons — zero external requests, "Language (Country)" labels, language-only locale resolution, and a styled fallback pill.**

## Performance

- **Duration:** ~4 min (Task 1 commit 16:55:38 → Task 2 commit 16:58:42; Task 3 was a blocking human-verify UAT gate)
- **Started:** 2026-05-22T21:55:38Z (Task 1 commit)
- **Completed:** 2026-05-22 (finalization after user UAT approval)
- **Tasks:** 3 (2 auto + 1 checkpoint:human-verify, approved)
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments
- **scripts/flags.mjs** — pure ES module: `FLAG_SVG` (12 inline SVGs, ids stripped/namespaced, ES/MX trimmed stripe variants), `LANG_TO_COUNTRY`, `localeToCountry`, `localeLabel`, `flagMarkup`. 15 node:test assertions cover FLAG-01/03/04 + D-03 + the FLAG-02 external-token sweep.
- **frontend/index.html** — inlined the FLAG_SVG map + helpers byte-identically, removed the `localeToFlag` emoji generator, rewired `makePill` to `flagMarkup(locale)`, rewrote `.detail-trans-pill .flag` into a bordered 16x12 box, and added a `.flag-fallback` rule. See-also pills (`detail-seealso-pill`) left untouched.
- **LICENSES/flag-icons-LICENSE.txt** — retained flag-icons MIT notice; inline attribution comment added above FLAG_SVG.

## Requirement & Decision Status
- **FLAG-01 (OS render):** PASS — inline SVG renders as graphics, no codepoints/boxed letters. Unit-asserted + UAT in-browser and on Railway Dev.
- **FLAG-02 (content blocker):** PASS — zero external tokens in FLAG_SVG (unit token sweep); UAT confirmed zero flag-related requests via Network tab with a blocker enabled.
- **FLAG-03 ("Language (Country)" label):** PASS — Intl.DisplayNames-composed aria-label/title (e.g., "English (United Kingdom)", "Spanish (Mexico)"). Unit-asserted + UAT hover.
- **FLAG-04 (styled fallback):** PASS — unbundled locales render a muted uppercase code pill, never a broken glyph. Unit-asserted + UAT.
- **D-03 (language-only resolution):** PASS — he->IL, hi->IN, ja->JP, zh->CN, es->ES, fr->FR. Unit-asserted + UAT.
- **D-04 (theme-aware border):** PASS — white-heavy JP/CN flags show a visible hairline across Dark/Light/Mixed. UAT confirmed.

## Manual UAT Outcome (Task 3 — blocking human-verify)
- **Result:** APPROVED. UAT performed by the orchestrator in-browser AND by the user on Railway Dev (https://folio-enrich-production.up.railway.app).
- **Coverage:** All 5 UAT steps passed — FLAG-01 inline render, FLAG-02 zero external requests (Network tab), FLAG-03 label, FLAG-04 fallback pills, D-03 language-only resolution, D-04 theme-aware borders.

## Task Commits

1. **Task 1: testable flags.mjs module + tests + license** - `1beee1c` (feat)
2. **Task 2: wire inline SVG flags into frontend, rewrite .flag CSS** - `12d02c0` (feat)
3. **Task 3: manual UAT (FLAG-01/FLAG-02/theme contrast)** - checkpoint:human-verify, no code commit (verification gate, approved)

**Plan metadata:** (this SUMMARY commit)

## Test Results
- `node --test scripts/flags.test.mjs` — **15 pass / 0 fail**.
- `node --test scripts/*.test.mjs` (full mjs suite) — **23 pass / 0 fail**.
- `cd backend && .venv/bin/python -m pytest tests/ -q` — **674 passed, 31 deselected** (backend untouched, no regression).

## Files Created/Modified
- `scripts/flags.mjs` - Pure locale->flag logic: FLAG_SVG (12 inline SVGs), LANG_TO_COUNTRY, localeToCountry, localeLabel, flagMarkup.
- `scripts/flags.test.mjs` - 15 node:test assertions (FLAG-01/03/04, D-03, FLAG-02 token sweep).
- `LICENSES/flag-icons-LICENSE.txt` - Retained flag-icons MIT notice (Copyright (c) 2013 Panayiotis Lipiridis).
- `frontend/index.html` - Inlined FLAG_SVG + helpers, removed localeToFlag emoji generator, rewired makePill, rewrote .flag CSS box + added .flag-fallback.

## Decisions Made
None beyond the plan — D-01b/D-03/D-04 were specified in the plan and followed as written.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
- **Pre-existing backend bug surfaced during UAT (NOT this plan):** The Synonyms section of the detail panel includes foreign-language translations. This is a backend behavior unrelated to and not caused by this plan's frontend-only flag changes. It was captured as a follow-up todo at `.planning/todos/pending/synonyms-exclude-translations.md` and is out of scope here.

## User Setup Required
None - no external service configuration required (flags are vendored author-time SVGs, no runtime dependency).

## Known Stubs
None - all flag logic is wired to real locale data via flagMarkup; no placeholder/empty-data paths introduced.

## Threat Flags
None - no new security surface introduced. Flag SVGs are an author-controlled allowlist (T-02-03 accepted); translation labels keep escapeHtml and aria-label/title keep escapeAttr (T-02-01/02 mitigated); all flag pixels are inline SVG (T-02-04 mitigated, the original live bug).

## Next Phase Readiness
- Translation-flag bug closed (FLAG-01..04). Ready for Phase 03 (consolidated system status chip).
- Follow-up: `synonyms-exclude-translations` todo pending (separate backend fix).

## Self-Check: PASSED
- `scripts/flags.mjs` — FOUND
- `scripts/flags.test.mjs` — FOUND
- `LICENSES/flag-icons-LICENSE.txt` — FOUND
- `frontend/index.html` — FOUND, `function localeToFlag` absent (grep = 0 matches)
- Commit `1beee1c` — FOUND
- Commit `12d02c0` — FOUND
- Test suites green (flags.test.mjs 15/15, all *.test.mjs 23/23, backend pytest 674 passed)

---
*Phase: 02-robust-translation-flags*
*Completed: 2026-05-22*
