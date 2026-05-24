---
title: Process Pipeline "Journey" UI — animated horizontal walk
type: feat
status: completed
date: 2026-05-24
origin: docs/brainstorms/2026-05-24-pipeline-journey-ui-brainstorm.md
---

# ✨ Process Pipeline "Journey" UI — animated horizontal walk

## Overview

Redesign the **Process Pipeline** progress indicator in `frontend/index.html` (single-file
vanilla JS, no build step) from a static vertical class-swap stepper into an **animated horizontal
"journey"**: a focus+context track where the active stage is magnified and a marker + progress fill
+ live count **walk left→right** as the backend advances. This is the 8th attempt; the prior 7 are
documented as rejected in `.planning/PIPELINE-UI-HANDOFF.md`. The agreed design and rationale come
from the brainstorm (see brainstorm: `docs/brainstorms/2026-05-24-pipeline-journey-ui-brainstorm.md`).

**This plan also fixes two verified correctness bugs** that research surfaced — bugs that on their
own can make a *working* animation look broken — so the redesign rests on a correct stage model.

## Problem Statement / Motivation

Across 7 iterations the component was treated as a **layout** problem (vertical/horizontal,
collapsed/expanded). The user's words — *"expand automatically"* and *"walk along the path"* — are
about **motion**. Today `renderProgressStages()` (`frontend/index.html:5891`) rebuilds the entire
`<ol>` via `innerHTML` on every status tick, so **nothing persists to animate** — motion can only
ever be a CSS color swap on a freshly-created node.

Two **verified** correctness bugs compound the perception of brokenness:

1. **Backward jump.** The frontend stage array is
   `['ingesting','normalizing','enriching','identifying','resolving','matching','judging']`, but the
   backend emits `judging` **before** `matching` (`branch_judge_stage.py:20` runs before
   `string_match_stage.py:38`; confirmed order in `orchestrator.py`). A real run lights *Judge*, then
   the marker snaps **left** to *Match*.
2. **Mid-run disappearance.** The SSE `status` event also emits `extracting_individuals` and
   `extracting_properties` (`individual_stage.py:87`, `property_stage.py:50`) after `matching`. These
   aren't in the array → `currentIdx = -1` → `dataset.phase = 'idle'` → **the whole pipeline hides**
   in the post-Judge tail, then pops back as "complete." (`exporting` is in the enum but never set at
   runtime — export is on-demand — so no node is needed for it, but the unknown-status fallback below
   covers it regardless.)

## Proposed Solution

A **focus + context horizontal journey** driven by a small client-side **state machine** with a
**min-dwell queue**, rendered over **stable DOM** (built once, mutated via classes/transforms —
never `innerHTML`-rebuilt during a run).

```
PROCESS PIPELINE                              ⤢ expand all

 ●────●────◉────○────○────○────○────○
 Ing  Nrm  Enrich Idn  Res  Jdg  Mat  Fin   tiny abbreviated labels; active = bold + larger
 ●━━━━━━━━━●· · · · · · · · · · · · ·  3 / 8  fill + marker + live count
 ▸ Identifying FOLIO concepts…               active stage's description, below the track

 ●━●━●━●━●━●━●━●  ✓ Complete  (holds ~2s) ──→  ✓ Pipeline complete   ⤢
```

Carried forward from the brainstorm (all 8 locked decisions — see brainstorm doc):
horizontal focus+context walk; **tiny labels always** (compact ≠ hidden); active description **below**
the track; **fill + marker + live count** position cue; `⤢` **expand-all**; **hold ~2s then collapse**,
re-expandable; **min-dwell ≥600ms + queue**; **entrance ease-in** on phase→running.

## Technical Approach

### Architecture: a `PipelineJourney` controller (single source of truth)

Replace the `innerHTML`-rebuild model with a small controller object that owns one canonical
**current index** and renders by mutating persistent nodes. Four visual representations — marker
position, fill width, magnified node, and the `N / total` count — must be driven from that **single
index**, never updated independently (prevents desync during fast-forward).

- **Build once:** on first use, render the full `<ol>` of stage `<li>` nodes once (stable DOM).
  Thereafter only toggle state classes and set `transform`/`width`/`textContent`.
- **Status → order map** with a **monotonic guard:** map every backend status to a canonical visual
  index. The marker **never moves backward** — if an incoming status maps to an index `≤` current,
  hold (covers the parallel-phase `identifying`/`enriching` race and any future backend reordering;
  console-warn on regression so backend changes are caught).
- **Min-dwell queue:** each stage holds focus `≥ DWELL_MS` (≈600ms). Bursts of fast SSE statuses are
  enqueued so the marker visibly **steps through every node**, never teleports (also handles the
  polling fallback jumping 2+ stages between 500ms ticks — enqueue all intermediate nodes).
- **Terminal latch:** once `completed`/`failed` is reached, subsequent `status` calls are ignored
  (late buffered SSE events or a stale poll can't re-animate a finished journey).
- **Reset:** a new run (`renderProgressStages('pending')` from submit/reset) **cancels all queued
  timers, clears the latch, resets index, clears error state, and re-expands** if collapsed.
- **Instant vs animated paths:** the walk/queue/hold runs **only** for the two dynamic drivers (SSE
  `status` `:5644`, poll `job.status` `:5592`). All **7 fixed-value call sites** (first-paint, cache
  restore, demo load, reset, terminal) take an **instant, no-walk** path. Make this structural (a flag
  like `{ animate: false }`), not inferred from the status value.

### Corrected stage model (the bug fix)

Canonical visual order = **true emission order**:

| # | Node (full / abbrev) | Backend status(es) mapped |
|---|----------------------|---------------------------|
| 1 | Ingest / Ing | `ingesting` |
| 2 | Normalize / Nrm | `normalizing` |
| 3 | Enrich / Enr | `enriching` |
| 4 | Identify / Idn | `identifying` (parallel phase — may be skipped on symbolic-only runs; render `done` once a later status arrives, never stuck) |
| 5 | Resolve / Res | `resolving` |
| 6 | **Judge / Jdg** | `judging` |
| 7 | **Match / Mat** | `matching` |
| 8 | **Finalize / Fin** | `extracting_individuals`, `extracting_properties` (+ the TripleEnrichment/Metadata tail, which set no status); also the catch-all for any **unknown** status. Count maxes at `8/8` only on `completed`. |

**Unknown-status fallback (durable fix):** any status not explicitly mapped → resolve to the
**Finalize** node (node 8) with a generic "Finalizing…" description, keep `phase='running'`, and never
move the marker leftward. **An unmapped status must never hide the component or regress the marker.**

### Animated elements (reuse existing primitives)

- **Magnified active node:** reuse the existing `font-size` transition on `.ppl-step-label`
  (`:2414`, already animates 12px↔14px) — the magnification primitive already exists. Match the
  Ollama wizard stepper's `active/done/error` state-class naming (`:2871`).
- **Marker + fill:** a determinate fill (`width` transition, like `.wizard-progress-fill` `:2909`)
  with a marker pin at the active node; transition `transform`/`width` on specific elements only.
- **Below-track description + `N / total` count:** updated via `textContent` on persistent nodes.
- **Entrance:** on `phase→running`, ease in (height/opacity grow). Suppress on first paint/restore
  via a `no-transition`-style guard (mirror the existing `main.no-transition` pattern at `:4213`).
- **Completion:** hold filled track ~2s, then ease-collapse to the existing `#pplDone` one-liner
  (`:5918`); re-expand restores the **persisted final** journey (no walk replay).

### Reduced-motion (`prefers-reduced-motion: reduce`) — net-new, project requirement (ENHC-04)

There are **zero** reduced-motion guards in the file today. Add a `@media (prefers-reduced-motion:
reduce)` block AND a JS check (because the queue/dwell is JS-timed, a CSS media query alone won't
catch it):
- No marker/fill slide, no magnify transform, no entrance grow, no 2s hold — apply states instantly.
- **Drop the artificial min-dwell** under reduced-motion (reflect true backend state immediately) —
  the perceptual reason for the queue no longer applies.

### Accessibility

- `role="progressbar"` + `aria-valuenow`/`aria-valuemax` on the track container — exposes progress
  semantically and lets AT announce per its own settings (storm-free).
- **aria-live milestones only:** announce start, completion (`N annotations`), and failure (`at
  <stage>`) — never per-node. Per-node motion is decorative (`aria-hidden` the marker).
- **Non-color cues:** done = filled/check glyph, active = bold+larger+description, error = `×` glyph,
  todo = outline. Keep the per-`<li>` `aria-label` (`:5912`) but outside any live region.

### Performance (from `.planning/research/PITFALLS.md`)

- Transition **specific element selectors**, never `:root`/`html` CSS variables (forces full-page
  recalc per frame). Cache `getComputedStyle()` theme reads once per cycle. Batch any dependent
  re-render via `requestAnimationFrame`.

### Layout / fit (historical #1 failure)

- Left column usable width can be ~318px (`main` grid `:663`/`:673`; `.panel-left min-width:0`
  `:687`). **Nodes must never wrap to a second row.** Use abbreviated off-focus labels; contain
  horizontally with `overflow-x` handling like `.dag-container` (`:1072`) if needed.
- Active full label + description go **below** the track so node magnification stays bounded.
  **Test magnification on the first and last node** (edge magnification clips). Description line
  **truncates with ellipsis** (single line) — never reflows the track.
- Completion collapse must not cause layout shift that yanks the results list under the cursor.

## Implementation Phases

### Phase 1 — Correct stage model + stable DOM (correctness; fixes the two bugs even with no animation)
- Reorder canonical stages to emission order (Judge before Match); add status→index map + monotonic
  guard + unknown-status fallback (kills the backward-jump and the mid-run disappear).
- Refactor `renderProgressStages()` to build stable DOM once and mutate, with an `animate` flag;
  route the 7 fixed call sites to the instant path.
- **Exit:** a real run at `:8731` walks Ingest→…→Match→Finalize→complete with no backward jump and
  no disappearance, even before fancy animation.

### Phase 2 — The walk: marker, fill, magnification, queue/dwell
- Add marker + fill + `N/total` count; magnify active node; below-track description.
- Implement min-dwell queue stepping through enqueued stages; single-source-of-truth index.
- **Exit:** the focus visibly walks left→right; sub-second bursts still step through every node.

### Phase 3 — Terminal/error/reset/entrance/collapse semantics
- Terminal latch; bounded fast-forward on `complete` (accelerated ~150–200ms/stage, total cap ≤~1s,
  else snap to 100% → hold); freeze-at-last-started on `failed` (errored node distinct, fill stops,
  future nodes aborted/muted); entrance ease-in; ~2s hold → collapse; re-expand persisted final.
- Full reset on re-run; stale-job guard (old `currentJobId` SSE can't drive a new walk);
  `visibilitychange` reconcile to latest status on tab refocus.

### Phase 4 — Accessibility + reduced-motion + polish
- `role="progressbar"`, aria-live milestones, non-color cues; reduced-motion fallback (CSS + JS);
  subtle indeterminate pulse on a genuinely slow (LLM) active node so it doesn't read as frozen.

## Alternative Approaches Considered

- **Vertical comet / sliding-dot / filling-rail** (brainstorm options A/B/D) — rejected by user in
  favor of horizontal journey (see brainstorm).
- **Keep `innerHTML` rebuild, add CSS animation** — rejected: nothing persists to animate (root cause
  of all prior "it doesn't walk" reports).
- **Backend reorder so match precedes judge** — out of scope; the UI must reflect real emission order.

## System-Wide Impact

- **Interaction graph:** SSE `status` (`:5644`) and `pollJob` (`:5592`) are the only dynamic drivers;
  `complete` (`:5725`–`:5736`) is terminal; `error` (`:5750`) may switch to polling. The new
  controller sits behind `renderProgressStages()` so **all** callers benefit without touching call
  sites individually (besides passing the `animate` flag from the 2 dynamic drivers).
- **Error propagation:** distinguish an SSE **transport** error (→ polling fallback, NOT a pipeline
  failure visual) from `job.status === 'failed'` (→ error visual). Don't flash the failed state on a
  transport hiccup.
- **State lifecycle risks:** queued dwell timers must be cancelled on reset/terminal/new-run to avoid
  leaking into a subsequent walk; terminal latch prevents resurrection by late events.
- **API surface parity:** none — purely frontend; backend status contract unchanged (we adapt to it).
- **Integration scenarios:** cached re-submit (no stream — instant complete); symbolic-only run (LLM
  nodes skip); SSE→poll handoff mid-run; double-submit; tab backgrounded mid-walk.

## Acceptance Criteria

### Functional
- [ ] Real run at `:8731` with a **fresh** doc: focus walks left→right through all visible nodes with
      **no backward jump** and **no mid-run disappearance**.
- [ ] Marker, fill, magnified node, and `N / total` count stay in sync at all times.
- [ ] Sub-second stage bursts: every node still gets a visible ≥600ms moment (queue).
- [ ] `complete` mid-walk fast-forwards (bounded ≤~1s) then holds ~2s and collapses; re-expand shows
      the persisted final journey (no replay).
- [ ] `failed` mid-walk freezes the marker at the last *started* stage, marks it errored, stops the
      fill, mutes un-run nodes; collapsed line reads "✕ Pipeline failed".
- [ ] First paint / cache restore / demo load / reset render the correct state **instantly** (no walk).
- [ ] Re-run on the same page fully resets and walks again; no leaked timers; stale-job events ignored.
- [ ] `⤢` expand-all reveals full labels + descriptions for every stage; independent of the
      collapse/re-expand toggle.

### Non-Functional (a11y / perf)
- [ ] `prefers-reduced-motion: reduce`: no slides/transforms/hold; min-dwell dropped; states instant.
- [ ] `role="progressbar"` with valuenow/valuemax; aria-live announces milestones only (no storm).
- [ ] Every state has a non-color cue.
- [ ] No animation of `:root` CSS variables; `getComputedStyle` reads cached; dependent renders rAF-batched.

### Layout
- [ ] At ~318px column width: **no wrapping** to a second row; edge-node (first/last) magnification
      does not clip or push nodes off-screen; long description truncates to one line.
- [ ] Completion collapse causes no jarring layout shift in the left column.

### Quality Gates
- [ ] Verified via Chrome DevTools MCP at `:8731` with a fresh document (per project convention).
- [ ] Backend test suite still green (no backend changes expected, but confirm).

## Risks & Mitigations
- **Re-introducing a rejected pattern** → cross-check against the 7 rejected designs in the handoff
  before finalizing visuals.
- **Test-condition false negatives** → only judge at `:8731`/Railway with a NEW doc; cached re-submits
  skip the stream.
- **Backend status order drift** → monotonic guard + console-warn surfaces it.

## Resolved Decisions

1. **8-node model (`N/8`) — APPROVED by user 2026-05-24, knowingly deviating from the brainstorm's
   7-node lock.** A dedicated **"Finalize"** node (node 8) covers `extracting_individuals/properties`
   plus the silent TripleEnrichment/Metadata tail, so the post-Match work has its own visible step
   and the live count only reaches `8/8` at true completion (avoids a "stuck at 7/7" read).

## Open Questions

1. **Is `Identify` worth its own node** given it runs in the parallel phase and may not emit on
   symbolic-only runs? Recommended: keep it, render `done` if skipped.

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-05-24-pipeline-journey-ui-brainstorm.md](../brainstorms/2026-05-24-pipeline-journey-ui-brainstorm.md)
  — carried forward: horizontal focus+context walk, tiny-labels-always, fill+marker+count, expand-all,
  hold-then-collapse-re-expandable, min-dwell+queue, no `innerHTML` rebuild.
- **Prior-art / rejected designs:** `.planning/PIPELINE-UI-HANDOFF.md` (7 iterations + test gotchas).

### Internal references (file:line)
- `renderProgressStages()` `frontend/index.html:5891`; 7-stage array `:5896`; state logic `:5901`–`:5916`.
- Markup `#pplWrap` `:3252`–`:3257`; pipeline CSS `:2357`–`:2419`; `pplPulse` `:2409`; label font-size
  transition `:2414`.
- SSE: `startSSE` `:5631`, EventSource `:5640`, `status` `:5642`–`:5647`, `complete` `:5725`–`:5736`,
  `error` `:5750`; poll driver `:5574`–`:5611`.
- 9 call sites: `:3835`, `:4139`, `:4221`, `:5525`, `:5592`(dyn), `:5644`(dyn), `:5732`, `:5736`, `:10656`.
- Layout: `main` grid `:663`/`:673`, `.panel-left` `:687`, `.pipeline-progress` `:2323`;
  wizard stepper analog `:2871`–`:2913`; `.dag-container` horizontal-scroll `:1072`.
- Labels/tooltips `:3855`/`:3863`; CSS tokens `:13`–`:57` (raw), `:63`–`:121` (dark), `:189`–`:245` (light).
- Backend: `JobStatus` `backend/app/models/job.py:14`–`26`; status set sites — `ingestion_stage.py:16`,
  `normalization_stage.py:17`, `orchestrator.py:409`, `llm_concept_stage.py:23`, `resolution_stage.py:171`,
  `branch_judge_stage.py:20`, `string_match_stage.py:38`, `individual_stage.py:87`, `property_stage.py:50`.

### Learnings applied
- `.planning/research/PITFALLS.md` — never animate `:root` vars; cache `getComputedStyle`; rAF-batch.
- `.planning/research/FEATURES.md` / `v1.0-REQUIREMENTS.md` ENHC-04 — reduced-motion is a project
  requirement; aria-live in-place updates to avoid storms.
- `.planning/quick/260523-box-.../260523-box-SUMMARY.md` — current one-word labels; prior `nowrap`+9px fix.

## Verification (2026-05-24, Chrome DevTools @ :8731)

Browser-verified:
- **Real fresh-doc run:** marker walked monotonically to Finalize; the `extracting_*` tail mapped to
  the Finalize node (NO mid-run disappearance), and it dwelled there with the pulse while Ollama ran
  (NO backward Judge→Match jump). State sequence stayed monotonic (`ddddddda`).
- **Complete:** all-8-done hold, then collapse to "✓ Pipeline complete ⤢" after ~2s.
- **Failed mid-walk (Resolve):** froze errored at idx4 (`ddddettt`), future stages todo, then "✕ Pipeline failed ⤢".
- **Terminal latch:** a late `enriching` status after completion was ignored.
- **Narrow column (panel 350px / track 307px):** all 8 labels on ONE row (no wrap), description truncates with ellipsis.
- **Expand-all (⤢):** full vertical legend of 8 stages (name + description, state-colored dots).
- **a11y:** `#pplTrack` `aria-valuenow` updates with the marker; `role="progressbar"`; aria-live announces milestones only.
- **Backend suite:** 674 passed (frontend-only change; no backend code touched).

Implemented but not browser-emulated this session (logic + CSS in place): `prefers-reduced-motion`
fallback (DevTools cannot emulate the reduced-motion media feature here) — worth a manual pass with the
OS flag set. Open question #2 (Identify as its own node) was kept as a node; renders `done` if skipped.
