---
quick_id: 260523-box
description: Shorten UI labels (Show Thinking, Debug Mode) and pipeline stage names to fit on one line
date: 2026-05-23
tasks: 1
---

# Quick Task 260523-box: Shorten UI labels

Pure display-text renames in `frontend/index.html` (no logic/key changes).

## Task 1: Rename display labels

**Files:** frontend/index.html

**Changes:**
- Toolbar button "Show Thinking" → "Thinking" (markup ~3215 + toggle innerHTML ~5442).
- Toolbar button "Debug Mode" → "Debug" (markup ~3216 + toggle innerHTML ~5436). The "truncated by Debug Mode" prose message (~5423) is left as-is (names the feature, not the button).
- Pipeline stage-label map values (~3822-3824) — display strings only, keys unchanged:
  Ingesting→Ingest, Normalizing→Normalize, Enriching→Enrich, Identifying→Identify, Resolving→Resolve, Matching→Match, Judging→Judge. ('Queued' and 'Extracting Individuals' untouched.)

**Verify:** `grep -c "Show Thinking"` = 0; buttons read "Thinking"/"Debug"; the seven shortened stage labels render on a single row.

**Done:** Labels shortened; stages fit on one line; no internal status keys or logic changed.
