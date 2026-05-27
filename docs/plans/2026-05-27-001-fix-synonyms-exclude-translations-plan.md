---
title: "Exclude translations, hidden codes, and self-label from concept SYNONYMS"
type: fix
status: completed
date: 2026-05-27
origin: docs/brainstorms/2026-05-27-synonyms-translations-split-brainstorm.md
---

# 🐛 fix: Exclude translations from the concept SYNONYMS list

## Overview

In the FOLIO concept detail panel, the **SYNONYMS** list incorrectly shows
foreign-language **TRANSLATIONS**, the `skos:hiddenLabel` code, and the concept's
own label. For "Commercial Finance Law," SYNONYMS should show only **"Commercial
Finance"** — but currently shows 12 items including `Handelsfinanzrecht`, `商业金融法`,
`COMF`, and `Commercial Finance Law` itself.

This plan implements a **backend-only, panel-scoped** filter so `ConceptDetail.synonyms`
means *true synonyms only*. Scope and approach were settled in the brainstorm
(see brainstorm: `docs/brainstorms/2026-05-27-synonyms-translations-split-brainstorm.md`).

## Problem Statement / Motivation

The FOLIO ontology data is **clean** — the problem is consumption. folio-python's
parser (`folio/graph.py:660-679`) appends *every* `skos:altLabel` to one
`alternative_labels` list, including `xml:lang`-tagged translations, and also appends
the `skos:hiddenLabel` code. folio-enrich then copies that list verbatim into
`synonyms` at `backend/app/services/folio/concept_detail.py:267`
(`synonyms=owl_class.alternative_labels or []`), with no filtering. The panel renders
it directly, so translations appear twice (once mislabeled as synonyms) and the
SYNONYMS list is misleading.

folio-python separately exposes the data needed to subtract the noise:
`translations: dict[langtag, text]` and `hidden_label: str`. Verified empirically:
`alternative_labels − translations.values() − {hidden_label} − {label}` =
`["Commercial Finance"]` exactly.

## Proposed Solution

Add a small pure helper in `concept_detail.py` and use it at the `synonyms=` assignment:

`synonyms = alternative_labels` minus (normalized) `translations.values()`,
`hidden_label`, and the concept `label`. Comparison is normalized
(`strip()` + `casefold()` + internal-whitespace collapse); **output preserves
original casing/text**. Order preserved; normalized-duplicate synonyms dropped.

### backend/app/services/folio/concept_detail.py (new helper, module level)

```python
import re

_WS_RE = re.compile(r"\s+")

def _norm_label(s: str) -> str:
    """Normalize a label for comparison only: trim, collapse internal whitespace, casefold."""
    return _WS_RE.sub(" ", (s or "").strip()).casefold()

def _true_synonyms(
    alternative_labels: list[str],
    translations: dict[str, str],
    hidden_label: str,
    label: str,
) -> list[str]:
    """Alternative labels with translations, the hidden-label code, and the self-label
    removed. Normalized comparison; original text preserved; order kept; dupes dropped."""
    excluded = {_norm_label(v) for v in (translations or {}).values()}
    if hidden_label:
        excluded.add(_norm_label(hidden_label))
    if label:
        excluded.add(_norm_label(label))
    out, seen = [], set()
    for alt in alternative_labels or []:
        key = _norm_label(alt)
        if not key or key in excluded or key in seen:
            continue
        seen.add(key)
        out.append(alt)
    return out
```

### backend/app/services/folio/concept_detail.py:267 (call site)

```python
# translations is already built above at line 243
synonyms=_true_synonyms(
    owl_class.alternative_labels or [],
    translations,
    getattr(owl_class, "hidden_label", "") or "",
    owl_class.label or "",
),
```

`hidden_label` is read with a guarded `getattr` to match the builder's existing
`getattr`/`hasattr` convention (lines 248-259) and to stay safe against mock/older
classes that lack the field.

## Technical Considerations

- **No frontend change.** `frontend/index.html:9273` already guards with
  `if (detail.synonyms && detail.synonyms.length)`, so a concept with zero true
  synonyms cleanly hides the SYNONYMS section.
- **Normalization, not Unicode forms.** Per the brainstorm, use `casefold` +
  whitespace tolerance. No `unicodedata` NFC/NFKC — translations and alt-labels come
  from the same parser source, so composed/decomposed mismatch isn't a real risk here.
- **No new normalizer dependency.** The existing `normalization/normalizer.py` only
  does document-level whitespace; the label normalizer is local and tiny.

## System-Wide Impact

- **API surface parity:** `ConceptDetail.synonyms` is consumed *only* by the detail
  panel route (`api/routes/concepts.py:45-54`). No other reader. Exports and matching
  read a *different* field (`FOLIOConcept.alternative_labels`), so they are unaffected.
- **State lifecycle / errors:** Pure function, no I/O, no persistence — no partial-failure
  or state risk. Empty input → empty list.
- **Out of scope (intentional, leave as-is):** `FOLIOConcept.alternative_labels`
  (`folio_service.py:645`) feeding EntityRuler matching, the 13 exporters
  (`json_exporter.py`, `jsonld_exporter.py`, …), and LLM prompt templates. Those keep
  translations on purpose for multilingual matching coverage. folio-python and the
  FOLIO ontology data are **not** touched (see brainstorm: Scope Boundaries).

## Acceptance Criteria

- [x] `_true_synonyms(...)` helper added to `concept_detail.py`; call site at line 267 uses it.
- [x] "Commercial Finance Law" → `synonyms == ["Commercial Finance"]`.
- [x] No `xml:lang` translation value appears in `synonyms` for any concept.
- [x] The `hidden_label` code (e.g. `COMF`) does not appear in `synonyms`.
- [x] The concept's own `label` does not appear in `synonyms`.
- [x] `translations` dict on `ConceptDetail` is unchanged (still all 10 entries for the example).
- [x] Comparison is normalized: a casing/extra-whitespace variant of an excluded label is still removed.
- [x] Surviving synonyms keep original casing/text and original order.
- [x] Existing `test_returns_synonyms` still passes (`"DWI Defense"` is a true synonym, retained).
- [x] Full backend suite green: `cd backend && .venv/bin/python -m pytest tests/ -v`.

## Testing Plan — backend/tests/test_concept_detail.py

1. **Extend `FakeOWLClass`** (lines 15-37): add `hidden_label=None` param → `self.hidden_label = hidden_label or ""`.
2. **Direct unit test of `_true_synonyms`** (import it) — the real-world leak case:
   - `alt_labels=["Commercial Finance", "Commercial Finance Law", "Derecho de Finanzas Comerciales", "Handelsfinanzrecht", "商业金融法", "COMF"]`
   - `translations={"en-gb":"Commercial Finance Law","es-es":"Derecho de Finanzas Comerciales","de-de":"Handelsfinanzrecht","zh-cn":"商业金融法"}`
   - `hidden_label="COMF"`, `label="Commercial Finance Law"`
   - assert `== ["Commercial Finance"]`.
3. **Integration test via `mock_folio`:** add (or extend a concept with) a translation value duplicated into `alt_labels` plus a `hidden_label`; assert it's absent from `result.synonyms` and `result.translations` is intact.
4. **Normalization edge:** alt label `"commercial  finance law"` (lowercase, double space) with `label="Commercial Finance Law"` → excluded.
5. **Empty-result case:** all alt labels are translations/code → `synonyms == []` (and frontend would hide the section).

## Dependencies & Risks

- **Risk:** A legitimate English synonym identical to a translation string in another
  language would be dropped. Practically impossible across distinct languages; accepted.
- **Risk:** A future caller relying on `ConceptDetail.synonyms` containing translations
  — none exists today (single consumer confirmed). Low.
- No new dependencies. No migration. No deploy-order concerns.

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-05-27-synonyms-translations-split-brainstorm.md](../brainstorms/2026-05-27-synonyms-translations-split-brainstorm.md)
  — carried-forward decisions: (1) UI-panel-only scope, (2) exclude translations + hidden codes + self-label, (3) backend-builder filter (Approach A), (4) normalized comparison.

### Internal References
- Touch point: `backend/app/services/folio/concept_detail.py:243,267`
- Model: `backend/app/models/graph_models.py:53-79` (`ConceptDetail.synonyms`, `.translations`)
- API route: `backend/app/api/routes/concepts.py:45-54`
- Frontend render: `frontend/index.html:9273-9296`
- Tests: `backend/tests/test_concept_detail.py:15-37,121-123`
- Root-cause source (do not edit): `folio-python/folio/graph.py:660-679`
- Out-of-scope leak (do not edit): `backend/app/services/folio/folio_service.py:645`

### Related Work
- Prior label-parsing fix establishing SKOS precedence: `docs/plans/2026-05-26-001-fix-agreement-concept-disambiguation-plan.md`

### AI-Era Notes
- Research via Claude (repo-research-analyst + learnings-researcher); root cause confirmed
  empirically against live folio-python data. Implementation is ~25 lines + tests — small
  enough to verify by reading the diff and running the suite.
