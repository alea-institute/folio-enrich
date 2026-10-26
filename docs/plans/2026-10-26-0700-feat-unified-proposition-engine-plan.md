---
title: Unified Proposition Engine - Plan
type: feat
date: 2026-10-26
topic: unified-proposition-engine
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Unified Proposition Engine - Plan

## Goal Capsule

- **Objective:** One engine turns any legal source, alone or in a corpus of hundreds, into flat, verified, FOLIO-tagged propositions, and both folio-enrich and folio-insights deliver that same output. A fix to extraction or tagging reaches both products at once.
- **Means:** Merge the two proposition models into one record in folio-propositions, make folio-enrich's per-document pipeline that engine, and package it so folio-insights runs it in-process for every document (KTD1, KTD8, KTD9).
- **Product authority:** Damien, inline on 2026-10-25 and 2026-10-26, recorded through Cockpit asks `folio-enrich-2026-10-25-2017-insights-into-enrich-scope` (`focus-slice`), `folio-enrich-2026-10-25-2022-insights-propositions-combine` (`combine-shape`), and `folio-enrich-2026-10-25-2046-insights-single-doc-surface` (`insights-single-doc-surface`). This plan supersedes the 2026-08-16 document/corpus boundary in `docs/plans/2026-08-16-2234-feat-proposition-system-phase-a-plan.md`, which assigned insights its own per-document extraction.
- **Active scope:** the shared record (folio-propositions), the engine and its per-document product surface (folio-enrich), and the engine's packaging for folio-insights. Rewiring folio-insights to consume the engine is a separate follow-on plan in that repo.
- **Target repos:** folio-enrich (home of this plan) for U2–U11; folio-propositions for U1. Paths are repo-relative to the unit's target repo.
- **Execution profile:** implementation goes to workers per the cockpit worker policy; the orchestrating session plans, reviews, verifies, merges, and deploys. One branch per unit or tight unit group, each landed by PR.
- **Stop conditions:**
  - Any LLM-tier benchmark run in U9 stops until Damien approves its spend estimate (a spend hard block).
  - Any change that alters flag-off exports or SSE output without a deliberate, reviewed baseline regeneration stops.
  - Any path where a model writes an IRI stops (R7).
  - Any change that breaks the existing server start command (`uvicorn app.main:app`) used by DEV and PROD deploys stops.
- **Open blockers:** none for implementation. U9's LLM tiers wait on the spend approval above.

---

## Product Contract

**Product Contract preservation:** restructured, no scope change. R2 now names the explicit status for tags that resolve to no IRI. R15 states that edits survive re-processing (previously "persist on the record"; the storage mechanism moved to KTD5). R16 says every export format instead of "all 13", since `main` now registers 15 (the two shared-schema proposition formats arrived in #44). AE4 added under R15. Problem Frame and Dependencies corrected to `main` as of `8ce29a7`. The three deferred questions are resolved in KTD5, KTD7, and KTD8.

### Summary

folio-propositions gains one proposition record that carries the best of both current models. folio-enrich becomes the single per-document engine: it extracts, verifies, tags, reviews, and exports those propositions. folio-insights runs that engine as a pinned library on every document and keeps the cross-document work on top.

### Problem Frame

Two proposition extractors, two proposition models, and two review surfaces exist today, and each holds half of what the product needs.

- **folio-insights' `KnowledgeUnit`** carries a verbatim source snippet, an anchor check, flat multi-branch FOLIO tags, and lineage, but no asserter, validator, disposition, or citation edges.
- **folio-propositions' `Proposition`**, which folio-enrich emits, carries that attribution ledger plus triples and an axiom lifecycle, but no FOLIO tags and no verbatim-anchor check.
- **The bridge:** folio-insights' `bridge_ingest` translates between the two, which exists only because of the duplication.

The folio-insights README, rewritten on 2026-10-25 (folio-insights PRs #48 and #49), now promises flat, span-grounded propositions tagged across FOLIO branches, Deontic Specification included. Neither tool delivers that end to end. Neither extractor has proven quality either: folio-enrich's Phase B lexicon (`phase-b-v1`, `backend/eval/reports/propositions/phase-b-v1.json`) matches 53 of Palsgraf's 104 gold propositions (F1 0.50), up from 7.7% recall in August, and in July a folio-insights treatise run invented units and pointed about 90% of 2,226 tags at the wrong concept. As long as two engines exist, any quality gain lands in one product and not the other.

### Key Decisions

- **One record, carved from both models.** folio-propositions holds the single proposition record, and `KnowledgeUnit` is deprecated. (session-settled: user-directed — chosen over folding all of folio-insights into folio-enrich, making folio-insights the home, or keeping both models with only a shared core: one model with each tool split by job keeps reuse without duplicate products.) Governs R1, R2, R3.
- **folio-enrich's pipeline is the only per-document engine.** folio-insights retires its own extractor and runs this engine on every document, whether a run holds one or hundreds. (session-settled: user-directed — chosen over insights keeping a separate extractor for corpus runs: Damien wants enrich's precision and recall inside insights regardless of document count.) Governs R11, R12, R13.
- **folio-insights also converts single documents.** A single document is a corpus of one, so insights needs no separate single-document mode. (session-settled: user-directed — Damien added this to the split-by-job option.) Governs R12.
- **folio-insights' per-document view shows propositions and what they cite.** (session-settled: user-approved — chosen over showing everything folio-enrich shows, or bare propositions: it keeps the products distinct on one engine.) Governs R14.
- **In-process library, not a network service.** folio-insights imports the pinned engine rather than calling a running folio-enrich. This completes the August bridge-to-library migration and keeps the insights CLI and offline runs working. Governs R11.
- **Measure before choosing the extractor.** The engine's extraction strategy is chosen by score against the gold sets, not by which repo it came from. Governs R8, R9.
- **"Proposition" names the record; "insight" stays a product word.** Code and data use proposition. The folio-insights README keeps its "insights (propositions)" phrasing.

### Requirements

**Unified proposition record (folio-propositions)**

- R1. Every proposition carries its character span, its verbatim source quote, and an anchor check recording whether the quote matches the source at that span.
- R2. Every proposition carries a flat list of FOLIO tags, each with IRI, label, top-level branch, confidence, and the path that produced it, with no hierarchy among tags; a tag that resolves to no IRI carries an explicit proposed status instead.
- R3. The record keeps the existing ledger fields (asserter, validator, disposition, citation edges, triple links, axiom status) and adds per-proposition lineage of the stages that produced or changed it.
- R4. Each proposition records the engine version that produced it.
- R5. Records persisted under earlier schema versions migrate forward without loss, as the v1-to-v2 migration already does.

**Per-document engine (folio-enrich)**

- R6. The engine tags each proposition with every FOLIO concept that applies, drawing on the concept annotations inside its span and adding judged tags such as Deontic Specification and Area of Law.
- R7. No model writes an IRI. Labels resolve to IRIs only through the deterministic resolver.
- R8. The engine rejects a proposition whose quote fails the anchor check, rather than emitting it.
- R9. Each candidate extraction strategy (current lexicon-and-dependency, the folio-insights LLM extractor, and a hybrid of the two) is scored against the gold sets, and the engine ships the best scorer.
- R10. Without a user API key the engine still runs and emits propositions with span-derived tags only. Judged tags appear only when the user supplies a key.

**Engine reuse (folio-enrich packaging)**

- R11. folio-insights can install a pinned engine release and run the full per-document pipeline in-process, without a running folio-enrich server and without importing folio-enrich source from a sibling checkout.
- R12. The engine's per-document output is identical whether folio-enrich or folio-insights invoked it, given the same document, engine version, and settings.
- R13. Corpus runs through the engine honor a spend cap, checkpoint after each document so a failed run resumes, and skip documents whose content hash already has a result for the current engine version.

**folio-enrich product surface**

- R14. The proposition workspace shows each proposition's span, verified quote, FOLIO tags grouped by branch, the authorities and entities it cites, and its linked triples. This same per-document view is the one folio-insights adopts.
- R15. A reviewer can accept, edit, or remove a proposition's tags and add a missed tag in the workspace, and those edits persist and survive re-processing of the same document.
- R16. Every export format includes propositions with their spans, quotes, and tags, matching how exports already carry individuals, properties, and triples.

### Acceptance Examples

- AE1. **Covers R1, R8.**
  - **Given:** a model paraphrases a holding and supplies a quote that does not appear in the source.
  - **When:** the engine runs the anchor check.
  - **Then:** the proposition is rejected and never reaches the workspace or an export.
- AE2. **Covers R6, R10.**
  - **Given:** the data-breach statute from the folio-insights README, run once with no key and once with a key.
  - **When:** the proposition "A business that discovers a data breach must notify each affected resident within 45 days" is emitted.
  - **Then:** without a key it carries span-derived tags such as Data Breach and Notice; with a key it also carries Obligation and Privacy Law.
- AE3. **Covers R12, R13.**
  - **Given:** a 200-document corpus run in folio-insights that fails at document 120, with one document already processed by folio-enrich at the same engine version.
  - **When:** the run resumes.
  - **Then:** it continues with the unprocessed documents and reuses the cached result for the already-processed document, and that document's propositions match folio-enrich's output exactly.
- AE4. **Covers R15.**
  - **Given:** a reviewer removed the Notice tag and added Obligation on a proposition, then the same document is submitted again after an engine upgrade.
  - **When:** the new run completes.
  - **Then:** the proposition shows Obligation and not Notice; an edit whose proposition no longer exists is listed as orphaned instead of silently dropped.

### Success Criteria

- The shipped extraction strategy's precision and recall on the gold sets are published with the release. If they fall short of the folio-insights publishing bar (RUB-EXTRACT ≥ 0.80), the README and UI label the output unvalidated, as folio-insights already labels its own.
- A planner for the folio-insights follow-on can retire `KnowledgeUnit` and its extractor, and reduce `bridge_ingest` to accepting the unified record without translation, using only this plan's record and engine contract, without inventing fields.

---

<!-- ce-section: work-relationships -->
## How This Work Fits Together

This plan covers the shared record, the engine, and its folio-enrich surface. The breakdown below is the current understanding, not a committed roadmap.

**Repository roles going forward:**

- **folio-propositions:** the shared vocabulary. It holds the proposition record, the interchange format, and schema migrations, and nothing else. It stays light so both products can pin it.
- **folio-enrich:** the per-document engine and its webapp. It extracts, verifies, tags, reviews, and exports propositions, alongside its existing concepts, individuals, properties, and triples.
- **folio-insights:** the corpus and governance product. It runs the engine on every document, then merges propositions across sources, flags contradictions, groups by task, mints signed shards, runs governance and review lifecycles, and keeps the SHACL-checked store.

**Later and parallel areas:**

- **folio-insights consumption follow-on** (a separate plan in folio-insights). Depends on R1–R5 and R11–R13. It retires `KnowledgeUnit`, the insights extractor, the translation inside `bridge_ingest` (which keeps receiving folio-enrich's push), the `IngestionBridge` sibling checkout (`folio_enrich_path`), and the sibling-checkout install; migrates stored shards to the unified record; adopts the R14 per-document view; adds spaCy to insights' worker image; and passes its metered LLM port into the engine.
- **In-flight folio-insights work.** Most can proceed independently of this plan:
  - **Can proceed independently of this plan:** Phase 13 storage, the U17 envelope and R18 disposition (already in folio-propositions), Phase 11 SHACL hybrid, governance, the shard minter and kernel, Phase 9 design principles, U6 polysemy, and retiring the last sibling bridges.
  - **Shares with this plan, so realign before new build:** Phase 10 pipeline re-plan (`docs/plans/2026-10-05-0308-feat-phase10-pipeline-replan-plan.md` in folio-insights). Its provider port, durable jobs, and spend reporting stay; new extraction logic waits for R9's result and lands in the engine.
  - **Shares with this plan, so realign before new build:** Review UI re-scope (`docs/plans/2026-10-20-1830-feat-review-ui-rescope-plan.md` in folio-insights). The shard page, supersession, governance wizards, and approval queue stay in insights; its span-anchored annotator is the R14/R15 per-document view, built once.
- **Corpus context feeding per-document tagging.** Still to decide.
- **Engine as a network service** for hosted setups. Still to decide.

---

### Scope Boundaries

- **Deferred for later:**
  - **Corpus context:** using a whole corpus to sharpen a single document's tags.
  - **Network service:** running the engine as a service that folio-insights calls.
  - **Viewer redesign:** redesigning the folio-insights viewer beyond retiring its per-document steps.
- **Outside this plan:**
  - **Insights code changes:** any change inside folio-insights, covered by the follow-on plan.
  - **Shard migration:** migrating existing insights shards, which also belongs to the follow-on.
  - **Cross-document features:** contradictions, task grouping, and minting.
- **Considered and not built:**
  - **PyPI publication** of the engine or folio-propositions. Both consumers already pin git tags with direct references; publishing becomes worth it when an outside consumer appears.
  - **A spend cap inside the folio-enrich webapp.** Its runs are single-document and use the user's own key; the cap lives with corpus runs (KTD9). Evidence that would change this: a hosted multi-document mode in the webapp.
  - **Live SSE updates for every tag change.** The workspace refetches once a job completes (U5); per-edit streaming adds no value for a single reviewer.
  - **A retention exemption for reviewed jobs.** Review edits live outside job files (KTD5), so the 30-day cleanup cannot destroy them.
  - **Reading a schema-5 job with an older engine.** Downgrades stay unsupported, as today; a rollback documents the one-way door instead.

### Deferred to Follow-Up Work

- The folio-insights consumption plan described in How This Work Fits Together.
- Damien's human validation of the AI-annotated Palsgraf gold set, through the DEV validation session; U9 scores against the validated record once it exists, and reports against AI-made gold until then.

### Dependencies / Assumptions

- folio-enrich and folio-insights both pin folio-propositions `v0.4.0` (schema 4); folio-propositions `main` sits at v0.4.0. The unified record ships as v0.5.0 (schema 5).
- folio-enrich already stamps `content_iri` on every proposition (`backend/app/services/proposition/source.py`), exports a `PropositionDocumentRecord` through the `propositions` and `propositions-ndjson` formats (`backend/app/services/export/propositions_exporter.py`), and pushes records to folio-insights after a job when configured (`backend/app/services/insights_client.py`, Damien's 2026-10-09 decision). This plan keeps that push; its payload simply becomes schema 5.
- The Palsgraf gold set (104 annotation rows) and its public-domain source text are committed under `backend/eval/gold/propositions/`. A human-validation session for it is live on DEV with 104 unreviewed items (`docs/plans/2026-10-03-2355-feat-gold-human-validation-plan.md`); `docs/plans/2026-10-26-0725-feat-fast-gold-annotation-plan.md` speeds that review.
- `backend/eval/proposition_benchmark.py` already scores extraction offline (greedy Dice ≥ 0.5 with Wilson intervals); CI runs the backend suite on pull requests (`.github/workflows/tests.yml`).
- The folio-insights README's eight synthetic examples are invented text with expected propositions, so they may be committed as a second gold set.

### Sources / Research

- **Insights model:** `src/folio_insights/models/knowledge_unit.py` in folio-insights defines `KnowledgeUnit`, `Span`, and `ConceptTag`.
- **Shared record:** `src/folio_propositions/models.py`, `interchange.py`, and `identity.py` in folio-propositions define `Proposition`, `PropositionDocumentRecord`, the single-step migration registry, and `content_iri`.
- **Enrich extractor:** `backend/app/services/proposition/extractor.py`, `identity.py`, and `backend/app/pipeline/stages/proposition_stage.py`.
- **Exports:** among the export modules in `backend/app/services/export/`, only `brat_exporter.py` emits propositions today; `backend/tests/test_proposition_byte_neutral.py` pins flag-off output.
- **Bridge:** `src/folio_insights/bridge_ingest/` and `src/folio_insights/services/bridge/ingestion_bridge.py` in folio-insights are the coupling this plan makes retirable.
- **Prior plan:** `docs/plans/2026-08-16-2234-feat-proposition-system-phase-a-plan.md` holds the August boundary and the proposition-system phases.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Record shape for v0.5.0 / schema 5.** `text` stays the verbatim span slice, so `content_iri` keeps its meaning. New fields:
  - **`statement`:** optional normalized wording, display-only, never used for anchoring or identity.
  - **Anchor:** `anchor_verified` and `anchor_score`, where `None` means "not checked" (all migrated records).
  - **`folio_tags`:** a flat list of tags carrying `iri` (nullable), `label`, `branch`, `confidence`, `path` (span, judged, reviewer), `evidence_text`, optional `source_annotation_id`, and `status` (`resolved`, `proposed`).
  - **`lineage`:** one event shape adopted from folio-insights' `StageEvent` (timestamp defaulted, paired template fields) plus an optional `actor`.
  - **`engine`:** per-proposition name and version; the record-level `generator` carries the same.
  - Pydantic's default extra-ignore stays, so older readers drop the new fields rather than fail. Governs R1–R5.
- KTD2. **Content-derived identity.** A document's `source_uri` is `document_source_uri(canonical_text)`. A proposition's `id` is a uuid5 over `(source_uri, start, end, proposition_type)`, replacing today's job-scoped id; `content_iri` (already stamped on `main`) stays text-based for shard identity. Existing gold sessions, which key candidates on the old id, keep their stored ids; new sessions use the new ones. Two typed propositions on one span, or repeated text in one document, therefore get distinct ids. Annotation and individual ids stay uuid4 and never enter proposition output except as `source_annotation_id` evidence. Governs R12, R15.
- KTD3. **Strict anchoring inside extraction.** Every strategy proposes a quote; the engine locates it in the canonical text with exact matching after whitespace normalization, sets the span from the match, and drops the candidate before it is stored or streamed when no match exists. Fuzzy matches are not accepted, because a 0.85 partial ratio still admits paraphrase. A substance gate skips headings, tables of contents, and attribution lines before any LLM extraction runs, since anchoring cannot catch fabrication from a heading (folio-insights `docs/solutions/heading-as-unit-fabrication.md`). Rejections are counted in job metadata. Governs R1, R8.
- KTD4. **A post-parallel tagging stage.** `PropositionTaggingStage` runs after `TripleEnrichmentStage` and before metadata, because concept annotations, individuals, properties, and triples must exist first.
  - **Span tags:** from non-rejected annotation concepts, individual class links, and properties whose spans fall inside the proposition span; each keeps its evidence text and source annotation id.
  - **Triple links:** `triple_ids` filled from triples inside the span.
  - **Judged tags:** Deontic Specification from the closed set of that subtree's children, and Area of Law from that branch's labels, both chosen by an LLM judge and resolved only through `ConceptResolver`; out-of-set labels are dropped.
  - **Failures:** a judge error marks the proposition degraded and keeps its span tags.
  - **Keyless:** with no provider the stage runs span tags only and makes no network call. Judge calls run under a concurrency limit.
  - Governs R6, R7, R10.
- KTD5. **A review overlay outside the job file.** Reviewer edits live in a review store keyed by `(source_uri, proposition id, tag key)`, separate from job JSON and from the 30-day job cleanup. The store applies on every read and export, and re-applies after any re-run; edits whose proposition vanished surface as orphaned. Edit routes refuse writes until the job is completed, require a revision token, and serialize per job. The job (plus overlay) owns tags; gold sessions stay a separate gold-set tool. Governs R15.
- KTD6. **Byte-neutral exports.** The two shared-schema formats (`propositions`, `propositions-ndjson`) move to schema 5 unchanged in shape. Every other exporter emits a propositions section only when `job.result.propositions` is non-empty, following the brat precedent, so flag-off output stays byte-identical. Exports read propositions with the overlay applied, omit removed tags, write proposed tags with an empty IRI in tabular formats, and never emit an RDF or Neo4j node for a proposed tag. Governs R16.
- KTD7. **Benchmark design.** Keep `backend/eval/proposition_benchmark.py`'s rule: greedy one-to-one matching at Dice ≥ 0.5, with Wilson intervals; scores are precision, recall, and F1 per gold set and per source type. Gold sets: Palsgraf (already committed, scored against the human-validated record once it exists) and the eight README synthetic examples, plus heading and attribution adversarial lines. The zero-LLM tier runs free in CI; LLM and hybrid tiers run with pinned model and temperature, only after a spend estimate is approved. Governs R9.
- KTD8. **Engine packaging.** The top-level package `app` becomes `folio_enrich`, with the web tier at `folio_enrich.web` behind a `[web]` extra; the engine core declares every runtime dependency it imports, including a pinned `en_core_web_sm` wheel. The repo keeps a `backend/app/main.py` shim outside the wheel so `uvicorn app.main:app` still starts DEV and PROD. The engine supports Python 3.11–3.13. Releases use `engine-vX.Y.Z` tags, which do not match the `v*` trigger of the desktop build, and consumers pin `git+…@engine-vX.Y.Z#subdirectory=backend`. Governs R11.
- KTD9. **Engine API and corpus runs.** The engine exposes a document entry point and a corpus entry point, both taking an explicit settings snapshot and injected LLM providers instead of reading the module-global settings.
  - **Cache key:** canonical-text hash, engine version, and a settings fingerprint covering the FOLIO ontology hash, spaCy model version, LLM model ids or "keyless", and label-set version.
  - **Checkpoints:** written only for fully processed documents; resume works by the set of finished hashes, not position.
  - **Budget:** a provider that raises budget exhaustion stops the corpus cleanly, leaves the current document unprocessed, and never falls back to keyless.
  - **Failures:** a failed document is recorded and the run continues, ending with a non-zero summary.
  - **Startup check:** the engine verifies FOLIO labels, the resolver, and the spaCy model at startup and fails loudly, carrying folio-insights' bridge-staleness lesson (`docs/solutions/sys-path-bridge-staleness.md` there).
  - Governs R11, R12, R13.
- KTD10. **Engine version.** The engine version is the distribution version plus a short hash of prompts, lexicons, and label sets, so a prompt edit invalidates caches without a manual bump. Governs R4, R13.

### High-Level Technical Design

Package and data relationships after this plan:

```mermaid
flowchart TB
  P["folio-propositions v0.5.0<br/>record, migrations, identity"]
  E["folio_enrich engine<br/>extract, anchor, tag, record"]
  W["folio_enrich.web<br/>API, SSE, review overlay routes"]
  F["frontend/index.html<br/>proposition workspace"]
  I["folio-insights<br/>corpus, shards, governance"]
  P --> E
  E --> W
  W --> F
  E -->|pinned engine tag, in-process| I
  P -->|pinned tag| I
```

Proposition lifecycle within one document run and its re-runs:

```mermaid
stateDiagram-v2
  [*] --> Candidate: strategy proposes quote
  Candidate --> Dropped: substance gate or no exact match
  Candidate --> Anchored: exact match sets span
  Anchored --> Tagged: span tags, triple links
  Tagged --> Judged: keyed run, judge succeeds
  Tagged --> Degraded: judge error
  Tagged --> Ready: keyless run
  Judged --> Ready
  Degraded --> Ready
  Ready --> Reviewed: overlay applied on read
  Reviewed --> Exported
  Ready --> Exported
  Reviewed --> Ready: re-run re-applies overlay, orphans listed
  Dropped --> [*]
```

Corpus run flow (KTD9):

```mermaid
flowchart TB
  S[Startup check] -->|fails| X[Stop loudly]
  S --> L[Next unfinished document]
  L --> K{Cache hit for key?}
  K -->|yes| R[Reuse result]
  K -->|no| D[Run document]
  D -->|budget exhausted| B[Stop, document not checkpointed]
  D -->|error| Q[Record failure, continue]
  D --> C[Checkpoint document]
  R --> L
  C --> L
  Q --> L
  L -->|none left| Z[Summary, non-zero if any failed]
```

Run modes:

| Mode | Extraction | Span tags | Judged tags | Network |
|---|---|---|---|---|
| Flag off | none | none | none | unchanged from today |
| Flag on, keyless | zero-LLM strategy | yes | no | none for propositions |
| Flag on, keyed | shipped strategy (U9) | yes | yes, or degraded | user's provider |
| Corpus, keyed, budget hit | stops at boundary | n/a | n/a | stops; never falls back to keyless |

### Assumptions

- Enrich's code uses no syntax newer than Python 3.11; U10 verifies this with a 3.11 test run.
- A uuid5 proposition id change is acceptable for existing jobs; migrated jobs keep their stored ids, and only new runs use KTD2 ids.

### Risks

| Risk | Mitigation |
|---|---|
| The package rename breaks DEV or PROD deploys | Repo shim keeps `uvicorn app.main:app`; U10 smoke-starts the server from the shim and from both Dockerfiles |
| FOLIO snapshot drift makes enrich and insights tag differently | Ontology hash enters the settings fingerprint (KTD9) and the record generator, so drift shows as a cache miss and a visible version difference |
| Benchmark overfits one opinion | Second gold set from the README's eight source types (KTD7) |
| Stricter verification raises the share of proposed tags that downstream consumers miscount | Explicit `proposed` status (KTD1); the engine contract tells consumers to exclude proposed tags from votes |
| Schema 5 jobs are unreadable after a rollback | Documented one-way door in the release notes; `JobStore.list_jobs` logs skipped ids instead of hiding them |

---

## Implementation Units

| U-ID | Title | Key files | Depends on |
|---|---|---|---|
| U1 | Unified record v0.5.0 | folio-propositions `src/folio_propositions/models.py`, `interchange.py` | — |
| U2 | Adopt schema 5 and content identity | `backend/app/models/job.py`, `backend/app/services/proposition/identity.py`, `backend/app/services/proposition/source.py` | U1 |
| U3 | Anchored extraction | `backend/app/services/proposition/`, `backend/app/pipeline/stages/proposition_stage.py` | U2 |
| U4 | Proposition tagging stage | `backend/app/pipeline/stages/proposition_tagging_stage.py`, `backend/app/pipeline/orchestrator.py` | U2 |
| U5 | Review overlay and edit routes | `backend/app/storage/review_store.py`, `backend/app/api/routes/propositions.py` | U4 |
| U6 | Workspace tags and citations | `frontend/index.html` | U5 |
| U7 | Propositions in all exports | `backend/app/services/export/*` | U5 |
| U8 | Benchmark gold sets | `backend/eval/proposition_benchmark.py`, `backend/eval/gold/propositions/` | U2 |
| U9 | Extractor bake-off | `backend/app/services/proposition/strategies/`, `backend/eval/proposition_benchmark.py` | U3, U8 |
| U10 | Engine package split | `backend/pyproject.toml`, `backend/folio_enrich/`, `backend/app/main.py` | U3–U9 |
| U11 | Engine API, corpus runs, contract | `backend/folio_enrich/engine.py`, `.github/workflows/engine-smoke.yml`, `docs/engine-contract.md` | U10 |

### U1. Unified record v0.5.0

- **Goal:** folio-propositions v0.5.0 carries the unified record with a lossless v4→v5 migration.
- **Requirements:** R1–R5; KTD1, KTD2.
- **Dependencies:** none.
- **Target repo:** folio-propositions.
- **Files:** `src/folio_propositions/models.py`, `src/folio_propositions/interchange.py`, `src/folio_propositions/identity.py`, `src/folio_propositions/__init__.py`, `pyproject.toml`, `docs/migration-0.5.0.md`, `docs/README.md`, `tests/test_models.py`, `tests/test_interchange.py`, `tests/test_identity.py`.
- **Approach:**
  1. Add the KTD1 tag, lineage, anchor, statement, and engine fields with defaults that keep v4 payloads valid.
  2. Add a proposition-id helper implementing KTD2 next to `content_iri`.
  3. Register a single-step `_migrate_v4_to_v5` following `_migrate_v3_to_v4`: empty tags and lineage, anchor `None`, no engine.
  4. Bump `SCHEMA_VERSION` to 5 and `__version__` to 0.5.0; write the migration doc; tag `v0.5.0` after merge.
- **Patterns to follow:** `_migrate_v3_to_v4` and its tests; the v0.4.0 release doc and annotated tag.
- **Test scenarios:**
  - A v4 record with two propositions migrates to v5 with empty `folio_tags`, empty `lineage`, and `anchor_verified` `None`.
  - A v3 Palsgraf gold proposition dict migrates through v4 to v5 unchanged in every existing field.
  - A tag with `status` `proposed` and `iri` `None` validates; a `resolved` tag with no IRI is rejected.
  - The proposition-id helper returns different ids for two types on one span, and for the same text at two offsets.
  - A v5 payload loaded by v0.4.0 models drops the new fields without raising (extra-ignore).
  - `migrate_record` refuses a v6 payload.
- **Verification:** the folio-propositions suite, ruff, and mypy pass on 3.11–3.13 in its CI; the `v0.5.0` tag exists.

### U2. Adopt schema 5 and content identity

- **Goal:** folio-enrich pins v0.5.0, builds content-derived ids, and stamps engine version on every proposition and record.
- **Requirements:** R4, R5, R12; KTD2, KTD10.
- **Dependencies:** U1.
- **Files:** `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/models/job.py`, `backend/app/services/proposition/identity.py`, `backend/app/services/proposition/source.py`, `backend/app/services/proposition/extractor.py`, `backend/app/services/export/propositions_exporter.py`, `backend/app/services/insights_client.py`, `backend/app/engine_version.py` (new), `backend/app/storage/job_store.py`, `backend/app/services/gold/store.py`, `backend/tests/test_proposition_identity.py` (new), `backend/tests/test_proposition_stage.py`, `backend/tests/test_gold_store.py`.
- **Approach:**
  1. Move the pin from `v0.4.0` to `v0.5.0`; existing `migrate_record` loading carries v3 and v4 jobs and gold rows to v5.
  2. Replace the job-scoped id with the KTD2 helper for new runs, defaulting `source_uri` to the canonical-text URI when the caller supplies none; leave stored gold-session ids untouched.
  3. Compute the KTD10 engine version once per process and stamp it on each proposition and on the record generator the `propositions` exporter and the insights push already build.
  4. Make `list_jobs` log job ids it skips because of a schema error.
- **Patterns to follow:** the `migrate_persisted_propositions` validator in `backend/app/models/job.py`; `stamp_content_iris` in folio-propositions.
- **Test scenarios:**
  - The same document text run as two jobs yields identical proposition ids.
  - A stored schema-4 job file loads with propositions at schema 5 and `anchor_verified` `None`.
  - An existing gold session still resolves every candidate by its stored id after the upgrade.
  - The `propositions` export and the insights push payload validate as schema-5 `PropositionDocumentRecord`s, including the `content_iri` check.
  - Editing a lexicon entry changes the engine version; an unrelated code change does not.
  - A job file with a newer schema is skipped by `list_jobs` and logged.
- **Verification:** the backend suite passes, including the byte-neutral test with no baseline change.

### U3. Anchored extraction

- **Goal:** every emitted proposition carries a verified verbatim quote, and unanchored candidates never reach storage or SSE.
- **Requirements:** R1, R8; KTD3. Covers AE1.
- **Dependencies:** U2.
- **Files:** `backend/app/services/proposition/anchoring.py` (new), `backend/app/services/proposition/substance.py` (new), `backend/app/services/proposition/extractor.py`, `backend/app/pipeline/stages/proposition_stage.py`, `backend/app/services/llm/prompts/templates.py`, `backend/tests/test_proposition_anchoring.py` (new), `backend/tests/test_proposition_stage.py`.
- **Approach:**
  1. Add an exact, whitespace-normalized locator over canonical text that returns the span or no match; port only the exact path of folio-insights' `resolve_anchor`.
  2. Change the LLM assist prompt to return quotes instead of offsets, and route its candidates through the locator.
  3. Run lexicon candidates through the locator too, so every proposition carries an anchor result.
  4. Add the substance gate before LLM extraction; count gated and rejected candidates in job metadata.
  5. Expose the locator for hand-added propositions in U5.
- **Patterns to follow:** `EarlyPropositionStage._assist` validation and merge; `_build` slicing text from offsets.
- **Test scenarios:**
  - Covers AE1. An LLM candidate whose quote is absent from the text is dropped, never stored, and counted as rejected.
  - A quote differing only in line breaks and double spaces anchors to the right span.
  - A quote that occurs twice anchors to the occurrence in the sentence the strategy named, else the first.
  - A heading line such as "II. DISCUSSION" never reaches the LLM and is counted as gated.
  - Lexicon output gets `anchor_verified` true and `anchor_score` 1.0.
  - An SSE stream for a job with a rejected candidate emits no `proposition_added` for it.
- **Verification:** the proposition tests pass; the byte-neutral test still passes with the flag off.

### U4. Proposition tagging stage

- **Goal:** each proposition carries flat FOLIO tags from its span plus judged Deontic and Area of Law tags when keyed.
- **Requirements:** R2, R6, R7, R10, R14 (data); KTD4. Covers AE2.
- **Dependencies:** U2.
- **Files:** `backend/app/pipeline/stages/proposition_tagging_stage.py` (new), `backend/app/services/proposition/tagging.py` (new), `backend/app/services/proposition/judge.py` (new), `backend/app/pipeline/orchestrator.py`, `backend/app/services/llm/prompts/templates.py`, `backend/tests/test_proposition_tagging.py` (new).
- **Approach:**
  1. Build span tags from non-rejected annotation concepts, individual class links, and properties contained in the proposition span; map `ConceptMatch.branches[0]` to the flat branch.
  2. Fill `triple_ids` from triples inside the span.
  3. Build the closed Deontic and Area of Law label sets from the loaded FOLIO ontology; the judge picks labels from them, and `ConceptResolver` resolves each to an IRI or the tag becomes `proposed`.
  4. Add the stage to both `build_stages` and `build_pipeline_config`, after `TripleEnrichmentStage`; judged tagging runs only when a proposition provider resolves.
  5. Bound judge calls with a semaphore; record degraded propositions and rejected labels in metadata.
- **Patterns to follow:** `BranchJudgeStage` and its conditional inclusion; `ConceptResolver.resolve`; the per-task LLM wiring for `"proposition"` in `TaskLLMs`.
- **Test scenarios:**
  - Covers AE2. Keyless run on the synthetic data-breach statute: the proposition carries Data Breach and Notice with `path` span and no Obligation.
  - Covers AE2. Keyed run with a stub judge returning "Obligation" and "Privacy Law": both tags resolve to their IRIs with `path` judged.
  - A judge returning "Very Obligatory" (out of set) produces no tag and increments the rejected-label count.
  - A judge timeout leaves span tags intact and marks the proposition degraded.
  - A rejected annotation inside the span contributes no tag.
  - A triple inside the span appears in `triple_ids`; one outside does not.
  - A keyless run performs no LLM call (the stub provider records zero calls).
  - A tag whose label the resolver cannot map is stored as `proposed` with no IRI.
- **Verification:** tagging tests pass; a flag-off pipeline run still matches the byte-neutral baseline.

### U5. Review overlay and edit routes

- **Goal:** reviewer tag edits and proposition adds and deletes persist outside the job, apply on every read, and survive re-runs.
- **Requirements:** R15; KTD5. Covers AE4.
- **Dependencies:** U4.
- **Files:** `backend/app/storage/review_store.py` (new), `backend/app/services/proposition/overlay.py` (new), `backend/app/api/routes/propositions.py` (new), `backend/app/main.py`, `backend/app/services/streaming/sse.py`, `backend/tests/test_review_overlay.py` (new), `backend/tests/test_proposition_routes.py` (new).
- **Approach:**
  1. Add a filesystem review store with atomic writes under the jobs root but outside job files and cleanup, keyed per KTD5.
  2. Add routes to read propositions with the overlay applied, edit tags (accept, remove, add), delete a proposition, and hand-add one anchored through the U3 locator.
  3. Gate writes on completed jobs, require the revision token the read returns, and serialize writes per job; each edit appends a lineage event with `actor` user.
  4. Re-apply the overlay after any run on a document with existing edits; list orphans in the read response.
  5. Add the proposition count to the SSE `complete` event.
- **Patterns to follow:** the promote, reject, and restore routes in `backend/app/api/routes/enrich.py`; `JobStore` atomic writes.
- **Test scenarios:**
  - Covers AE4. Remove Notice, add Obligation, re-run the same text: the read shows Obligation and not Notice.
  - Covers AE4. An edit for a proposition absent from the new run appears in the orphan list.
  - An edit sent while the job is running returns 409 and changes nothing.
  - Two edits with the same revision token: the first succeeds, the second returns 409.
  - A hand-added proposition whose quote is absent from the text is refused.
  - Overlay data survives `cleanup_expired` deleting the job file.
  - The SSE `complete` event reports the proposition count.
- **Verification:** route and overlay tests pass; existing annotation route tests pass unchanged.

### U6. Workspace tags and citations

- **Goal:** the proposition workspace shows R14's per-document view and lets a reviewer edit tags through U5.
- **Requirements:** R14, R15.
- **Dependencies:** U5.
- **Files:** `frontend/index.html`.
- **Approach:**
  1. In `renderPropositionCard`, show the verified quote (or "quote not checked" for migrated jobs), the display statement when present, tags grouped by branch with proposed tags visibly distinct, cited authorities and entities, and linked triples.
  2. Add accept, remove, and add-tag controls that call the U5 routes with the revision token, handle 409 with a refresh prompt, and show orphaned edits.
  3. Refetch propositions on the SSE `complete` event.
  4. Keep gold-session controls only in annotation mode.
- **Patterns to follow:** the existing proposition review workspace CSS and JS blocks; branch colors and pills from the multi-branch span tooltip.
- **Test expectation:** UI behavior verified in a real browser (Playwright, per the repo's browser-testing rule): a keyed demo job renders grouped tags, a tag removal persists across reload, and a 409 shows the refresh prompt. Screenshots inspected and deleted.
- **Verification:** the browser checks above pass on desktop and phone widths, with keyboard-reachable controls and visible focus.

### U7. Propositions in all exports

- **Goal:** every exporter includes propositions with spans, quotes, and tags when a job has them, and stays byte-identical when it does not.
- **Requirements:** R16; KTD6.
- **Dependencies:** U5.
- **Files:** `backend/app/services/export/json_exporter.py`, `jsonld_exporter.py`, `xml_exporter.py`, `csv_exporter.py`, `jsonl_exporter.py`, `parquet_exporter.py`, `elasticsearch_exporter.py`, `neo4j_exporter.py`, `rag_exporter.py`, `rdf_exporter.py`, `brat_exporter.py`, `html_exporter.py`, `excel_exporter.py`, `propositions_exporter.py`, `backend/app/api/routes/export.py`, `backend/tests/test_proposition_exports.py` (new), `backend/tests/fixtures/proposition_exports/` (new).
- **Approach:**
  1. Have the export route pass propositions with the overlay applied.
  2. Add a guarded propositions section to each exporter, mirroring its triples section.
  3. Apply KTD6's rules for removed and proposed tags in every format.
- **Patterns to follow:** each exporter's `if job.result.triples:` section; brat's propositions-only-when-present rule.
- **Test scenarios:**
  - A flag-off job exports byte-identically to the existing baseline in every pinned format.
  - A job with one resolved and one proposed tag exports both in JSON and CSV, the proposed one with an empty IRI.
  - RDF and Neo4j exports contain no node for the proposed tag.
  - A tag removed through the overlay appears in no export.
  - Golden fixtures per format match for a two-proposition job.
- **Verification:** export tests and the byte-neutral test pass.

### U8. Benchmark gold sets

- **Goal:** the existing deterministic benchmark measures any extraction strategy against Palsgraf and a new README synthetic set.
- **Requirements:** R9; KTD7.
- **Dependencies:** U2.
- **Files:** `backend/eval/proposition_benchmark.py`, `backend/eval/gold/propositions/readme-synthetic.jsonl` (new), `backend/eval/gold/propositions/readme-synthetic/` (new source texts), `backend/eval/gold/propositions/manifest.json`, `backend/eval/gold/propositions/README.md`, `backend/tests/test_proposition_benchmark.py`.
- **Approach:**
  1. Encode the README's eight synthetic excerpts and their expected propositions as a gold record, plus heading and attribution adversarial lines marked as must-not-extract.
  2. Extend the benchmark to score any strategy (not only the lexicon), report per gold set and per source type, and prefer a `-validated` record over its AI original when both exist.
- **Patterns to follow:** the existing benchmark's matching and report layout; the `eval` marker and long timeout from `docs/solutions/2026-07-07-ner-eval-gold-set-harness.md`.
- **Test scenarios:**
  - Every synthetic gold span slices its committed text to its stored `text`.
  - A stub strategy returning fixed spans is scored with the same Dice rule as the lexicon.
  - An extracted adversarial heading counts as a false positive.
  - With both `palsgraf-248-ny-339` and `palsgraf-248-ny-339-validated` present, the benchmark scores the validated one.
- **Verification:** scorer tests pass in the default suite; the deterministic scoring run executes under the `eval` marker.

### U9. Extractor bake-off

- **Goal:** the engine ships the best-scoring extraction strategy, chosen by measurement.
- **Requirements:** R9, Success Criteria; KTD3, KTD7.
- **Dependencies:** U3, U8.
- **Files:** `backend/app/services/proposition/strategies/__init__.py` (new), `strategies/lexicon.py` (new, wraps today's `phase-b-v1` extractor), `strategies/llm.py` (new, ports folio-insights' boundary and distill prompts), `strategies/hybrid.py` (new), `backend/eval/proposition_benchmark.py`, `backend/eval/estimate_spend.py`, `backend/eval/reports/` (new report), `backend/app/config.py`, `backend/tests/test_proposition_strategies.py` (new).
- **Approach:**
  1. Put the three strategies behind one interface; all three propose quotes and pass through U3 anchoring.
  2. Port folio-insights' LLM extraction prompts, keeping its distilled wording only as `statement`.
  3. Score the lexicon strategy for free; estimate the LLM and hybrid runs and file the estimate as a spend decision for Damien before running them.
  4. After approval, run with pinned model and temperature, write the report, and set the default strategy config to the winner, keeping lexicon as the keyless strategy.
  5. Record the scores and the unvalidated label decision against the RUB-EXTRACT bar in the report and README.
- **Execution note:** steps 3–4 pause on the spend approval; everything before them proceeds.
- **Patterns to follow:** `backend/eval/proposition_benchmark.py` and its `phase-b-v1` report; `PINNED_FLAGS` in `backend/eval/synthetic_runner.py`.
- **Test scenarios:**
  - Each strategy, given a stub LLM returning fixed quotes, yields anchored propositions only.
  - The hybrid strategy merges lexicon and LLM candidates without duplicate ids.
  - The runner refuses an LLM tier without an explicit approved-spend flag.
  - The keyless config always selects the lexicon strategy.
- **Verification:** strategy tests pass; the committed report lists precision, recall, and F1 for each strategy on both gold sets.

### U10. Engine package split

- **Goal:** folio-enrich installs as a namespaced engine with no web stack, while the webapp and deploys keep running.
- **Requirements:** R11; KTD8.
- **Dependencies:** U3–U9.
- **Files:** `backend/folio_enrich/` (renamed from `backend/app/`), `backend/folio_enrich/web/` (from `app/main.py`, `app/api/`, `app/middleware/`), `backend/app/main.py` (shim, outside the wheel), `backend/pyproject.toml`, `Dockerfile`, `backend/Dockerfile`, `.github/workflows/build.yml`, `backend/tests/` (import updates), `CLAUDE.md`.
- **Approach:**
  1. Rename the package and update every import mechanically; move the web tier under `folio_enrich.web`.
  2. Move API-key resolution out of `api/routes/settings.py` into the engine, so `_make_llm` no longer imports the web tier.
  3. Make checkout-relative paths (gold export directory, demo seeding) configurable, defaulting to today's locations in the web tier.
  4. Split dependencies into engine core (including the pinned spaCy model wheel) and a `[web]` extra; wheel packages only `folio_enrich`.
  5. Keep `uvicorn app.main:app` working through the shim; update both Dockerfiles and the PyInstaller hidden imports.
- **Execution note:** mostly packaging; prove it with install and start smoke checks rather than new unit tests.
- **Patterns to follow:** the lazy-import packaging lesson in cockpit `docs/solutions/2026-07-07-book-indexer-oss-extraction.md`.
- **Test scenarios:**
  - Importing the engine in an environment without fastapi succeeds.
  - The server starts through `app.main:app` and through `folio_enrich.web.main:app`, and `/health` answers.
  - The full backend suite passes on Python 3.11 and 3.13.
- **Verification:** the suite passes; both Dockerfiles build and serve `/health`; a fresh virtual environment installs the engine without `[web]`.

### U11. Engine API, corpus runs, and contract

- **Goal:** folio-insights can call one documented engine API for single documents and corpora, with caching, resume, budget stops, and a loud startup check.
- **Requirements:** R11, R12, R13; KTD9, KTD10. Covers AE3.
- **Dependencies:** U10.
- **Files:** `backend/folio_enrich/engine.py` (new), `backend/folio_enrich/corpus.py` (new), `backend/folio_enrich/canary.py` (new), `backend/tests/test_engine_api.py` (new), `backend/tests/test_corpus_runs.py` (new), `.github/workflows/engine-smoke.yml` (new), `docs/engine-contract.md` (new), `README.md`.
- **Approach:**
  1. Add the document entry point, which takes text or a file, a settings snapshot, and providers, and returns the `PropositionDocumentRecord` plus run metadata (degraded flags, rejection counts, engine version).
  2. Add the corpus entry point implementing KTD9's cache key, per-document checkpoints, hash-set resume, budget stop, and failure summary.
  3. Add the startup check and call it from both entry points.
  4. Add a CI workflow that installs the engine from a fresh environment on 3.11 and 3.12 and runs one synthetic document end to end.
  5. Write `docs/engine-contract.md` for the folio-insights follow-on: entry points, record fields, proposed-tag voting rule, cache and budget behavior, version and tag scheme.
  6. Tag `engine-v0.1.0` after merge.
- **Patterns to follow:** `PipelineOrchestrator(JobStore(base_dir=...))` with explicit `llm=` from the gold-set harness lesson; folio-insights' `CostMeter` budget exception as the provider contract.
- **Test scenarios:**
  - Covers AE3. A 5-document corpus whose provider fails on document 3 resumes and processes only documents 3–5.
  - Covers AE3. A document already processed at the same engine version and settings is reused from cache, and its record equals the document entry point's output byte for byte.
  - Changing the ontology hash, LLM model id, keyless flag, or engine version each produces a cache miss.
  - A budget exception mid-document stops the run, leaves that document without a checkpoint, and makes no keyless retry.
  - A corpus with one failing document finishes the rest and returns a non-zero summary.
  - A missing spaCy model makes the startup check raise before any document runs.
- **Verification:** engine tests pass; the smoke workflow passes on 3.11 and 3.12; the contract doc names every field a follow-on planner needs.

---

## Verification Contract

| Scope | Command or gate | Applies to |
|---|---|---|
| folio-propositions suite | `.venv/bin/pytest -q`, ruff, and mypy (its CI matrix on 3.11–3.13) | U1 |
| Backend suite | `cd backend && .venv/bin/python -m pytest tests/ -v`, also run on every PR by `.github/workflows/tests.yml` | U2–U11 |
| Flag-off byte neutrality | `backend/tests/test_proposition_byte_neutral.py` passes with no baseline regeneration | U2–U7, U10 |
| Deterministic eval tier | `cd backend && .venv/bin/python -m eval.proposition_benchmark` and `pytest -m eval` | U8, U9 |
| Python range | backend suite on 3.11 and 3.13 | U10, U11 |
| Fresh-install engine smoke | `.github/workflows/engine-smoke.yml` | U11 |
| Container start | both Dockerfiles build and answer `/health` | U10 |
| Browser check | Playwright screenshots of the workspace, inspected | U6 |
| Deploy check | DEV (`propositions-dev.damienriehl.com`) serves a keyed proposition job with tags after merge | after U7 and after U10 |

## Definition of Done

- **All units:**
  - **Tests:** each unit's test scenarios exist and pass, and its Verification Contract rows are green.
  - **Byte neutrality:** flag-off exports and SSE output still match the baseline.
  - **Cleanup:** no abandoned-attempt code, stray debug output, or committed non-public source text remains.
- **Releases:** folio-propositions `v0.5.0` and folio-enrich `engine-v0.1.0` tags exist, and folio-enrich pins `v0.5.0`.
- **Benchmark:** the U9 report is committed. The README states the measured precision and recall, labeled unvalidated if below the RUB-EXTRACT bar.
- **Handoff:** `docs/engine-contract.md` lets the folio-insights follow-on plan proceed without inventing fields, and a sanitized handoff in `docs/handoffs/` points to it.
- **Deploy:** DEV runs the new build. The release notes record the schema-downgrade one-way door.
