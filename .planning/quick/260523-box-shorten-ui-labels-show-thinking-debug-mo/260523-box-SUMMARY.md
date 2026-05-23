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

## Scope

frontend/index.html only; no backend changes; no new dependencies; no status-key or logic changes.
