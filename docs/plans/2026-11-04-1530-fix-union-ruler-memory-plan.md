---
title: "fix: union EntityRuler reuses FOLIO's cached ruler plus a Canon-delta ruler"
status: completed
date: 2026-11-04
---

# Problem

A live "Enrich against both" job kills DEV's propositions-dev container (mem_limit 1600m).

Local measurement (real FOLIO + Canon, RSS after each step):

| step | RSS |
|---|---|
| FOLIO graph + labels | 356 MB |
| FOLIO shared ruler bundle | 884 MB (+528) |
| Canon graph + labels | 1050 MB |
| union labels | 1145 MB (+95) |
| private union ruler bundle | 1696 MB (+551) |
| union bundle dropped | 1475 MB (330 MB never returned) |

FOLIO has 69,368 labels; the union has 71,604; only 2,245 union labels are absent from FOLIO.
The private union ruler recompiles all of FOLIO's patterns for every both job.

# Fix

1. Build the union matcher as the shared, cached FOLIO bundle plus a small "Canon-delta"
   ruler compiled only from union labels whose key FOLIO does not have.
2. Merge the two rulers' matches with spaCy's overlap rule (longest span wins, earliest on ties;
   no overlapping spans), drop FOLIO matches whose concept the overlap index does not know
   (the union label map already excludes them), and stamp regions as today.
3. Cache the union bundle in its own cache, keyed by the identity of the FOLIO bundle and the
   union label dicts; the shared FOLIO cache never holds Canon patterns.
4. Regression test: the delta ruler holds only delta patterns and the FOLIO ruler object is
   the cached one.

# Known edge

The FOLIO ruler resolves its own overlaps before the merge, so a FOLIO span suppressed by a
longer FOLIO span cannot reappear when a still-longer Canon-delta span suppresses that longer
span. Rare, and the result still has no overlaps.

# Verification

Full suite, the slow union tests, a local RSS rerun, then a live both job on DEV with no
container restart.

# Results (2026-11-04)

- RSS: the union bundle now adds 16 MB on top of the cached FOLIO ruler (was +551 MB); repeat jobs reuse the cached bundle.
- Delta ruler: 2,236 labels.
- Equivalence: across 23 baked demo documents, old and new union rulers return identical matches (3,973 of 3,973).
- Suite: 1647 passed; the 3 failures are the known env-only ones (insights router path, parquet byte fixture, nupunkt abbreviation split). Slow union tests: 3 passed.
