---
quick_id: 260525-ppl
status: complete
date: 2026-05-25
tasks_completed: 1
---

# Summary: Expand pipeline node labels to full words

Replaced the 8 abbreviated PROCESS PIPELINE node labels with full words and
renamed the now-misnamed `abbr` field to `label`.

## Changes (frontend/index.html)

- `PPL_STAGES` values: Ing→Ingest, Nrm→Normalize, Str→String, LLM→LLM,
  Res→Resolve, Jdg→Judge, Mat→Match, Fin→Finalize. Status `key`s unchanged.
- Field rename `abbr` → `label`; render reference updated (`s.label`).
- Two comments updated (no longer "abbreviated").

## Verification

Forced `renderProgressStages('completed')` and measured every
`.ppl-step-label` bounding box via Chrome DevTools:

- **487px panel (live width):** 0 overlaps, 0 clipping. Tightest inter-label
  gap 30px (Normalize↔String); edge margins 13px (Ingest) / 10px (Finalize).
- **300px panel (grid minimum):** 0 overlaps, 0 clipping.

Screenshot confirmed clean rendering: Ingest · Normalize · String · LLM ·
Resolve · Judge · Match · Finalize.

No internal status keys, pipeline logic, or activity maps changed.
