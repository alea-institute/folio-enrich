---
quick_id: 260523-box
description: Shorten UI labels (Show Thinking, Debug Mode) and pipeline stage names to fit on one line
date: 2026-05-23
status: complete
tags: [ui-labels, copy, header]
key-files:
  created: []
  modified:
    - frontend/index.html
---

# Quick Task 260523-box: Shorten UI labels

Display-text renames only — no logic, status keys, or behavior changed.

## What changed (frontend/index.html)

- **"Show Thinking" → "Thinking"** — button markup + the `toggleShowThinking` innerHTML rebuild (so the label stays short when toggled on/off).
- **"Debug Mode" → "Debug"** — button markup + the `toggleDebugMode` innerHTML rebuild. The "truncated by Debug Mode …" prose message was intentionally left (it names the feature in explanatory text, not the button).
- **Pipeline stage labels** (status→label map values, keys unchanged): Ingesting→Ingest, Normalizing→Normalize, Enriching→Enrich, Identifying→Identify, Resolving→Resolve, Matching→Match, Judging→Judge.

## Verification (live, Chrome DevTools @ localhost:8731)

- `grep -c "Show Thinking"` → 0; "Debug Mode" remains only in the truncation prose (1).
- Toolbar buttons render "Thinking" and "Debug".
- All seven shortened stage labels render on the **same row** (measured `getBoundingClientRect().top` identical for all seven) — they now fit on one line.

## Follow-up (2026-05-23, same task)

Shortening the labels alone still wrapped to two lines on narrower panels (the row was
`flex-wrap: wrap` at 10px). Resolved + added requested tooltips:
- `.progress-stages` → `font-size: 9px`, `gap: 3px`, **`flex-wrap: nowrap`** + `white-space: nowrap`; `.stage-pill` → `padding: 1px 5px`, `cursor: help`. All seven pills now sit on one row (verified: identical `getBoundingClientRect().top`, no container overflow).
- Added a `STAGE_TOOLTIPS` map and a `title` attribute (escaped) on each pill so hovering describes what that pipeline stage does. Descriptions grounded in the backend stages: Ingest=ingestion_stage, Normalize=normalization_stage, Enrich=parallel EntityRuler+early extraction, Identify=llm_concept_stage, Resolve=resolution_stage, Match=string_match_stage, Judge=branch_judge_stage.

## Final design — "Process Pipeline" (collapsible vertical stepper)

After several design iterations via Q&A (chips → chevron flow [reverted] → node track → vertical
stepper), the chosen end state is a **collapsible vertical stepper**:
- **Before:** every stage labeled and visible (hollow/dim nodes on a rail) — "easily see each stage".
- **During:** stages fill done→active→to-do; the active stage is **emphasized** (14px, accent, bold) with its description inline; the rail fills green up to it.
- **After:** all stages green; auto-collapses; collapsed header reads "✓ Complete".
- **Accordion auto-disclosure:** collapsed at rest (before) and after completion, auto-expands while processing — driven by phase transitions (idle/done → collapsed, running → expanded). Manually expandable/collapsible anytime via the header chevron; a manual toggle is respected until the next phase transition. The collapsed header shows a **representative stage** with a state dot: the **first** stage (Ingest) before, the **current** stage while running, the **final** stage (Judge, green) after.
- Hover any step for its full description. Theme-aware (`--accent`/`--conf-high`/`--border`); `renderProgressStages(status)` signature unchanged (still driven by the existing SSE status flow).

## Scope

frontend/index.html only; no backend changes; no new dependencies; no status-key or logic changes.
