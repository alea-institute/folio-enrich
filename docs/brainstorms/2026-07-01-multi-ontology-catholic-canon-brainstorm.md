# Brainstorm: Multi-Ontology Support — Catholic Semantic Canon

**Date:** 2026-07-01
**Status:** Brainstorm (WHAT, not HOW) — ready for `/ce:plan`
**Author:** Damien Riehl + Claude

---

## What We're Building

Let users enrich documents against a **second selectable ontology** — the **Catholic Semantic Canon** (`https://ontology.catholicos.catholic/`) — alongside the default **FOLIO**. Everything else about the app (the 14-stage pipeline, exports, individuals/properties/triples, demos, OWL auto-update) stays the same; we swap the *ontology* underneath.

FOLIO remains the default and the common case. Canon is a rarer, opt-in mode reachable via a **subtle header control**, serving both CatholicOS insiders and curious visitors.

### Scope (this milestone)
- Extract an **`OntologyService` protocol + registry** so ontologies are pluggable (FOLIO = entry #1, Canon = entry #2, N-th ontology = one more entry).
- Parameterize the **OWL update/ping machinery** per-ontology (repo coords → registry), reusing `owl_cache.py` / `owl_updater.py` / the "Manage" modal rather than rebuilding.
- Add a **subtle header switcher** that swaps the active ontology and triggers a **light rebrand** (accent/branch palette + masthead title/tagline + exemplar set). Tabs and layout unchanged.
- Author a **Canon exemplar/demo set** (real Catholic/Christian texts), including "rich enrich" high-density samples, comparable in length to FOLIO demos so they process fast. Bake them like the FOLIO demos.
- Sources: **public domain by default, plus explicitly-licensed** texts (per-source license check).

### Out of scope (YAGNI, for now)
- A separate CatholicOS-branded deployment/domain (kept *possible* via env var, not built).
- Deep theming (custom typography, hero art, iconography) — only a light rebrand now.
- User-uploaded / arbitrary third-party ontologies (registry makes it feasible later, not a goal now).

---

## Why This Approach

The repo research found the system is **already ~80% ontology-agnostic at the seams**, it's just *named and hardcoded* for FOLIO:

- **`FolioService`** (`backend/app/services/folio/folio_service.py`) is a clean singleton whose public methods (`get_all_labels`, `get_all_labels_multi`, `search_by_label`, `get_property`, `get_all_property_labels`, `get_all_branches`) already form a natural `OntologyService` protocol. Most of the 23 consumers treat concepts as opaque `(text, IRI, branch, definition)` tuples.
- **The OWL update lifecycle** (`owl_cache.py`, `owl_updater.py`, routes in `folio_update.py`, the "FOLIO Manage" modal) is complete and reusable — it just hardcodes `alea-institute/FOLIO/main`. Parameterizing the repo coordinates gives Canon the *same* ping-GitHub-for-new-OWL behavior the user asked for, with one code path for both ontologies.
- **The Canon OWL is structurally FOLIO-like** (verified 2026-07-01): ~15K `owl:Class`, 396 object-property entries, SKOS labeling (`rdfs:label` + `skos:prefLabel` + `skos:altLabel`) — the same label shape FOLIO uses. So concept matching *and* property extraction should port without redesign.
- **The demo system** is mechanically text-source-agnostic; it just needs a namespaced second `SAMPLES` set + a second baked `frontend/demos/` set + per-ontology freshness sidecars.

A registry (vs. hardcoding two ontologies) is the right call because the reusable seams are already singleton/registry-shaped — special-casing `if canon … else folio …` across 23 files would be *more* work and would re-open every file for a future 3rd ontology.

Same-app-with-light-rebrand (vs. separate site) is coherent with a subtle header switcher and keeps one deploy / one CI / one bake pipeline. The registry keeps a standalone branded deployment available later via `FOLIO_ENRICH_DEFAULT_ONTOLOGY=canon`.

---

## Key Decisions (Resolved)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Deployment model | **Same app, one deploy, + light rebrand** | Coherent with subtle switcher; one pipeline; separate site still possible via env var |
| 2 | Extensibility | **Registry for N ontologies** | Seams are already registry-shaped; Canon = entry #2; future ontology = one entry |
| 3 | Switcher UX | **Subtle header control** (recessive dropdown/segmented control, visible on hover/focus) | "Accessible but not overwhelming"; serves both audiences |
| 4 | Audience | **Both insiders + curious public** | Balances discoverability with restraint |
| 5 | Rebrand depth | **Accent palette + title/tagline + exemplar set** | Distinct identity, low design effort; layout/tabs unchanged |
| 6 | Demo sources | **Public domain by default + explicitly licensed** | Douay-Rheims/KJV, Church Fathers (CCEL), Aquinas, older encyclicals, Baltimore Catechism; per-source license check for anything modern. Modern NABRE/RSV-CE and current CCC are NOT PD. |

---

## Architecture Seams (for the plan to build on)

**Backend**
- **Extract `OntologyService` protocol** from `FolioService`; make `get_instance()` route by `ontology_id`. Keep FOLIO as the reference implementation.
- **Ontology registry** keyed by id → `{repo_owner, repo_name, branch, owl_url, base_iri, branch_config, samples_dir, demos_dir, brand}`. FOLIO coords move here from `owl_cache.py`.
- **Per-ontology OWL cache/update**: parameterize `owl_cache.py` (`_REPO_*`, `_OWL_URL`, cache filename hash) and `owl_updater.py` by ontology id; keep the idle-pipeline-wait + hot-reload + re-index behavior. Routes become `/{ontology}/update/*` (or accept an `ontology` param).
- **Branch taxonomy**: `branch_config.py` becomes per-ontology. Canon needs its own top-level branch map + colors (see open questions — derive vs. curate).
- **LLM prompt templates** (`llm/prompts/templates.py`) that enumerate FOLIO branches must become ontology-aware (branch names injected from the active ontology, not hardcoded).
- **Config** (`config.py`): add `default_ontology: str = "folio"`, `enabled_ontologies: list[str] = ["folio", "canon"]`, and the per-ontology repo registry. Add an `ontology` field to the `/enrich` request model.

**Frontend** (`frontend/index.html`, single-file)
- **Header switcher** near the Demo toggle / "Manage" affordance; drives an `ontology` state used by `/enrich`, demo loading, and CSS palette.
- **Per-ontology CSS branch-color palette** (`--branch-*` var set) swapped on switch.
- **Rebrand hooks**: title/tagline swap; masthead accent.
- **Second exemplar grid** + `SAMPLES` set; "Manage" modal re-targets the selected ontology's `/update/*` routes.

**Demos** (`backend/scripts/`)
- Canon `SAMPLES` (inline, real texts) → `extract_exemplars.py` / `demo_documents.py` gain a namespace/ontology dimension.
- `generate_demos.py` bakes Canon demos against the Canon ontology → second `frontend/demos/` set (namespaced), with per-ontology `.owl-version` / `.samples-version` / `.pipeline-version` sidecars.
- `demo_seed.py` seeds both ontologies' demo jobs at startup.

---

## Risks / To-Validate in Planning

1. **folio-python vs. arbitrary OWL (highest risk).** `_get_folio()` uses `from folio import FOLIO`, whose constructor is GitHub-repo-oriented and may assume FOLIO's specific schema/IRIs (`FOLIOTypes` enum, `get_folio_branches()`, `folio[iri]`, `object_properties`). **Must validate early** whether folio-python can load the Canon OWL as-is, or whether Canon needs a lightweight independent OWL loader (rdflib-based) that presents the same interface. The Canon's SKOS/object-property structure is encouraging, but the loader is the make-or-break unknown.
2. **Canon branch taxonomy.** Unknown whether the Canon OWL has a small, clean set of top-level superclasses (like FOLIO's ~27 branches) suitable for color-coding, or a flatter/deeper structure. Affects `branch_config` design and the graph-overlay UI.
3. **Demo bake cost/time.** FOLIO's 22-demo bake is ~60–90 min and needs an LLM key. Canon adds a second bake. Budget for it; consider a smaller initial Canon demo set.
4. **Copyright discipline.** Must verify each Canon source is PD or explicitly licensed before baking it into the repo (~committed JSON). Modern translations/catechisms are traps.
5. **Frontend sprawl.** 356 FOLIO references in one file; the switcher/rebrand must be data-driven (palette + strings from the active ontology) rather than a second hardcoded UI, or the file becomes unmaintainable.

---

## Resolved Questions

1. **UI naming (Canon mode):** Masthead reads **"CatholicOS Enrich"** when Canon is active — leads with the CatholicOS brand, ties to the broader project.
2. **Switcher control:** A low-contrast **"Ontology ▾" dropdown** in the header listing *FOLIO* / *Catholic Semantic Canon*. Neutral and self-explanatory.
3. **Canon branch taxonomy:** **Auto-derive** branches from the OWL's top-level superclasses, then hand-tune the color palette. (Falls back to hand-curation only if the OWL's top level turns out to be unusable — validate during planning.)
4. **Initial Canon demo count:** *(Default, overridable in planning)* Start **smaller — ~6–8 demos incl. 2–3 "rich enrich"** — to keep the first bake cheap, then expand toward FOLIO's ~22 once the pipeline is proven on Canon.
5. **Push policy:** **Normal push rules** — folio-enrich is an alea-institute repo, so push freely to `dev`/feature branches without asking (this feature does not fall under the CatholicOS "ask-before-push" rule).
