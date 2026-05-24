# Process Pipeline UI — Handoff for Compound Engineering Brainstorm

**Date:** 2026-05-24 · **Branch:** `dev` (auto-deploys to Railway DEV) · **File:** `frontend/index.html` (single-file vanilla JS, no build step)

## The ask (in the user's words)
The "Process Pipeline" progress indicator (left column, under **DOCUMENT INPUT**) should feel like a *live pipeline*. During processing it should **expand automatically** and the active stage should **"walk along the path"** — a visible, animated progression through the stages. After 6+ iterations it still doesn't match the user's mental model. The user wants to **brainstorm the design fresh** (this doc exists so they can `/clear` first).

## Current complaints (still open)
1. **During processing it isn't expanding automatically.**
2. **It isn't "walking along the path."**

## ⚠️ CRITICAL testing gotcha — check this FIRST (likely why it "looks broken")
`const API = window.location.origin`. The pipeline only animates when a **real job streams stage updates**. Two traps have repeatedly made a *working* component look broken:
- **Wrong URL:** Open **http://localhost:8731** (FastAPI serves the frontend same-origin). At **http://localhost:8732** (standalone static server) the backend is unreachable → `/health` 404s → no job runs → the pipeline never enters "running" and looks static/hidden. On **Railway DEV** it's same-origin (works) — but confirm the deploy actually updated before judging.
- **Cached document:** Re-submitting an *identical* document returns a **cached** result that completes instantly **without streaming the stage progression** → the pipeline jumps straight to "done" and never visibly walks. **Always test with a NEW/changed document.**

Before redesigning, confirm the user is testing at `:8731`/Railway with a fresh document. The "not walking" symptom may be a test-condition artifact, not a code bug.

## How it's wired
- **Markup** (~`index.html:3223`): `<div class="ppl" id="pplWrap" data-phase="idle"><div class="ppl-title">Process Pipeline</div><ol class="ppl-steps" id="pplSteps"></ol><div class="ppl-done" id="pplDone"></div></div>`
- **CSS** (~`index.html:2357`): `.ppl[data-phase=...]` controls visibility; `.ppl-step` is a vertical stepper (node = `::before`, rail = `::after`); states `.done/.active/.error`; `@keyframes pplPulse` on the active node; active label emphasized (accent, 14px, inline description).
- **Render** (~`index.html:5852`): `renderProgressStages(currentStatus)` — sets `wrap.dataset.phase` (`idle|running|done|failed`), rebuilds the 7 `<li.ppl-step>` (state class + `title` for hover desc), sets the done-line text. **Called from ~9 sites** with statuses, driven by the SSE stream.
- **Stage label/desc maps** (~`index.html:3821`): `STAGE_LABELS`, `STAGE_TOOLTIPS`.
- **Backend statuses** (`backend/app/models/job.py` `JobStatus`): `pending, ingesting, normalizing, enriching, identifying, resolving, matching, judging, completed, failed` (+ `extracting_individuals/properties`, `exporting`). Each stage sets its status: ingestion_stage→INGESTING, normalization_stage→NORMALIZING, orchestrator→ENRICHING, llm_concept_stage→IDENTIFYING, resolution_stage→RESOLVING, string_match_stage→MATCHING, branch_judge_stage→JUDGING. **Note:** these stream over SSE and can advance in well under a second each (some LLM stages take longer) — fast stages may be imperceptible without a minimum animation dwell.

## Current behavior (commit `653b4d5`)
- **idle** (pending/unknown): `#pplWrap` hidden (`display:none`).
- **running**: whole vertical list visible; active row = accent + bold + pulsing node + inline description; done rows green on a filling green rail; to-do dim. The active row is the "highlight" that moves down as statuses advance (class swap, **not** an animated token).
- **done/failed**: steps hidden → single "✓ Pipeline complete" / "✕ Pipeline failed" line.
- No chevron, no manual toggle.

## Iteration history — what was tried & REJECTED (do NOT repeat)
1. Horizontal chips (9px) → too small, wrapped to 2 lines.
2. Chevron "flow" (`›` connectors) → reverted; disliked.
3. Horizontal node-track + single active label → stage names hidden behind tooltips; "can't see the stages."
4. Vertical stepper, collapsible via chevron → "hides everything."
5. Auto-collapse/expand on phase transitions (chevron) → still hid stages.
6. Accordion: collapsed shows ONE representative stage (Ingest before / Judge after) → "not what I described."
7. **(current)** Appears-on-enrich, full list, collapses to one-line after → "still isn't expanding automatically / not walking along the path."

**Recurring miss:** the assistant kept adding *hide/collapse* affordances (chevron, accordion). The user wants the **full pipeline visible during processing** with a **visibly animated walk** of the active state along the path. To the user, **"collapsed" seems to mean "compact," not "hidden."** And **"expand automatically"** may mean a literal **entrance animation**, and **"walk along the path"** a literal **moving marker / progressively filling path**, not just a CSS class swap.

## Open questions for the brainstorm
1. **Test conditions:** Is the user testing at `:8731`/Railway with a *fresh* (non-cached) document so a real stage stream actually fires? (See gotcha above.)
2. **"Expand automatically":** entrance animation (height/opacity grow), a size change, or just "appear"? What should the *expand* motion look like?
3. **"Walk along the path":** a moving/sliding token, a progressively filling rail with a moving head, a pulse that hops node→node, a shimmer traveling the path? Reference any product they've seen do this well.
4. **Orientation:** vertical list (current) vs a horizontal "path", or something more literal (a track/road the marker travels)?
5. **After completion:** stay fully visible, collapse to one line, or disappear?
6. **Perceptibility:** should each stage have a minimum dwell/animation time so the walk is visible even when a backend stage completes in <1s?
7. **Scope of stages:** show the 7 high-level stages (current) or the finer 14-stage pipeline?

## How to run & verify
- Local backend (serves frontend same-origin): `cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8731 --reload` → open **http://localhost:8731** → paste a **NEW** legal doc → click **Enrich**.
- Verify UI with Chrome DevTools MCP (project convention). `renderProgressStages('ingesting'|'enriching'|'completed')` can be called in the console to drive states without a job.
- Deploy: `dev` → Railway DEV (auto). PROD = `main` → openlegalstandard.org (NOT shipped; all pipeline work is dev-only). Several other DEV-only changes are also pending PROD (Annotations chip; Thinking/Debug label shortening). Confirm with the user before any PROD ship.

## Relevant commits on `dev` (quick task `260523-box`)
`653b4d5` (current, appears-on-enrich) · `b4b6d40` · `cc5a78a` (accordion repr. stage) · `e93a6bb` (auto-disclosure) · `fde0aa3` · `87b9662` · `1786505` (vertical stepper) · `8f71340` (node track) · `2403b64` (revert chevron) · `4d1fae1` (chevron, reverted). Earlier same task: shortened "Show Thinking"→"Thinking", "Debug Mode"→"Debug", and stage labels to one-word forms.
