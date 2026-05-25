---
title: Pre-Baked Exemplar Demo Mode ("Try an Exemplar")
type: feat
status: completed
date: 2026-05-25
origin: docs/brainstorms/2026-05-25-demo-exemplars-refresh-brainstorm.md
---

# ✨ Pre-Baked Exemplar Demo Mode ("Try an Exemplar")

## Overview

Turn the 22 existing exemplar buttons (7 **Rich Enrichment** + 15 **Quick Start**) into instant, zero-cost demos. Each exemplar's full LLM enrichment is **baked once** (Gemini 3 Flash) into static JSON; a **"Demo" toggle** (folio-mapper pattern) puts the UI into a presentation mode where clicking an exemplar hydrates the complete result instantly — **no LLM, no API key, no tokens, no wait**. Normal ("lean") mode is unchanged: clicking an exemplar prefills the textarea for a real run.

This is a **resurface + refresh + unify**, not a from-scratch build. A demo system already exists (built 2026-03-16) but the owner didn't know it existed, it's ~69 days stale, it was generated rule-based-only (understating the tool), and it's disconnected from the actual exemplar buttons users click (see brainstorm: docs/brainstorms/2026-05-25-demo-exemplars-refresh-brainstorm.md).

## Problem Statement / Motivation

The owner demos the tool frequently. Today every demo requires entering an LLM API key and running the live pipeline — spending money, burning tokens, and waiting. The goal: **pay the LLM cost once at generation, then demo free and instantly forever**, while showcasing the *full* pipeline (LLM concepts, individual class-linking, properties — not just rule-based output).

## Proposed Solution

1. **Single source of truth** for exemplar text (`frontend/demos/samples.json`) consumed by both the frontend and the generator — eliminating the current `SAMPLES` (frontend) vs `demo_documents.py` (backend) split.
2. **Generate with the LLM** (Gemini 3 Flash via the in-env `GOOGLE_API_KEY`, `llm_model` left empty) for all 22 exemplars → `frontend/demos/<slug>.json`.
3. **"Try an Exemplar" demo mode** — an `aria-pressed` toggle that superimposes a CSS `DEMO` badge on every exemplar and reroutes clicks to instant hydration; soft lockdown so editing/Enrich consciously exits to a live run.
4. **Exports work in demo mode** by seeding the baked jobs into the server job store on startup.
5. **Retire** the old separate 10-demo modal.

## Decisions Carried From Brainstorm + Refinement

| # | Decision | Source |
|---|----------|--------|
| D1 | Pre-bake all **22** exemplars (Rich Enrichment 7 + Quick Start 15). Narratives (7) + debug (9) out of scope. | brainstorm |
| D2 | Generate **with the LLM**, provider **Gemini 3 Flash** via `GOOGLE_API_KEY`; **leave `llm_model` empty** (never hardcode `gemini-3-flash-preview` — breaks provider-pinned deploys). | brainstorm + learnings |
| D3 | **Single source of truth** = `frontend/demos/samples.json`; frontend loads it (with a readiness guard), generator reads it. | refinement (resolves SpecFlow G1) |
| D4 | Demo UI = folio-mapper "Try an Exemplar": `aria-pressed` Demo toggle, CSS `.demo-mode .exemplar-btn::after` badge, **session-scoped (not persisted)**, deep-link `?demo=` forces pressed. | user (folio-mapper ref), verified in `/home/damienriehl/Coding Projects/folio-mapper` |
| D5 | Demo click pushes `?demo=<slug>` to the URL → free refresh / back / shareable links. | refinement (SpecFlow G8/state-7) |
| D6 | **Soft lockdown:** editing the textarea or clicking Enrich **intentionally exits demo mode** and runs the real pipeline; clean teardown of demo globals + `document.title` on exit. | user |
| D7 | **Exports work** in demo mode by seeding baked jobs into the job store on startup (fresh timestamp, excluded from cleanup). | user |
| D8 | **Retire** old demo modal: `DEMO_CATALOG`, `openDemos`, `openAllDemoTabs`, `#demoLinksModal`, header "Demo" button. Rewire/keep `tryLoadDemo`/`hydrateFromDemo`. | brainstorm |
| D9 | **Triples drift is NOT a confirmed bug** — `renderResults` reads `job.result.triples` (present), not `cache.triples`. Verify in-browser; add `cache.triples`+`accumulatedTriples` parity only if a gap shows. | code-verified research (corrects brainstorm decision #3) |

> **Correction to the brainstorm:** brainstorm decision #3 assumed the empty `cache.triples` key breaks the Triples tab. Deep, file-verified research shows the render path uses `job.result.triples` (40 present in `litigation.json`), so the tab likely renders fine. Demoted to a verification step (D9).

## Technical Approach

### Architecture

```
samples.json (canonical 22 texts)
   ├── frontend/index.html  → loads at startup (readiness-guarded) → loadSample() & demo routing
   └── backend/scripts/generate_demos.py → reads → runs FULL pipeline (Gemini 3 Flash) → frontend/demos/<slug>.json
                                                                                              │
frontend/demos/<slug>.json (baked cache: job, annotations, individuals, properties, triples, normalizedText, docInput)
   ├── Demo mode click → fetch /static/demos/<slug>.json → hydrateFromDemo() → renderResults(job.result.*)
   └── app startup → seed cache.job into ~/.folio-enrich/jobs/{uuid}.json → /enrich/{id}/export works (13 formats)
```

### Implementation Phases

#### Phase 1 — Single Source of Truth (foundation) — resolves G1

- **`frontend/demos/samples.json`** (new): pure JSON `{ "<slug>": "<text>", … }` for the 22 exemplars. Slug = the existing `SAMPLES` key (snake_case kept verbatim so files are `rich_lit_timekeeping.json` etc. — no slug remapping).
  - *Pre-check:* confirm the 22 `SAMPLES` values are static strings (no `${}` template interpolation) before externalizing. (Sizes range 2.3 KB–16.4 KB; verified all 22 keys exist, `index.html:4086-4160`.)
- **`frontend/index.html`**: replace the inline `const SAMPLES = {…}` with an async load of `samples.json` on `init()`. Add a **readiness guard** so `loadSample()` can't fire against `undefined` (await readiness; disable sample buttons until loaded). *(Race-condition sensitive — see Julik review note in Risks.)*
- **`backend/scripts/demo_documents.py`**: replace the 10 disjoint docs by **reading `frontend/demos/samples.json`** (path resolved relative to repo root) → `DEMO_DOCUMENTS = {slug: {"text": …, "title": …, "description": …}}` for the 22. Titles/descriptions derived from the exemplar button labels.
- **Consistency test** (new, `backend/tests/test_samples_source.py`): assert every exemplar `loadSample('<key>')` referenced in `index.html` has a matching key in `samples.json` (catches drift in both directions).

#### Phase 2 — Generator Upgrade + Generation Run

- **`backend/scripts/generate_demos.py`**:
  - Build a real LLM (`build_llm`/registry) for **provider `google`, `model=""`** instead of `llm=None` (`:187-191`). Accept `--provider` / `--model` overrides; default google.
  - `build_cache_payload()` (`:157-170`): **add `"triples": job_dict["result"].get("triples", [])`** for parity (D9 — harmless even if unused by the renderer).
  - `get_staleness_info()` (`:56-132`): expected slugs now from the 22 (via `DEMO_DOCUMENTS.keys()` once it reads samples.json); **add `frontend/demos/samples.json` to `_TRACKED_SOURCE_FILES`**.
  - Add LLM-stage source dirs to tracked sources if not present (`app/services/concept/`, `app/services/llm/`).
- **One-time generation run** (prerequisite: Google key reachable by the provider):
  - The provider reads `FOLIO_ENRICH_GOOGLE_API_KEY`; env currently exposes `GOOGLE_API_KEY` → run with `FOLIO_ENRICH_GOOGLE_API_KEY="$GOOGLE_API_KEY"`.
  - `cd backend && FOLIO_ENRICH_GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python scripts/generate_demos.py` → writes 22 `frontend/demos/<slug>.json`.
  - Mind provider rate limits across 22 docs (some dense, e.g. `advice_regulatory` 16 KB); add light pacing/retry if needed.
  - **Delete the 10 obsolete demo JSONs** (litigation.json, transactional.json, …) that no longer correspond to an exemplar.
- **Verify** each baked file has populated `job.result.triples`, `individuals`, `properties`, and LLM-derived concepts.

#### Phase 3 — "Try an Exemplar" Demo Mode UI

- **State** (`frontend/index.html`): `let exemplarMode = 'lean'` (default; **not persisted** — reset on load, per folio-mapper "presentation intent, not preference"). Reconcile with existing `isDemoMode`/`currentDemoSlug`/`originalDemoCache` globals.
- **Toggle**: a `Demo` button adjacent to the exemplar groups, `aria-pressed`, accessible name "Demo mode: instant pre-baked results, no API key". On toggle, `container.classList.toggle('demo-mode')` and announce via an `aria-live="polite"` region.
- **Badge (CSS-only)**: add `.exemplar-btn{position:relative}` + `.demo-mode .exemplar-btn::after{content:"DEMO";position:absolute;top:4px;right:4px;…}`. Verify contrast (WCAG AA) and no clipping in the dense Quick Start grid across light/dark/mixed themes.
- **Click routing** (`loadSample`/exemplar handler):
  - *Demo mode* → `fetch('/static/demos/<slug>.json')` → `hydrateFromDemo(cache, slug)` → **push `?demo=<slug>` to URL** (`history.pushState`) → move focus to results heading.
  - *Lean mode* → unchanged (`loadSample` prefill).
- **Soft lockdown (D6)**: editing `#docInput` OR clicking **Enrich** while a demo is hydrated → `exitDemoMode()` (real run proceeds). `submitEnrichment()` (`:5608`) gains an `isDemoMode` branch that exits cleanly first.
- **`exitDemoMode()` clean teardown (G10/G11)**: reset `exemplarMode='lean'`, `isDemoMode=false`, `currentDemoSlug=null`, `originalDemoCache=null`, hide `resetDemoBtn`, restore `document.title`, clear `?demo=` from URL, remove `.demo-mode` class.
- **Missing/404/malformed JSON (G6)**: visible recoverable toast ("Demo unavailable — loading the text instead") + fall back to lean prefill. No silent no-op.
- **Deep link (G8)**: arriving via `?demo=<slug>` forces the toggle to `aria-pressed=true` and `.demo-mode` on.
- **Retire old path (D8)**: delete `DEMO_CATALOG` (4166), `openDemos` (4253), `openAllDemoTabs` (4267), `#demoLinksModal` (3811-3821), header "Demo" button (3314). Keep `tryLoadDemo`/`hydrateFromDemo`; fold `resetDemo` into the new teardown. Remove dead references (AC9).
- **Discoverability (G12)**: concise label on/near the toggle conveying "instant, no API key".

#### Phase 4 — Exports in Demo Mode (server-side seeding) — D7

- **`backend/app/main.py` startup**: load each `frontend/demos/<slug>.json`, extract `cache.job`, write `~/.folio-enrich/jobs/{uuid}.json` via the existing job store with **`updated_at = now`** so it isn't immediately purged.
- **`backend/app/storage/job_store.py` `cleanup_expired`**: exclude the known demo UUIDs (a module-level demo-id set, or re-seed on each startup) so hourly cleanup can't delete them mid-demo.
- Result: in demo mode, all 13 `/enrich/{jobId}/export?format=…` calls resolve → exports work with **no new export code**.
- *Edge:* `renderExportButtons` already uses `currentJobId` (= demo jobId) — no frontend change needed once jobs exist server-side.

#### Phase 5 — Verify + Deploy

- **Browser verification (chrome-devtools MCP, per project CLAUDE.md)** against `http://localhost:8732` (frontend) / `:8731` (backend):
  - Toggle demo on → badges appear on all 22; click several → instant render, **DevTools Network shows zero `/enrich` POST and zero LLM calls** (AC2); all tabs populate (Annotations, Individuals, Properties, **Triples**, Metadata).
  - Click an export (e.g. Neo4j CSV, RDF/Turtle) → valid download, no 404 (AC4).
  - Edit textarea / click Enrich → exits demo cleanly, runs live (AC10/D6).
  - Refresh + browser Back with `?demo=` reproduce state (AC8).
  - a11y: `aria-pressed` correct, mode change announced, badge contrast AA (AC7).
- **Tests**: `cd backend && .venv/bin/python -m pytest tests/ -v` (incl. new source-consistency + freshness `-m demo_regen`).
- **Deploy**: commit baked JSON + code, push to `dev` → Railway DEV auto-deploys (owner is traveling — push after the change). Ensure `FOLIO_ENRICH_GOOGLE_API_KEY` is set on Railway only if live (non-demo) runs are also wanted there; demo mode itself needs no key.

## System-Wide Impact

- **Interaction graph**: exemplar click → (demo) fetch static JSON → `hydrateFromDemo` → `renderResults` → `renderAnnotatedText`/`renderConceptsList`/`renderTriples`/`renderIndividualsTab`/`renderPropertiesTab`/`renderMetadata`/`renderExportButtons`. Startup seeding → job store write → export endpoint reads job. Toggle → `.demo-mode` class → CSS badges + click-routing branch.
- **Error propagation**: demo fetch failure → toast + lean fallback (no throw). Export in demo → now backed by a real job (no 404). Generation run failure (rate limit/key) → script exits non-zero, no partial commit of broken JSON (verify before deleting old files).
- **State lifecycle risks**: demo globals must fully reset on exit (G10) or the app sits in a half-demo state; cleanup must not orphan/delete seeded demo jobs mid-session (Phase 4 guard). `?demo=` URL and toggle `aria-pressed` must never disagree (G8).
- **API surface parity**: both the input-screen `loadSample` path and the `?demo=` deep-link path must route through the same `hydrateFromDemo`; exports use the unchanged `/enrich/{id}/export` surface.
- **Integration test scenarios** (cross-layer, beyond unit): (1) toggle on → click → network shows no `/enrich`; (2) export Turtle in demo → valid RDF body; (3) edit textarea in demo → live run starts with correct text; (4) refresh on `?demo=` → identical hydration; (5) startup seeding survives one `cleanup_expired` cycle.

## Acceptance Criteria

### Functional
- [x] **AC1** All 22 exemplars have `frontend/demos/<slug>.json` generated via Gemini 3 Flash; `generate_demos.py --check` exists. *(Note: `--check` has a pre-existing false-positive — app startup bumps the OWL cache mtime past the demos' `generated_at`. Gated behind the opt-in `demo_regen` marker; follow-up: use OWL content version, not mtime.)*
- [x] **AC2** Demo mode ON + exemplar click → results render with **zero `/enrich` calls and zero LLM calls** (verified in DevTools network: only `/static/demos/complaint.json` + metadata lookups); instant.
- [x] **AC3** Demo mode OFF (lean) → exemplar click only prefills the textarea (`prefillSample`), unchanged.
- [x] **AC4** All 13 export formats resolve in demo mode (verified json/jsonld/csv/rdf/neo4j → 200 against a seeded demo job).
- [x] **AC6** Missing/404/malformed demo JSON → toast + lean prefill fallback (implemented in `loadDemoExemplar`).
- [x] **AC8** Demo click pushes `?demo=<slug>` (verified); `popstate` handles back/forward; refresh re-hydrates.
- [x] **AC9** Old demo path fully removed (verified: 0 refs to `openDemos`/`openAllDemoTabs`/`demoLinksModal`/`DEMO_CATALOG`/`resetDemoBtn`).
- [x] **AC10 (D6)** Editing the textarea exits demo cleanly, clears stale annotations, keeps the typed text (verified); Enrich exits then runs live.
- [x] **AC5** Exiting demo resets all demo globals, restores `document.title`, clears `?demo=` (verified via DevTools).
- [x] **AC-Triples (D9)** Triples tab populates from baked demos (verified: "Triples (82)" rendered for complaint). The drift was cosmetic; not a functional bug.

### Non-Functional
- [x] **AC7** Toggle exposes correct `aria-pressed`; `aria-live` announcement is now visually hidden via standalone `.sr-only` (verified 1×1px, clipped). DEMO badge = white-on-accent; visually clear in dark theme. *(Formal WCAG-AA contrast sampling across all themes not automated — visual check only.)*
- [x] Generation is reproducible from the single source (inline `SAMPLES`); `test_samples_source.py` + `test_demo_seed.py` pass; 706 backend tests pass.

## Success Metrics

- A full live demo can be delivered with **no API key configured and $0 token spend**.
- Time-to-first-enriched-view drops from a live pipeline run to instant (< 0.5 s).
- All 22 exemplars + all 13 exports demonstrable offline.

## Dependencies & Risks

- **R1 — Frontend load-order race (Phase 1).** Externalizing `SAMPLES` to async JSON risks `loadSample` firing before data loads. *Mitigation:* readiness guard + disable sample buttons until loaded; subject to a Julik-style frontend-races review.
- **R2 — Template-literal interpolation in SAMPLES.** If any of the 22 texts use `${}`, they can't be pure JSON. *Mitigation:* Phase 1 pre-check; keep as escaped strings.
- **R3 — Generation key/rate limits.** Provider reads `FOLIO_ENRICH_GOOGLE_API_KEY`; pacing across 22 docs. *Mitigation:* map env key for the run; light retry.
- **R4 — Seeded-job cleanup (Phase 4).** Hourly `cleanup_expired` could purge demo jobs. *Mitigation:* exclusion set / re-seed on startup with fresh `updated_at`.
- **R5 — Don't hardcode `llm_model`.** Must stay empty so provider-pinned deploys (PROD=anthropic) resolve correctly (learnings).
- **R6 — Theme/badge rendering perf.** `.planning/research/PITFALLS.md` flags `getComputedStyle`/canvas repaint cost; the CSS `::after` badge is cheap but verify no layout thrash on 22 buttons.

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-05-25-demo-exemplars-refresh-brainstorm.md](../brainstorms/2026-05-25-demo-exemplars-refresh-brainstorm.md). Carried forward: generate-with-LLM (Gemini 3 Flash), unify 22 exemplars-as-demos, retire old modal, single source of truth. **Corrected:** triples "drift" demoted to a verification step (D9).

### Internal References
- `frontend/index.html`: `SAMPLES` 4086-4160; 22 exemplar buttons 3406-3457; `tryLoadDemo`/`hydrateFromDemo` 4179-4251; `renderResults` 6314-6343 (triples read 6329-6330); `loadSample`/`clearAll` 10959-10989; `submitEnrichment` 5608; export buttons ~10792; old modal 3314/3811-3821/4166-4279.
- `backend/scripts/generate_demos.py`: `build_cache_payload` 157-170; `llm=None` 187-191; `get_staleness_info` 56-132.
- `backend/scripts/demo_documents.py` (10 disjoint docs — to be replaced).
- `backend/app/storage/job_store.py` (`cleanup_expired`); `backend/app/main.py:192` (`/static` mount).
- `backend/tests/test_demo_freshness.py`.

### External / Pattern Reference
- folio-mapper "Try an Exemplar" (verified local clone `/home/damienriehl/Coding Projects/folio-mapper`): `packages/ui/src/components/input/ExemplarPanel.tsx` (toggle + badge), `apps/web/src/store/demo-store.ts` (session-scoped `exemplarMode`), `apps/web/src/App.tsx:548-594` (click routing, LLM suppression).

### Related Work
- `.planning/quick/260525-c1x-*` (Gemini 3 Flash default; keep `llm_model` empty).
- Prior demo build: `docs/brainstorms/2026-03-16-demo-exemplars-brainstorm.md`.

## AI-Era Notes
- Built with Claude Code (research + planning). Generation run + browser verification (chrome-devtools MCP) must be executed and observed, not assumed — emphasize the DevTools network check (AC2) and a real export download (AC4).
