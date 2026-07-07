# NER eval gold set

Human-verifiable ground truth for the NER cross-validation eval harness
(`backend/eval/`). Answers the flip precondition for
`ner_cross_validation_enabled`: *does turning it on improve F1 without regressing
recall?* Each line of `folio_ner_gold.jsonl` is one judgment about one text span.

## Why this exists

`ner_cross_validation_enabled` (default **False**) boosts/penalizes annotation
confidence during reconciliation using spaCy NER labels vs. a per-ontology branch
affinity map, and can reject a span whose confidence drops below 0.20. Deciding the
flip needs precision/recall/F1 with the flag on vs off — which needs gold. The baked
`frontend/demos/*.json` are **pipeline outputs (silver), not gold**; this set is the
human-verifiable ground truth.

## Format (`folio_ner_gold.jsonl`, one JSON object per line)

```json
{
  "gold_id": "GOLD-FOLIO-CONTRACT-001",
  "doc_id": "contract",
  "doc_source": "frontend/demos/contract.json",
  "span": {"start": 0, "end": 13, "text": "FORCE MAJEURE"},
  "expected_iri": "https://folio.openlegalstandard.org/RCp6PzHvkRv1l3pXC9E4Mse",
  "expected_label": "Force Majeure",
  "branch": "Objectives",
  "polarity": "positive",
  "verification": "deterministic",
  "verified_by": "folio-label-oracle 2026-07-07",
  "difficulty": "clear",
  "rationale": "Unique (lemma-)preferred FOLIO label match — oracle-confirmed.",
  "candidates": []
}
```

| field | meaning |
|---|---|
| `gold_id` | stable id `GOLD-<ONTOLOGY>-<DOC>-<NNN>` |
| `span.start/end` | **character** offsets into the document's *canonical* `full_text` (half-open). The deterministic pipeline reproduces canonical text run-to-run, so these are stable. |
| `expected_iri` | the concept the span SHOULD (positive) or should NOT (negative) map to |
| `polarity` | `positive` = span maps to `expected_iri`; `negative` = span must NOT map to it (a known collision / false-positive case) |
| `verification` | `deterministic` (FOLIO-label-oracle confirmed) · `human` (a person set it — **never overwritten by curation**) · `needs_review` (seeded but ambiguous; **not scored** until promoted) |
| `difficulty` | `clear` or `borderline` |
| `candidates` | competing concepts for a borderline span (surfaced in the evidence pack) |

**Scoring.** Only `deterministic` + `human` entries count toward P/R/F1
(`needs_review` is excluded). Metrics are **span-restricted** over the labelled spans
(correct for a sampled gold): a positive entry is a TP when a confirmed prediction
overlaps its span AND carries `expected_iri` (compared by IRI hash suffix, host-agnostic).

## Seeding / refreshing (the curator)

```bash
cd backend
.venv/bin/python -m eval.curate                       # default doc set, 25/doc cap
.venv/bin/python -m eval.curate --docs contract,nda   # subset
```

Seeding is **non-circular**: spans come from the demo documents, but the correct label
is decided by the **FOLIO label dictionary oracle** (`FolioService.get_all_labels_multi`),
not by the enrich ranking. A surface that maps to exactly one concept via a
(lemma-)preferred label → `deterministic/clear`; an ambiguous or alternative-label
surface → `needs_review/borderline` with the competing `candidates` recorded.

Curation is **idempotent** and **preserves `verification:"human"` entries** — so hand
verification is never clobbered by a refresh.

## Extending it (Damien / other lanes)

1. **Promote a borderline case.** Find a `needs_review` entry, confirm the right IRI
   (use the FOLIO MCP or `folio-python`), set `expected_iri`/`expected_label`, set
   `verification:"human"`, `verified_by:"<you> <date>"`, `difficulty` as apt. It now
   counts toward the score and survives future `eval.curate` runs.
2. **Add a negative case.** New line, `polarity:"negative"`, `expected_iri` = the wrong
   concept the span must NOT get (e.g. bare "Agreement" must NOT map to
   "License (Agreement)"), `verification:"human"`.
3. **Add a new document.** `.venv/bin/python -m eval.curate --docs <newslug>` (any
   `frontend/demos/<slug>.json`), then verify the seeded entries by hand.

Re-run the eval after any change: `.venv/bin/python -m eval.runner`.
