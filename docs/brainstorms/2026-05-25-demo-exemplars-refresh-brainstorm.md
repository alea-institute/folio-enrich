# Brainstorm: Pre-Baked Exemplar Enrichments ("Try an Exemplar" Demo Mode)

**Date:** 2026-05-25
**Status:** Captured — ready for planning
**Builds on:** `2026-03-16-demo-exemplars-brainstorm.md` (original demo build)

## The Surprise

The request was: *"Build pre-made demo examples so I can demo without entering an LLM key, spending money, or burning time."*

**A demo system already exists** (built 2026-03-16): a header **Demo** button → modal → 10 pre-computed static JSON files in `frontend/demos/`, hydrated via `?demo=<slug>`. No key, no cost, instant. **But the owner who demos most didn't know it existed**, it's stale, generated rule-based-only (understates the tool), and disconnected from the actual exemplar buttons users see.

So the real work is **resurface + refresh + unify**, not build-from-scratch.

## What We're Building

**Pre-baked enrichments for the real exemplar buttons, surfaced as a "Try an Exemplar" demo mode** (modeled on the folio-mapper repo's pattern the owner likes).

Scope — every exemplar in two existing groups (`index.html:3406` and `:3425`), 22 total:

- **Rich Enrichment (7):** `rich_lit_timekeeping`, `rich_ma_timekeeping`, `rich_re_timekeeping`, `rich_motion`, `rich_order`, `rich_contract`, `rich_advisory` (dense docs, 180–392 FOLIO labels each).
- **Quick Start (15):** `motion`, `complaint`, `opinion`, `appellate`, `injunction`, `settlement`, `contract`, `nda`, `lease`, `employment`, `merger`, `advice_litigation`, `advice_regulatory`, `regulatory`, `patent`.

Source texts already live in the frontend `SAMPLES` object (`index.html:4086`); `loadSample()` (`:10959`) currently only fills the textarea, then requires a live LLM run.

**Out of scope (for now):** the 7 "Narratives" exemplars (owner named only Rich Enrichment + Quick Start). Easy to add later.

## Why This Approach

- **Generate WITH the LLM, once.** Demos must showcase full pipeline output (LLMConcept, LLM individual class-linking, LLMProperty) — not the rule-based-only output the current generator produces (`generate_demos.py:189`, `llm=None`). Pay once at generation, serve free + instant forever.
- **Provider: Gemini 3 Flash** via the `GOOGLE_API_KEY` already present in the environment (no key entry needed while traveling; the Claude Max plan can't drive the backend pipeline, which needs an API key). Bonus: Gemini 3 Flash is the product's new default, so demos mirror the real default experience.
- **Unify demos with exemplars.** Rather than a separate 10-demo modal disconnected from what users click, the 22 exemplar buttons *become* the demos. A **"Demo" toggle near the exemplars superimposes a "Demo" badge on each button**; clicking loads the pre-baked enrichment instead of running the pipeline. Recommended to **replace** the old `openDemos()` modal + `DEMO_CATALOG` (overridable if you'd rather keep both).

## Resolved Decisions

1. **Reuse the static-JSON + hydration architecture** (proven); don't rebuild.
2. **Generate all 22 with the full LLM pipeline**, provider **Gemini 3 Flash** / `GOOGLE_API_KEY` (already in env).
3. **Fix the triples format drift** — top-level `cache.triples` is empty while `job.result.triples` has data, so the Triples tab renders nothing from demos.
4. **Refresh against the current FOLIO ontology** (was ~69 days stale).
5. **Discoverability = folio-mapper "Try an Exemplar" pattern** — "Demo" control adjacent to exemplars, superimposed "Demo" badges, click-to-load pre-baked results.
6. **Demo set = the 22 Rich Enrichment + Quick Start exemplars**; Narratives deferred.
7. **Freshness guard stays valid** (timestamp-based; LLM non-determinism doesn't break it).
8. **Retire the old 10-demo modal** (`openDemos()` / `DEMO_CATALOG`) — the 22 exemplars become the single unified demo surface.

## Open Questions (for planning to settle)

1. **Where source texts live for generation:** the generator (`generate_demos.py`) reads its own `demo_documents.py`; the 22 exemplar texts live in frontend `SAMPLES`. Plan must pick a single source of truth (extract `SAMPLES` to a shared file the backend reads, vs. duplicate).
2. **Badge/affordance details:** exact "Demo mode" interaction — toggle vs. always-on badges, copy, and how "exit demo / try your own" works.

## Next

`/ce:plan`. Small-to-medium scope: single-source the 22 exemplar texts → generator tweak (LLM + drift fix) → one Gemini 3 Flash generation run → "Try an Exemplar" demo-mode UI → browser verify → Railway push (owner traveling, push after every change).
