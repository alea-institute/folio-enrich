---
type: bug
status: pending
created: 2026-05-22
title: Synonyms section includes foreign-language translations (should be English-only)
tags: [backend, concept-detail, folio, data]
severity: medium
discovered_during: 02-robust-translation-flags UAT (Railway Dev)
resolves_phase: null
---

## Bug

The concept Detail panel's **Synonyms** section lists foreign-language translations
(e.g., "Negligencia Marítima", "Negligência marítima", "Seefahrtsnachlässigkeit",
"הפרת חובת זהירות בימים", "समुद्री लापरवाही", "海事过失", "海事過失") alongside the
English label. Synonyms should contain **English-only** alternative labels; the
non-English variants belong solely to the separate **Translations** section.

Observed on Railway Dev for the "Maritime Negligence" concept during Phase 02 UAT.
Confirmed NOT caused by Phase 02 (flag work was frontend-only and never touched the
synonyms code path).

## Root Cause

The backend assigns the full multilingual `skos:altLabel` set straight into `synonyms`
with no language filter:

- `backend/app/services/folio/concept_detail.py:267` → `synonyms=owl_class.alternative_labels or []`
- `backend/app/services/folio/search.py:445` → `"synonyms": owl_class.alternative_labels or []`

FOLIO `alternative_labels` contains labels in many languages. The same non-English
strings also legitimately populate the separate `translations` dict
(`concept_detail.py:243`), so they appear in BOTH sections.

## Frontend (renders verbatim — not the bug)

`frontend/index.html:8347` renders `detail.synonyms` as-is. No frontend change needed
once the backend array is clean.

## Proposed Fix

Filter `alternative_labels` to English-only before assigning to `synonyms`. Options:
1. Exclude any altLabel whose value appears in `translations.values()` for non-`en`
   locales (precise — drops exactly the strings shown in the Translations section).
2. If the FOLIO model exposes language tags on altLabels, keep only `en`-tagged values.

Add a unit test in `backend/tests/` asserting a concept with multilingual altLabels
yields English-only `synonyms` while `translations` still carries the full set.
Apply the same fix at both `concept_detail.py` and `search.py` sites.
