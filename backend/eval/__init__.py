"""FOLIO Enrich evaluation harness.

Precision / recall / F1 gold-set evaluation for the NER cross-validation feature
(``ner_cross_validation_enabled``). See ``eval/gold/README.md`` for the gold-set
format and curation workflow, and ``docs/plans/2026-07-07-001-ner-eval-harness-plan.md``
for the design rationale.

Modules
-------
- ``gold_schema`` : gold-entry data model + JSONL load/save.
- ``metrics``     : span-restricted precision/recall/F1 over a curated gold set.
- ``runner``      : runs the pipeline flag OFF vs ON and reports the delta (CLI).
- ``curate``      : seeds/refreshes the gold set from baked demos + the FOLIO oracle (CLI).
- ``estimate_spend`` : token-grounded full-mode LLM cost estimate (CLI).
"""
