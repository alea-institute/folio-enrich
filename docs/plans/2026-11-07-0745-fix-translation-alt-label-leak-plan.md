---
title: "fix: translations leak into alternative labels under folio-python >= 0.3.5"
type: fix
status: completed
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

1. Decide alternative labels by OWL language tag. folio-python keeps the parsed OWL
   tree (`folio.tree`) in every version. A class's true alternative labels are its
   untagged `skos:altLabel` literals plus its `skos:hiddenLabel`, in folio-python's
   order (`app/services/folio/labels.py`). The label builder, search scoring and
   synonyms, the LLM prompt's "Also known as" line, and the concept-detail synonyms
   all use it. Translations keep flowing through the existing
   `translation_matching_enabled` path.
   - **Revised after review (2026-11-07):** an earlier version subtracted
     `translations` values by text. An independent review proved that wrong both
     ways. It dropped an untagged English alias that also exists as an en-gb
     translation ("Dependency Claims"). It also kept a second translation in one
     language, because `translations` holds only the last value per language.
   - **Measured:** under folio-python 0.4.0, the tag rule reproduces 0.3.3's
     alternative labels exactly for all 18,326 FOLIO and 14,973 Canon classes.
1b. Pin `folio-python[search]==0.4.0` (lock updated), so DEV's `pip install .` and
   PROD's `uv pip install -e .` resolve the same parser and the same label digests.
2. Key the label-embedding cache by a digest of the indexed label list as well as
   the OWL hash, so a label-set change rebuilds (or loads a matching) cache instead
   of reusing stale vectors.
3. Refresh baked demos with `scripts/replay_fix_demos.py` (deterministic fix; no
   LLM calls), and report the per-demo annotation deltas.
4. Deploy DEV and PROD. Pre-build the new label-embedding caches locally and copy
   them to PROD before restart, as on 2026-11-04, so the 2-core box does not
   re-encode at startup.

Not in scope: lockfile-driven installs (the exact pin covers folio-python)
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

## Results (2026-11-07)

Shipped in PR #60 (`5c62e88`): labels by OWL tag, rescored label search, label-digest cache keys, and the `folio-python==0.4.0` pin. PR #61 (`3dc214d`) added the demo replay plus two replay-script fixes: the replay now preserves job status and remaps class links. Three focused reviews, each with an independent cross-model read, found three P2s, all fixed before merge.

Same memo (`advice_regulatory`, 16,206 chars), both mode:

| | ruler preferred | ruler alternative | semantic | annotations |
|---|---|---|---|---|
| DEV before (0.4.0, no fix, no embeddings) | 131 | 229 | n/a | 360 |
| PROD before (0.3.3, embeddings) | 131 | 129 | 23 | 281 |
| DEV after (no embeddings) | 131 | 139 | n/a | 270 |
| PROD after | 131 | 139 | 11 | 280 |

- **DEV/PROD gap:** DEV and PROD now differ only by PROD's semantic (embedding) matches, because DEV's image has no sentence-transformers. FOLIO-only mode on the same memo gives an identical ruler (115 preferred + 125 alternative) on both servers.
- **Both-mode alternatives (+10 vs PROD before):** these are Canon lemma matches. PROD's old Canon lemma cache collided with FOLIO's file.
- **Semantic matches (23 → 11):** translation strings left the embedding index (69,368 → 28,331 FOLIO vectors).

## PROD deploy receipt (2026-11-07, `3dc214d`)

- **Backup:** HEAD and `.env` in a dated `enrich-backup-<ts>-pre3dc214d` directory, and a dated venv copy, both in the ubuntu home on the enrich box.
- **Dependencies:** `uv pip install -e .` changed only folio-python 0.3.3 → 0.4.0 and lxml 6.0.2 → 6.1.3; a smoke import passed.
- **Caches:** the new FOLIO and Canon label-embedding caches and the lemma caches were built locally under the same pin. They were staged with verified checksums before restart; both loaded from cache with no re-encode.
- **Verification:**
  - **Health:** `/health` 200 within seconds of the restart.
  - **Jobs:** both job 280 annotations in 35 s; FOLIO job 250.
  - **Admin gate:** settings PUT without token → 403.
  - **Memory:** peak 2.42 GB; box 3.3 GB available.
  - **Neighbors:** folio-mapper, ontokit and Caddy active.
  - **Public demo and browser:** the public demo JSON is the replayed one (NDA 343 annotations), and a browser render of the NDA exemplar showed no page errors.
- **Rollback:** stop the service; restore the dated venv copy and `.env`; `git checkout 9a28361`; start. The old cache files are untouched.

## DEV deploy note

Building the DEV image on hetzner-dev (8 GB, shared with Coolify apps and previews) drove the box out of memory: swap full, about 15 minutes unreachable, recovered on its own with no container lost. DEV images are now built on the home box and shipped with `docker save | ssh docker load`, then `docker compose up -d --no-deps --no-build propositions-dev`.
