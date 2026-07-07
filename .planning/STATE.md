---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Header & Status UX
status: milestone_complete
stopped_at: Milestone complete (Phase 03 was final phase)
last_updated: 2026-05-23T02:45:57.985Z
last_activity: 2026-05-22 -- Phase 03 execution started
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 5
  completed_plans: 6
  percent: 50
---

> **⚠️ POINTER (refreshed 2026-07-07): this GSD `STATE.md` is STALE — it stops at milestone v1.2 (Header & Status UX, May 2026).**
> Active planning moved OUT of `.planning/` after v1.2. The current source of truth is **`docs/plans/*.md`** (dated-prefix convention) plus **`docs/HANDOFF-*.md`**.
> Latest completed plan: **`docs/plans/2026-07-03-001-feat-canon-branch-roots-and-pos-salvage-plan.md`** (status: completed; deployed PROD `1fdbf8e`). It shipped Canon branch-root fixes (WS-A implicit roots → 3→7 roots), search substring penalty (WS-B #26), NER cross-validation default-off (WS-C #27), branch-label unify (WS-D #28), WS-E canonical root-label snapping (#30 + re-bake #31).
> Post-v1.2 work NOT reflected below: multi-ontology registry + Canon enablement, BYOK, backup-candidate semantic filter, WordIngestor `.docx` `<w:sdt>` handling.
> **Open follow-up (C4, 2026-07-07):** `ner_cross_validation_enabled` stays `False` — flipping it requires an F1/recall gold-set eval that does not yet exist (`test_disambiguation_eval.py` is an IRI-assertion regression, not an F1 harness). Building that harness + a spend-gated baseline run is a `[CE]` task; logged to the Lane-5 QA queue.

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Make legal documents semantically rich — every recognizable concept, individual, property, and triple tagged with a FOLIO IRI, in a WCAG AA-compliant UI.
**Current focus:** Milestone complete

## Current Position

Phase: 03
Plan: Not started
Status: Milestone complete
Last activity: 2026-05-25 - Completed quick task 260525-c1x: latest LLMs + default Gemini 3 Flash

Progress: [██████████] 100%

## Phases (v1.2)

- [x] Phase 02: Robust translation flags — FLAG-01..04 (UI hint: yes) — COMPLETE (UAT approved)
- [ ] Phase 03: Consolidated system status chip — STATUS-01..07 (UI hint: yes; gets a `/gsd:ui-phase` design contract)

## Accumulated Context

### Decisions

- v1.2 scope fixed at exactly two phases (decided with user): Phase 02 = translation-flags bug, Phase 03 = system-status-chip feature.
- Phase numbering continues from v1.1 (last phase = 01); v1.2 starts at Phase 02. Numbers are NOT reset.
- All 11 requirements (FLAG-01..04, STATUS-01..07) map to exactly one phase. 100% coverage, no orphans.
- Phase 02 implementation lives in single-file `frontend/index.html`: `localeToFlag()` near line 10286, translation pill render near line 8343. No build step, no new dependencies.
- Phase 03 uses existing `/health` and `/health/detail` data — no new backend endpoints. LLM chip stays a separate actionable control (not folded in).
- Phase 03 will get a `/gsd:ui-phase` design contract before planning.
- [Phase 02]: Phase 02 flags: vendored inline flag-icons SVGs (MIT), ES/MX trimmed to stripe-only variants; zero external requests survive content blockers (FLAG-01/02).
- [Phase 02]: Language-only locales resolve to representative country flags before the BUNDLED check (he->IL, hi->IN, ja->JP, zh->CN); fixes the 'HE'->blank bug (D-03).

### Pending Todos

- Plan Phase 02 (`/gsd:plan-phase 02`).
- Run `/gsd:ui-phase` for Phase 03 before planning it.

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260522-uot | Consolidate Nouns/Verbs/Individuals layer toggles under one "Annotations" disclosure chip (Parts of Speech kept separate) | 2026-05-23 | 9369907 | [260522-uot-consolidate-nouns-verbs-individuals-laye](./quick/260522-uot-consolidate-nouns-verbs-individuals-laye/) |
| 260523-box | Shorten UI labels: Show Thinking→Thinking, Debug Mode→Debug, pipeline stages to one-word forms (fit on one line) | 2026-05-23 | (see commit) | [260523-box-shorten-ui-labels-show-thinking-debug-mo](./quick/260523-box-shorten-ui-labels-show-thinking-debug-mo/) |
| 260525-c1x | Update providers to latest LLMs (GPT-5.5, Claude Opus 4.7, Gemini 3.5 Flash / 3.1 Flash Lite) and default to Gemini 3 Flash (top of list) | 2026-05-25 | (see commit) | [260525-c1x-update-providers-to-latest-llms-and-defa](./quick/260525-c1x-update-providers-to-latest-llms-and-defa/) |
| 260525-ppl | Expand Process Pipeline node labels from 3-letter abbreviations to full words (Ingest, Normalize, String, LLM, Resolve, Judge, Match, Finalize) | 2026-05-25 | (see commit) | [260525-ppl-expand-pipeline-stage-labels-full-word](./quick/260525-ppl-expand-pipeline-stage-labels-full-word/) |

## Session Continuity

Last session: 2026-05-22T22:50:39.644Z
Stopped at: Phase 03 UI-SPEC approved
Resume file: .planning/phases/03-consolidated-system-status-chip/03-UI-SPEC.md
Next step: `/gsd:verify-work 02` (manual acceptance for FLAG-01..04)
