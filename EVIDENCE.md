# Evidence packs — folio-enrich

ID-addressable HTML review packs (Portfolio Plan standing policy 2). Review by EP-ID;
ID-referenced feedback becomes the next iteration.

| Date | Campaign | Pack | Rubric | Spend |
|---|---|---|---|---|
| 2026-07-07 | NER cross-validation gold-set eval (`EP-ENRICH-NER-EVAL-001..013`) | [`docs/evidence/ner-eval/pack.html`](docs/evidence/ner-eval/pack.html) | ner-flip-precondition (F1 up, no recall regression) | $0 (full-mode run closed — see next row) |
| 2026-07-07 | NER full-mode eval closure — baseline (146/52) + expanded (159/62) gold, authoritative full pipeline | [`docs/evidence/ner-eval/full-mode-closure.md`](docs/evidence/ner-eval/full-mode-closure.md) | ner-flip-precondition **NOT MET** (F1 +0.000 both runs; recall safe) → verdict **HOLD**, default stays `False` | est $0.23–$1.04 total + $0.01 curation (q8 cap <$5) |
