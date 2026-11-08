---
title: "chore: DEV preview lanes, restart-guard fix, and label follow-ups"
type: chore
status: completed
date: 2026-11-08
---

# chore: DEV preview lanes, restart-guard fix, and label follow-ups

## Context

The 2026-11-07 handoff (`docs/handoffs/2026-11-07-label-fix-and-ruler-followups.md`) left four items
an agent can finish alone and two that need the owner. On 2026-11-08 the owner said to proceed with
all of them.

## Findings before work

- **Stops did not stick:** hetzner-dev runs a `coolify-restart-guard` timer (dev-twin repo) every 30
  minutes. It starts every stopped Coolify-managed container, so the previews stopped on 2026-11-07
  came back.
- **Builds on the box returned:** clearing the jammed deploy queue on 2026-11-07 re-enabled Coolify's
  push-triggered builds. Four folio-enrich builds then ran on hetzner-dev (`main` at `804fb1e` took
  19 minutes; PRs #48, #49 and #50 followed). None ran out of memory.
- **Disk is the tighter limit:** folio-insights images weigh 9.4 GB each, and the Docker data disk
  has 24 GB free. An image built on another machine shares no layers with the ones already on the
  box, so each folio-insights image shipped from elsewhere costs the full 9.4 GB.
- **Docs-only previews:** folio-enrich PRs #48 and #49 and folio-insights PRs #78 and #79 change
  only documentation. Their previews duplicate `main`, so they cost memory and give nothing to review.
- **folio-enrich #50:** its preview already runs the PR head (`dac6a80`).

## Units

1. **Restart guard respects deliberate stops (dev-twin).** Start a stopped managed container only
   when the stop came before the current boot, which is the reboot case the guard exists for.
   Tested with a stubbed `docker`. Installed on hetzner-dev after merge.
2. **Free memory.** Once the fixed guard is live, stop the docs-only previews (folio-enrich #48 and
   #49) and the orphaned preview of merged folio-insights PR #50. Remove nothing else.
3. **Replay lanes.** Use images built on the home box, then a Coolify deploy that skips its build.
   Replay folio-mapper #15 and folio-insights `master`; skip folio-insights #70 if the disk would
   drop below a safe margin, and skip the docs-only lanes.
4. **Property altLabel translations.** Measure first.
5. **Label-search candidate pool.** Measure the raw pool size (now 20) against the demo concept
   texts; raise it only if recall improves and latency stays bounded.
6. **Owner decisions.** Coolify panel access (stale home IP), and the existing drawdown credit-halt
   ask that holds PRs #48–#50.

## Verification

- Guard: its new test fails against the old script on the "stopped after boot" case and passes after
  the fix; on the box, a stopped preview stays stopped across a guard run.
- Memory: `free -m` before and after.
- Lanes: Coolify reports "Build step skipped", and each preview answers its health check.
- Label pool: a measurement table and examples; the full backend suite passes.

## Results

1. **Restart guard (done).** dev-twin PR #23 is merged. The new test failed 13 of its first 17
   cases against the old script, and all 35 pass after the fix. A review pass caught one gap: after an
   unclean reboot, Docker stamps the stop time after boot, so the fixed guard would never restart that
   container. That case is fixed and tested too. The guard is installed on hetzner-dev, with the old
   script kept beside it as a `.bak` file. The previews stopped at 07:14Z stayed stopped through every
   guard run since.
2. **Memory (done).** folio-enrich #48 and #49 and folio-insights #50 are stopped (`docker stop`
   only; images and volumes kept). Memory pressure reads zero (PSI avg300 = 0.00). Swap stays near
   full (about 4.0 of 4.1 GB) with roughly 1.5 GB available, so swap is not the limit to watch.
3. **Lanes (done).**
   - **folio-mapper #15:** deployed and healthy (`/api/health` 200). Coolify **rebuilt** the image on
     hetzner-dev and ignored the shipped one, because preview deploys tag images
     `pr-<n>-<deployment-id>`, not `pr-<n>-<commit>`. Skipping the build with a shipped image works
     only for main-branch apps. The unused shipped image was deleted.
   - **folio-insights `master`:** image `99c3f6d` was built on the home box and loaded with
     `docker load`. The Coolify deploy took 85 s and started no build process on the box. The
     container runs `99c3f6d`, is healthy, and `/health` and `/` return 200. The prior image stays as
     Coolify's rollback.
   - **Skipped:** folio-insights #70, because the Docker disk has 14 GB free after the `master` image,
     and a second 9.4 GB image would leave about 5 GB. Also skipped: the docs-only lanes (folio-insights
     #78 and #79, folio-enrich #48 and #49).
4. **Property altLabels (closed, no change).** Measured from the OWL: FOLIO has 181 ObjectProperty
   nodes with 224 untagged altLabels and **0** language-tagged ones. Canon (pinned sha) has 170 nodes,
   also with 224 untagged and 0 tagged. No translations reach property altLabels, so there is nothing
   to filter. Revisit only if a future OWL release adds tagged property altLabels.
5. **Label-search pool (closed, no change).** The pool stays at `max(top_k * 4, 20)`. The
   measurement below shows why.
6. **Owner decisions.**
   - **Coolify panel lock:** filed as Cockpit ask `folio-enrich-2026-11-08-0908-coolify-panel-lock`,
     recommending Tailscale only.
   - **PRs #48–#50:** still held by the existing drawdown spend ask
     (`chief-2026-10-31-2255-drawdown-credit-halt`). It was not filed again.

## Label-search pool measurement

`backend/scripts/measure_label_search_pool.py` ran 2,350 unique queries, drawn case-insensitively
from the concept and span texts in all 34 baked demos. It used folio-python 0.4.0 with translations
off and the production true-label WRatio rescoring. It loaded the production OWL branch
(`FOLIO_SPEC` `main`, sha256 prefix `44657b4ed844`) and compared every pool size against a fixed P=20.

| Pool P | Top-1 IRI changes | Top-1 score gain | Rescues (top-1 < 90 → ≥ 90) | Below-top-1 gains (k=5) | Median ms (k=5) | p95 ms (k=5) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0 | 0 | 0 | 0 | 2.96 | 4.06 |
| 40 | 79 | 0 | 0 | 1 | 3.11 | 4.30 |
| 80 | 107 | 0 | 0 | 2 | 3.41 | 4.74 |
| 160 | 130 | 0 | 0 | 2 | 3.97 | 5.67 |

- **No top-1 gain:** every changed top-1 is a tie, with the same rescored score, broken differently.
  A larger pool raised no query's top score. Of 15 sampled ties, one is plausibly better and several
  are clearly worse; for example, "Company" goes from Limited Company to Northern Mariana Islands.
- **Below top-1, the gains are noise:** a "below-top-1 gain" means a concept newly enters the top_k
  with a higher score than P=20's lowest kept score.
  - **k=5:** "voir dire" gains Coir (73), and "nun" gains Articulation Disorder (90).
  - **k=10:** production already uses P=40 (`max(top_k * 4, 20)`). Against that baseline, P≥80 adds
    only "apostolic tribunal" → Napo and "nun" → Articulation Disorder.
  - **Count:** 16 queries gain against a fixed P=20 at k=10, all of the same kind, such as "church" →
    Uri.
  - **Meaning:** a larger pool admits lexical look-alikes, not better English matches.
- **Some crowding exists:** 2.6% of P=20 raw hits reach the pool only through a translation match.
  None of them displaced a higher-scoring top-1.
- **Decision rule failed:** shipping needed rescues on at least 1% of queries and better changed
  results. Latency would have passed, but no production code changed.
- **Scope limit:** the run searches only the FOLIO service, including the 344 queries that come only
  from Canon demos, so it says nothing about the Canon service's pool.
- **Receipt:** the full per-query JSON (43 MB, sha256 prefix `115047fdce3e3bd3`) stays out of git.
  Rerun the script to regenerate it. An earlier run against the `2.0.0` OWL reached the same
  conclusion; code review caught the branch mismatch.

## Test evidence

- **CI on main:** `804fb1e` passed (1,698 tests) on the lockfile versions.
- **Local suite:** 1,706 passed and 3 failed in a venv built from unpinned `>=` ranges with
  `uv pip install -e`, which skips `uv.lock`. The failures:
  - `test_insights_route::test_router_is_mounted`: a local environment failure already known on main.
  - `test_proposition_byte_neutral` (Parquet) and `TestNupunktSentences`: this venv resolved pyarrow
    26.0.1 and nupunkt 0.8.0, while CI's lockfile resolves pyarrow 23.0.1 and nupunkt 0.6.0. The
    failures show what will break when the lockfile moves to those versions; they do not show a
    regression on main.
- **Follow-up:** before bumping pyarrow past 23 or nupunkt past 0.6 in `uv.lock`, regenerate the
  proposition byte-neutral Parquet fixture and check the sentence-splitting expectation.

## Follow-up: Canon label-search pool (2026-11-08)

`measure_label_search_pool.py --ontology canon` ran the same 2,350 demo queries through the Canon
service, built by the production registry from the pinned OWL (sha256 prefix `add8b2b140273b19`).

| Pool P | Top-1 IRI changes vs P=20 | Top-1 score gain vs P=20 | Rescues | Below-top-1 gains, k=10 vs production P=40 | Median ms (k=5) | p95 ms (k=5) |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0 | 0 | 0 | 0 | 1.81 | 2.56 |
| 40 | 83 | 0 | 0 | 0 | 1.94 | 2.73 |
| 80 | 112 | 0 | 0 | 6 | 2.19 | 3.20 |
| 160 | 127 | 0 | 0 | 6 | 2.71 | 4.07 |

- **Same verdict as FOLIO:** no rescues and no top-1 score gain. Every changed top-1 is a tie.
- **Gains below top-1 are noise:** of the 6 queries that gain at P≥80, 4 gain junk matches: "nun" →
  Satun, "escrow instructions clause" → Ruse, "specific performance clause" → Ruse, and "amicable
  resolution clause" → Resolutions. The other 2 swap in a match with the same score.
- **Decision:** Canon also keeps `max(top_k * 4, 20)`.
- **Run cost:** the warm-cache timing pass needs more than 4 GB, so run it under an 8 GB cap
  (`box-run --max 8G`). The 4 GB attempt was OOM-killed during warm-up.
- **Receipt:** the JSON (44 MB, sha256 prefix `e50eb54915813652`) stays out of git under the existing
  `label_search_pool_*.json` ignore rule.
