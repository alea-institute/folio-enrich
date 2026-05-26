# Brainstorm: Fixing "Agreement" → "License (Agreement)" Precision Error

**Date:** 2026-05-26
**Status:** Captured — ready for `/ce:plan`
**Type:** Bug / precision improvement (concept disambiguation)

---

## The Problem

The input string **"Agreement"** is frequently resolved to the FOLIO concept
**"License (Agreement)"** ([`RKKRGOkIme6pnG2BSePt1Z`](https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z))
instead of the correct concept **"Agreement" / "Agreements" / "Contracts"**
([`R88D8i8AcSTUig2X3yPbFHg`](https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg)).

### Root cause (verified against live FOLIO data)

| | Correct concept `R88D8…` | Wrong concept `RKKR…` |
|---|---|---|
| `rdfs:label` | **"Agreements"** (plural) | "License (Agreement)" |
| `skos:prefLabel` | "Contracts" | (none) |
| `skos:altLabel` | Accords, Acordos, Agreements… | **"Agreement"** (singular) |

The singular string **"Agreement" is not a label of the correct concept at all.**
The *only* concept in FOLIO carrying the singular token "Agreement" is
`License (Agreement)`, where it sits as an alternative label. The correct concept
is reachable only via the plural key `"agreements"`.

This is **two compounding bugs**, not a ranking preference for longer names:

1. **Reachability gap** — the label index lowercases but does no singular/plural
   normalization. `"Agreement"` and `"Agreements"` are separate keys; the correct
   concept never enters the candidate set for the singular form.
   (`folio_service.py:222-392`)
2. **Disambiguation gap** — EntityRuler emits the only candidate it has
   (`License`), and reconciliation keeps the only-present IRI when merging with the
   LLM's bare-string concept. Embedding conflict-triage never fires (it requires two
   differing IRIs). Search scoring then rewards the *exact* alt-label match over the
   *plural* match. (`reconciler.py:197-223`, `search.py:135-216`)
3. **No recovery** — Rerank/BranchJudge/ContextualRerank/StringMatch only adjust
   confidence/branch/spans; none re-select the IRI once chosen.

**Secondary data issues:** a deprecated `"DUPE of License"` concept also carries
"Agreement" and isn't being filtered; same-type alt-label ordering falls back to
arbitrary ontology iteration order.

**Key implication:** embeddings/reranking alone cannot help — the correct concept
isn't even a candidate. Reachability must be fixed *first*, then disambiguation.

---

## What We're Building

A **general-class precision fix** with three coordinated parts:

### 1. Reachability — morphological normalization in the label index
Add lemma-based (singular/plural) normalization so concepts become reachable from
inflected surface forms. "Agreements" (label) → lemma `agreement` → reachable from
input "Agreement". Use the existing spaCy singleton; keep it **conservative**
(lemma only, no aggressive stemming). Preserve an exact-match index alongside a
lemma index so exact matches still rank above lemma matches.

### 2. Disambiguation — hybrid rule hierarchy + embedding tiebreak
When a span now matches multiple concepts, rank deterministically:

```
exact-primary  >  lemma-primary  >  exact-alt  >  lemma-alt
```

(primary = `rdfs:label`/`skos:prefLabel`; alt = `skos:altLabel`)

This cleanly resolves the bug: "Agreements" (lemma-primary) outranks
"License (Agreement)" (exact-alt). Filter deprecated/dupe concepts before ranking.
**Only when a genuine tie remains** (same tier, ≥2 concepts) invoke the existing
embedding service — compare the surrounding sentence against each candidate's FOLIO
definition and pick the best semantic fit.

### 3. Upstream FOLIO data cleanup (alea-institute/FOLIO)
Belt-and-suspenders, benefits every FOLIO consumer:
- Re-home the singular "Agreement" altLabel (remove from `License (Agreement)`
  and/or add as an altLabel on the Contracts/Agreements concept).
- Remove or correctly deprecate-flag the `"DUPE of License"` concept.

### 4. Regression guard — labeled eval set
Create a small gold-standard set of `string → correct-IRI` mappings (seeded with
"Agreement" and other known-ambiguous terms) and assert precision in tests. Makes
the fix measurable and prevents silent regressions from normalization.

---

## Why This Approach

- **Fixes the category, not the symptom.** Reachability + the primary>alt rule
  resolves an entire class of singular/plural and alt-label precision errors, not
  just "Agreement."
- **Explainable + fast by default.** The rule hierarchy is deterministic and
  testable; embeddings are reserved for true ties, so latency stays low.
- **Leverages what's already there** — spaCy singleton for lemmas, the embedding
  service that currently only fires on two-IRI conflicts.
- **Data + app fix together** means the system is robust even if the ontology has
  future quirks, while the ontology gets genuinely cleaner.
- **Eval set** turns "seems better" into a measured precision number and guards the
  blast radius of normalization.

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Fix location | **Both app + upstream data** | App robust to imperfect data; ontology fix helps all consumers |
| App-side scope | **General class fix** (normalization + disambiguation) | Reachability can't be patched case-by-case without recurring |
| Disambiguation mechanism | **Hybrid: rule hierarchy + embedding tiebreak** | Explainable & fast first, semantic fallback for real ties |
| Rule order | `exact-primary > lemma-primary > exact-alt > lemma-alt` | Makes primary-label match beat alt-label match — fixes the bug |
| Normalization aggressiveness | **Conservative (spaCy lemma only)** | Avoid over-merging (e.g. "licensing"→"license") |
| Regression guard | **Labeled eval set** + targeted unit tests | Measurable precision, prevents silent regressions |
| Disambiguation placement | **New dedicated stage** | Receives candidate sets; clean separation, testable in isolation |
| Eval seed discovery | **Auto-discover collisions** | Scan ontology for strings that are primary label of one concept AND alt label of another |
| Rule vs embedding authority | **Embeddings can override low-confidence rule decisions** | When a rule call is "close" (e.g. lemma-primary vs exact-alt) and context strongly disagrees, context wins |

---

## Resolved Questions

1. **Pipeline placement of disambiguation.** → **New dedicated stage.** The wrong
   IRI is currently locked in *early* (EntityRuler → Reconciliation), so the
   candidate set must be preserved and handed to an explicit Disambiguation stage
   that applies the rule hierarchy + embedding tiebreak. Cleanest separation and
   easiest to unit-test. *(Exact insertion point in the 14-stage pipeline and how
   candidate sets are threaded through is a `/ce:plan` HOW-detail.)*
2. **Seed contents of the eval set.** → **Auto-discover collisions.** Scan the FOLIO
   ontology for every string that is a *primary* label of one concept AND an
   *alternative* label of another — these are the high-risk ambiguous terms. Seed
   the gold-standard eval set from that generated list (with "Agreement" as the
   anchor case).
3. **Exact-alt vs lemma-primary edge cases.** → **Embeddings can override
   low-confidence rule decisions.** Rules run first, but when a rule decision is
   "close" (notably lemma-primary vs exact-alt) and the context embedding strongly
   disagrees, the embedding result wins. Trades a little determinism for accuracy on
   genuine edge cases; the eval set keeps this honest.

---

## Out of Scope (YAGNI)

- Full lemmatizer/stemmer or fuzzy/Levenshtein matching across all labels.
- Re-architecting the whole resolution pipeline beyond what disambiguation needs.
- LLM-based concept selection (the LLM already only proposes text, not IRIs).
