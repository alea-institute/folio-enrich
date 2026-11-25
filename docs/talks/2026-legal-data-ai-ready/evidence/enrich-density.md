# FOLIO Enrich tag density: demo document

- **Date:** 2026-11-25
- **Document:** `demo-document.md` (leading HTML comment stripped, fed as plain text), title "Breach of Exclusive Distribution Agreement"
- **Command (from `backend/`):** `box-run --max 12G -- .venv/bin/python ../docs/talks/2026-legal-data-ai-ready/tools/run_enrich.py`
- **Measure:** `python3 tools/measure_density.py evidence/enrich-result.json`
- **Provider:** codex-cli (subscription, no API key), model `gpt-6.1-sol`, effort medium, every LLM task routed to it
- **Ontology:** FOLIO, with the local embeddings extra installed (semantic stages active)
- **Run time:** 105 s service init (OWL + embedding index) + 407 s pipeline = about 8.5 min
- **Output:** `evidence/enrich-result.json` (demo format, slimmed the same way as exemplars; nothing written to `frontend/demos/`)

## Result

| Metric | This document | rich_contract | rich_advisory |
|---|---|---|---|
| Coverage (words with any tagged char) | **49.9%** (336/674) | 50.8% (333/656) | 65.5% (527/805) |
| Annotations | 241 | 229 | 347 |
| Distinct concept IRIs | 126 | 134 | 171 |
| Individuals | 34 | 23 | 24 |
| Properties | 75 | 36 | 60 |
| Triples | 61 | 57 | 63 |

Coverage = share of `[A-Za-z]{3,}` words in `cache.normalizedText` overlapping any `cache.job.result.annotations` span. Baselines re-measured with the same script.

## Longest untagged stretches (3+ consecutive untagged words; count in brackets)

- [21] November 3, 2025, Brazilian customs authorities detained three containers after laboratory testing showed sulfite levels above the regulatory limit. The Ministry of Agriculture issued
- [10] that every shipment would conform to the product specifications, carry a valid
- [10] include the storage fees, destruction costs, and regulatory fine. The
- [9] dated June 1, 2022 ## Executive Summary Distribuidora Atlântica Ltda., a Brazilian
- [7] the competitor creates a likelihood of confusion and supports
- [7] with the ICC Secretariat and pay the
- [6] before the International Chamber of Commerce, seated
- [6] its wine products in the Federative Republic
- [6] establish nonconformity. Under the CISG, the
- [6] because product contamination was within the
- [6] will be enforceable in all three countries. The
- [6] and chain of custody records rebut each
- [5] Distribuidora Atlântica Ltda. **From
- [5] for a five-year term. The
- [5] paid storage fees, destruction costs

## Run 2 (final): revised matter-profile document, 2026-11-25

- **Change:** the memo prose was rewritten as a terse matter profile (field: value lines, noun-phrase sentences, no Markdown marks). Function words (the, and, for, under, with) made up about 45% of run 1's untagged words; no ontology tags them.
- **Command (from `backend/`):** `box-run --max 12G -- .venv/bin/python ../docs/talks/2026-legal-data-ai-ready/tools/run_enrich.py` (worktree venv; provider codex-cli, model gpt-6.1-sol, effort medium; no API spend)
- **Time:** 383.5 s pipeline (492.9 s service setup, cold embedding index)
- **Coverage:** **84.4%** (331 of 392 words), measured with `tools/measure_density.py`
- **Counts:** 219 annotations, 130 distinct concept IRIs, 23 individuals, 23 properties, 11 triples
- **Baselines (same measurer):** rich_advisory 65.5%, rich_contract 50.8%; run 1 of this document 49.9% (kept as `enrich-result-v1.json`)
- **Remaining untagged stretches:** party names (Distribuidora Atlântica Ltda), "Customs detention: Brazilian customs", "Import and Export", "for the International", "detained wine shipment", "electronically stored information"
- **Trade-off:** the terser text has fewer verb relations, so properties fell from 75 to 23 and triples from 61 to 11. Tag density, the talk's point, rose.
