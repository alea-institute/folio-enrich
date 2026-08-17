# Proposition gold records

This directory contains human-reviewed proposition JSONL, brat standoff files, and a cycle manifest.
Gold is non-circular: exported labels come from explicit annotator outcomes, not from pipeline output alone.
Deleted pre-selected candidates remain as audit records so pre-selection precision is computable.

- Recall proxy: `1 - hand-added / total exported gold`.
- Precision: `(accepted + edited) / (accepted + edited + deleted)` over pre-selected candidates.
- Density: exported gold propositions per 1,000 words of normalized canonical text. Deleted candidates and learning-only tags are excluded.
