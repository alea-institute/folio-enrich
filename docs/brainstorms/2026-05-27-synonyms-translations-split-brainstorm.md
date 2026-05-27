# Brainstorm: Stop translations leaking into the SYNONYMS list

**Date:** 2026-05-27
**Status:** Ready for planning

## What We're Building

In the FOLIO concept detail panel, the **SYNONYMS** list incorrectly includes
foreign-language **TRANSLATIONS** (and a couple of other non-synonyms). For the
"Commercial Finance Law" concept, SYNONYMS currently shows `Commercial Finance`,
`Commercial Finance Law`, `Derecho de Finanzas Comerciales`, `Handelsfinanzrecht`,
`商业金融法`, `COMF`, etc. — when the only true English synonym is **"Commercial
Finance."** The panel already has a separate, correct TRANSLATIONS section, so the
translations are being shown twice and the SYNONYMS list is misleading.

The fix: make `ConceptDetail.synonyms` mean *true synonyms only* by filtering out
three categories before the panel renders them.

## Root Cause (confirmed empirically)

The FOLIO ontology data is **clean** — the problem is consumption, not data:

- True synonyms and translations are both stored as `skos:altLabel`. The only
  difference is translations carry an `xml:lang` tag (`de-de`, `zh-cn`, …); true
  synonyms have no lang tag.
- The folio-python parser (`folio/graph.py:660-679`) appends **every** `altLabel`
  to a single `alternative_labels` list — including lang-tagged translations — and
  also appends the `skos:hiddenLabel` code (e.g. `COMF`).
- folio-enrich copies that whole list straight into `synonyms` at
  `backend/app/services/folio/concept_detail.py:267`
  (`synonyms=owl_class.alternative_labels or []`), with no filtering.
- The API route returns it unchanged; the frontend
  (`frontend/index.html:9273-9296`) renders `detail.synonyms` directly as pills.

folio-python keeps a separate, correct `translations: dict[langtag, text]` and a
`hidden_label` string — so we have everything needed to subtract the noise.

Verified: `alternative_labels − translations.values() − {hidden_label} − {label}`
yields exactly `{"Commercial Finance"}`.

## Why This Approach

**Chosen: backend builder filter, panel scope only.**

Compute the clean synonym set once, where `synonyms` is assigned in
`concept_detail.py`, so the `ConceptDetail.synonyms` field becomes semantically
honest ("true synonyms"). The frontend stays dumb and untouched, and the behavior
is covered by the Python test suite.

Rejected alternatives:

- **Frontend filter (`index.html`)** — leaves the API contract misleading, lacks a
  clean handle on `hidden_label`, and puts logic in untested single-file HTML.
  Pushes the problem to the wrong layer.
- **Fix folio-python parser** — single upstream fix, but it's a local dependency
  edit that changes `alternative_labels` for *all* consumers, including EntityRuler
  string matching and search indexing that may legitimately want translations for
  multilingual matching. Out of scope for this UI bug.
- **Fix FOLIO ontology source data** — not applicable; the data already encodes the
  distinction correctly via `xml:lang`.

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Fix scope | **UI detail panel only** | Smallest blast radius; matching/exports keep using translations for multilingual coverage (intentional, untouched). |
| Exclude from SYNONYMS | **translations + hidden codes + self-label repeat** | All three are non-synonyms polluting the list (`Handelsfinanzrecht`, `COMF`, `Commercial Finance Law`). |
| Where to filter | **Backend builder** (`concept_detail.py`, Approach A) | Single source of truth; field becomes semantically honest; test-covered; frontend unchanged. |
| Comparison strictness | **Normalized** (case-insensitive, trimmed, whitespace-collapsed) | A stray-spacing or casing variant of a translation can't slip through; low cost, more durable than exact match. |

## Scope Boundaries (explicitly out of scope)

- `FOLIOConcept.alternative_labels` (`folio_service.py:645`) feeding EntityRuler
  matching, the 13 exporters, and LLM prompt templates — **left as-is**. Translations
  there aid multilingual matching. Revisit only if translations are observed showing
  up as English synonyms in exports/LLM output.
- No changes to folio-python or the FOLIO ontology data.

## Implementation Pointers (for the plan, not decided here)

- Touch point: `backend/app/services/folio/concept_detail.py:267`.
- Build an exclusion set from `owl_class.translations.values()`,
  `owl_class.hidden_label`, and `owl_class.label`, each passed through a normalizer
  (`strip().casefold()` + collapse internal whitespace). Keep an `alternative_label`
  only if its normalized form isn't in the exclusion set.
- Preserve original casing/text of the surviving synonyms (normalize for comparison
  only, not for output).
- Add a unit test using "Commercial Finance Law" asserting `synonyms == ["Commercial
  Finance"]` and that TRANSLATIONS still has its 10 entries.

## Resolved Questions

- **How wide should the fix go?** → UI panel only.
- **What to exclude besides translations?** → hidden codes and the self-label repeat too.
- **Backend or frontend filter?** → Backend builder (Approach A).
- **Comparison strictness?** → Normalized (case-insensitive, whitespace-tolerant).

## Open Questions

None — all resolved.

## Success Criteria

- "Commercial Finance Law" panel shows SYNONYMS = `Commercial Finance` only.
- TRANSLATIONS section still shows all 10 language entries.
- No translation, hidden code, or self-label appears under SYNONYMS for any concept.
- EntityRuler matching, exports, and LLM prompts are unchanged (no regression).
- New test passes; full suite stays green.
