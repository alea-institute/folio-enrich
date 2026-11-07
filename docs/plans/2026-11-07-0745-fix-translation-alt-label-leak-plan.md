---
title: "fix: translations leak into alternative labels under folio-python >= 0.3.5"
type: fix
status: active
date: 2026-11-07
---

# fix: translations leak into alternative labels under folio-python >= 0.3.5

## Problem

On 2026-11-04 the same "Enrich against both" job on the regulatory advice memo
returned 360 annotations on DEV and 281 on PROD. Stage logs located the gap in the
entity ruler: identical preferred matches (131), but 229 alternative matches on DEV
against 129 on PROD.

Cause: environment drift in folio-python. `pyproject.toml` allows
`folio-python[search]>=0.1.5`; `uv.lock` pins 0.3.6, but neither deploy installs
from the lock. DEV's image runs `pip install .` and resolves 0.4.0; PROD's venv
kept 0.3.3. Starting with 0.3.5, folio-python appends every language-tagged
`skos:altLabel` to `alternative_labels` (it also records them in `translations`).

Measured locally on the FOLIO OWL (hash 44657b4ed844f5f9):

| folio-python | FOLIO label keys | alternative entries | both-mode ruler matches on the memo |
|---|---|---|---|
| 0.3.3 | 28,331 | 9,755 | 260 |
| 0.4.0 | 69,368 | 51,299 | 360 |

Under 0.4.0, 47,347 of 57,547 FOLIO alternative labels equal a translation value
(fr-fr, pt-br, de-de, ja-jp, zh-cn, es-es, he-il, hi-in, en-gb ...). The extra
matches are noise: "data" resolves to the "Data" Definition concept, French
"actions" to Shares, Portuguese "pai" to Parent, French "surveillance" to
Monitoring.

folio-enrich already decides translations deliberately: `FolioService` adds them
as `translation` labels only when `translation_matching_enabled` (default off).
folio-python 0.3.5+ bypasses that switch.

A second defect compounds it: the label-embedding cache is keyed by model and OWL
hash only. PROD loaded a cache built under 0.4.0 (69,368 labels, translations
included) although its own ruler used 0.3.3 labels, and no label-set change ever
invalidates the cache.

## Approach

1. In `FolioService._to_folio_concept`, drop from `alternative_labels` every value
   that equals one of the concept's `translations` values, unless the same text is
   also the concept's preferred label. Translations keep flowing through the
   existing `translation_matching_enabled` path. This makes label sets identical
   across folio-python versions and restores the documented switch.
2. Key the label-embedding cache by a digest of the indexed label list as well as
   the OWL hash, so a label-set change rebuilds (or loads a matching) cache instead
   of reusing stale vectors.
3. Refresh baked demos with `scripts/replay_fix_demos.py` (deterministic fix; no
   LLM calls), and report the per-demo annotation deltas.
4. Deploy DEV and PROD. Pre-build the new label-embedding caches locally and copy
   them to PROD before restart, as on 2026-11-04, so the 2-core box does not
   re-encode at startup.

Not in scope: changing how deploys install dependencies (lockfile-driven installs)
and adding sentence-transformers to DEV. Both are recorded as follow-ups; the code
fix removes this drift's effect on labels.

## Verification

- Unit test: a concept whose `alternative_labels` contains its own translation
  values yields no `alternative` label entries for those values, keeps a genuine
  English alternative, and yields `translation` entries only with the switch on.
- Unit test: two label lists for the same OWL hash map to different cache paths.
- Local measurement: under folio-python 0.4.0 the FOLIO label count and the memo's
  both-mode match count equal the 0.3.3 numbers above.
- Full backend suite passes (known env-only failures excepted).
- After deploy: the same both job returns the same count on DEV and PROD.

## Rollback

Revert the merge commit and redeploy; restore the previous embedding cache files
(kept under their old names).
