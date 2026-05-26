---
quick_id: 260525-ppl
description: Expand Process Pipeline node labels from 3-letter abbreviations to full words
date: 2026-05-25
tasks: 1
---

# Quick Task 260525-ppl: Expand pipeline node labels to full words

The PROCESS PIPELINE track shows 8 stations with tiny labels under each node.
They were 3-letter abbreviations (Ing, Nrm, Str, LLM, Res, Jdg, Mat, Fin) from
an earlier space-constrained pass. The panel now has room for full words.

Pure display-text change in `frontend/index.html` (no logic/key changes).

## Task 1: Expand node labels + rename field

**Files:** frontend/index.html

**Changes:**
- `PPL_STAGES` map (~6189): full words, status keys unchanged —
  Ing→Ingest, Nrm→Normalize, Str→String, LLM→LLM, Res→Resolve,
  Jdg→Judge, Mat→Match, Fin→Finalize.
- Rename the field `abbr` → `label` (values are no longer abbreviations);
  update the single render reference (~6241) `s.abbr` → `s.label`.
- Update two comments describing labels as "abbreviated" (~2371, ~2436).

**Verify:** Force completed render (`renderProgressStages('completed')`) and
measure each `.ppl-step-label` bounding box. No adjacent-label overlap and no
clipping past the panel content box — at both the live (~487px) and the
minimum (300px) left-panel widths.

**Done:** Full words render under every node; verified no overlap/clipping at
300px and 487px panel widths via Chrome DevTools geometry + screenshot.
