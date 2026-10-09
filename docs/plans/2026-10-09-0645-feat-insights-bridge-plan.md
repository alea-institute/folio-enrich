---
title: folio-enrich ↔ folio-insights bridge
date: 2026-10-09
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
repos:
  - folio-propositions (main)
  - folio-enrich (main)
  - folio-insights (master; bridge-ingest module and bridge retirement only)
  - folio-resolve (main; docs/migration/SCHEDULE.md only)
---

# folio-enrich ↔ folio-insights bridge

## Goal Capsule

- **Objective:** An enrich user reviewing one document's propositions can see, for each proposition, what the folio-insights corpus knows about it: its shard IRI, its epistemic status, and the shards that relate to or contest it. Enrich propositions reach insights as hypothesis shards under one identity that both products compute identically.
- **Means:** Bridge the two products through the shared folio-propositions vocabulary and two small HTTP/file seams. Do not merge or port insights code into enrich.
- **Product authority:** Damien settled "Bridge, not merge" on 2026-10-09 (cockpit ask `coding-projects-2026-10-09-1134-friday-quota-drain`). It reaffirms the 2026-08-16 rule in `docs/ideation/2026-08-16-axiom-proposition-extraction-ideation.html`: single-document work belongs in enrich, multi-document work in insights, shared vocabulary in folio-propositions. A parallel lane owns folio-insights shards, minting and governance; `src/folio_insights/shards/minting.py` is a frozen contract for this work.
- **Open blockers:** none.

## Product Contract

### Summary

folio-propositions v0.4.0 gains a content-addressed identity function that reproduces the insights shard-IRI recipe exactly, and a real, signed `axiom_status` lifecycle. Enrich stamps that identity on every proposition, keeps its legacy uuid5 ID, and exports propositions as a shared-schema interchange record. Insights ingests such a record as hypothesis shards and serves a read-only status API. Enrich's Propositions tab shows that corpus status beside each proposition.

### Problem Frame

Damien's original ask was to bring folio-insights' capabilities into folio-enrich. The two products cannot talk today. Enrich proposition IDs are `uuid5(folio-enrich:{job}:{start}:{end}:{type})`, so the same sentence gets a new ID in every job and can never be matched to a corpus record. Insights mints `urn:folio:shard/{sha256(nfc(source_uri) + "\n" + span)[:32]}`, but enrich jobs carry no source URI at all. The interchange record exists in folio-propositions and neither product emits or reads it. Insights still reaches into enrich's working tree through `sys.path` bridges, so a deployed insights image depends on a sibling checkout that its Dockerfiles do not provide.

### Key Decisions

- **Bridge, not merge.** (session-settled: user-directed — chosen over a full merge of insights into enrich and over a selective port: keeps the document/corpus rule and the two release trains.) Governs R1–R22.
- **The shared identity is the insights shard recipe, hosted in the library.** folio-propositions reproduces the recipe byte for byte; insights proves parity in a test instead of re-pointing `minting.py`, which the parallel lane owns. Governs R1, R2, R13.
- **Identity is per source span, not per type.** Two enrich propositions over the same span with different types share one content IRI, matching insights' one-shard-per-span granularity. Governs R2, R7, R12.
- **The legacy uuid5 stays the proposition `id`.** Gold sessions and annotations key on it; the content IRI is a new field, and enrich lookups accept either. Governs R6, R8.
- **A source URI defaults to a content hash of the canonical text.** A caller-supplied URI wins, so a document insights already holds under a URL matches. Governs R5.
- **Lifecycle signatures are verifiable without insights.** The library defines the canonical signing payload and a verifier interface, plus an optional did:key Ed25519 verifier. Governs R3, R4.
- **Post-job review and push are two independent, user-controlled choices.** (session-settled: user-directed — Damien, 2026-10-09, ask `folio-enrich-2026-10-09-1152-insights-bridge-auto-push`, chosen over pull-only, per-job opt-in only, and push-everything: each user decides whether to review and whether to push, with saved defaults and per-job overrides.) The pull path stays. Governs R9, R12, R23–R28.
- **The enrich backend proxies the insights read API.** The browser never calls insights directly, so there is no CORS or credential exposure, and an unconfigured enrich degrades to a "not connected" state. Governs R17–R19.

### Requirements

**Shared identity and lifecycle (folio-propositions)**

- R1. A public function returns the content IRI and full provenance hash for a `(source_uri, span)` pair, identical to `folio_insights.shards.minting.mint_shard_iri` for every input, including NFD/NFC, CRLF/LF and trailing-slash variants.
- R2. `Proposition` carries an optional `content_iri`, and `PropositionDocumentRecord` carries an optional `source_uri`; a record that has both a source URI and a span-bearing proposition validates that the stamped IRI matches the recomputed one.
- R3. `axiom_status` changes only through recorded transitions on the proposition (`axiom_history`), along an explicit legal-transition table whose action names match insights' `SignedAction` vocabulary where they overlap.
- R4. Every transition after migration carries a signature over a canonical payload that a supplied verifier can check; an illegal or unverifiable transition is refused with a specific error.
- R5. `SCHEMA_VERSION` becomes 4 with a registered 3→4 migration and a `docs/migration-0.4.0.md` note; v1–v3 records migrate forward losslessly, and `docs/shard-mapping.md` no longer marks the lifecycle design-only.
- R6. A tagged release `v0.4.0` exists, and both consumers pin it.

**Enrich stamps and exports (folio-enrich)**

- R7. Every proposition enrich extracts carries a `content_iri` computed through the library from the job's source URI and the proposition text.
- R8. Existing jobs keep their uuid5 IDs; loading a pre-change job yields the same IDs, and a proposition can be found by either its uuid5 or its content IRI.
- R9. A caller can supply a document's `source_uri` when submitting a job; otherwise enrich derives a deterministic URN from the canonical text, so the same document text yields the same IRIs in any job.
- R10. An export format emits a job's propositions as a schema-v4 `PropositionDocumentRecord`, and a streaming form emits one proposition per line; existing export formats stay byte-neutral.

**Insights ingests and serves (folio-insights)**

- R11. A new bridge-ingest module turns a `PropositionDocumentRecord` into `hypothesis` shards whose IRIs come from `mint_shard_iri`; a record whose stamped `content_iri` disagrees is refused, not silently re-minted.
- R12. Ingest is idempotent per shard IRI, keeps every proposition type observed on a span, and writes through the existing corpus storage gates (PII, SHACL).
- R13. A test proves library identity equals `mint_shard_iri` across a property-based corpus.
- R14. An end-to-end test drives one opinion through enrich's extractor, exports the record, ingests it into a temporary insights corpus, and finds the minted IRIs with a SPARQL query.
- R15. A read-only insights endpoint returns, for a batch of content IRIs, whether each is in the corpus and its shard type, epistemic status, contested flag, supersession links, related shards and contesting or conflicting shards.
- R16. Ingest is reachable from the insights CLI; an HTTP ingest route exists only when an operator token is configured.

**Enrich surfaces corpus status (folio-enrich UI)**

- R17. Enrich exposes a backend route that returns the insights status for a job's propositions, configured by `FOLIO_ENRICH_INSIGHTS_API_URL`.
- R18. The Propositions tab shows, per proposition, its content IRI and corpus status, with related and contesting shards on demand.
- R19. When insights is unconfigured or unreachable, the tab says so plainly and the rest of the review workflow is unaffected.

**Retire the sys.path bridges (folio-insights, folio-resolve)**

- R20. Each `sys.path` or file-path bridge in `src/folio_insights/services/bridge/` is either replaced by a packaged or vendored dependency with a parity test, or kept with a recorded reason.
- R21. A bridge is replaced only when its parity test passes; a failing parity check keeps the bridge.
- R22. `folio-resolve/docs/migration/SCHEDULE.md` records each bridge's new status.

**Post-job review and push (folio-enrich)**

- R23. After a job finishes, two independent choices apply: a review step ("review before continuing" or "skip review / auto-accept") and a push to insights ("push" or "don't push"); when review is on, the push waits until the review is completed.
- R24. Both choices default from the user's saved preferences, stored the way enrich already stores user and session settings.
- R25. A per-job override of both choices is offered at job submission and again when the job completes.
- R26. A push sends the job's shared-schema record to insights' ingest route; re-pushing the same job creates no duplicate shards because shard IRIs are content-addressed.
- R27. The UI shows each job's review status and push status (including push failures with a retry).
- R28. Tests cover all four review × push combinations, a preference default, and a per-job override.

### Key Flows

- F3. **Post-job flow (R23–R27).** Job completes → if review is on, the job waits in "awaiting review" until the user completes review → if push is on, enrich pushes the record to insights → the job shows review and push status.

- F1. **Export and ingest (R7, R9–R12, R16).** User runs an enrich job with proposition extraction on → downloads `?format=propositions` → operator runs `folio-insights bridge-ingest record.json --corpus <name>` → shards appear in the corpus.
- F2. **Corpus status in review (R15, R17–R19).** User opens the Propositions tab → enrich backend asks insights about the job's content IRIs → each card shows a corpus badge; expanding it lists related and contesting shards.

### Acceptance Examples

- AE1. Covers R1, R13. `content_iri("https://Example.com/a/", "x\r\ny ")` equals `mint_shard_iri("https://example.com/a", "x\ny")[0]`.
- AE2. Covers R3, R4. A `proposition → promoted` transition with a valid did:key signature applies; `superseded → promoted` raises an illegal-transition error; a tampered payload raises a signature error.
- AE3. Covers R8, R9. The same opinion text submitted in two jobs yields different uuid5 IDs and identical content IRIs.
- AE4. Covers R14. The SPARQL query `SELECT ?s WHERE { ?s <…/vocab/shardType> "hypothesis" }` over the ingested corpus returns exactly the record's distinct content IRIs.
- AE5. Covers R19. With `FOLIO_ENRICH_INSIGHTS_API_URL` unset, the tab shows "folio-insights not connected" and proposition review still saves outcomes.

### Scope Boundaries

- No merge or port of insights pipeline code into enrich.
- No change to `minting.py`, the envelope, SHACL shapes or governance events; those belong to the parallel lane.
- No scheduled sync or webhook beyond the post-job push in R23–R28.
- No authentication added to the insights API beyond the optional ingest token; insights API auth is an existing follow-up.
- No production deploy today.
- Insights shard promotion from these hypotheses runs through insights' own governance, not through enrich.

### Outstanding Questions

- Deferred to Planning: which bridges pass parity today; the plan records each outcome per R20–R21.

## Planning Contract

### Key Technical Decisions

- KTD1. **Library recipe is a verbatim copy of `minting.py`, guarded by parity tests on both sides.** folio-propositions carries golden vectors; folio-insights carries a property-based parity test (U4). Neither side imports the other's implementation. Covers R1, R13.
- KTD2. **`content_iri` is a new optional field; `id` stays the job-scoped uuid5.** Lookup routes accept either. Covers R2, R7, R8.
- KTD3. **Default source URI is `urn:sha256:<sha256(normalized canonical text)>`** via `document_source_uri()`; a caller `source_uri` on `/enrich` wins. Covers R9.
- KTD4. **Lifecycle = `axiom_history` of `AxiomTransition` entries + legal-transition table + Ed25519 signatures over canonical JSON.** The core library stays pydantic-only; did:key verification lives behind the `signing` extra. v3 records with a non-default status get one unsigned `migrate` entry. Covers R3–R5.
- KTD5. **Export is two registry formats (`propositions`, `propositions-ndjson`)** so the existing export route, auth and byte-neutral guarantees carry over. Covers R10.
- KTD6. **One hypothesis shard per content IRI; all enrich types and source ids go to a provenance manifest** (`bridge-ingest/manifest.jsonl` under the corpus root), because the envelope is `extra="forbid"` and owned by the axioms lane. Covers R11, R12.
- KTD7. **Insights read API is `POST /api/bridge/v1/status` (batch ≤ 500) + `GET /health`; ingest over HTTP only with `FOLIO_INSIGHTS_BRIDGE_TOKEN`.** Enrich proxies it at `GET /enrich/{job_id}/insights-status`. Covers R15–R19.
- KTD9. **Enrich hypotheses carry fixed, documented envelope defaults** (resolves the deferred envelope question): `epistemic_status=hypothesis`, `generation_method=inductive`, `verification_method=extractor_assertion`, `layer=L3_jurisdictional`, `fork=synthetic_a_posteriori`, `predication_mode=per_accidens`, `bfo_category=continuant_dependent`, `confidence=0.5`, `framework_id` default `us.case-law.unspecified` (overridable per ingest), speech act from the asserter role. They mark the shard as an unreviewed extractor claim; insights governance promotes or corrects them. Mapping table: folio-insights `docs/bridge-ingest.md`. Covers R11, R12.
- KTD8. **Bridge retirement ships per seam behind parity tests in its own insights PR** (separate worktree), so a failed seam never blocks bridge-ingest. Covers R20–R22.

### Sequencing

1. U1 (library) → review → merge → tag `v0.4.0`.
2. In parallel with U1: U5 (bridge retirement).
3. After U1 is reviewable: U2, U3 (enrich, same worktree, disjoint files) and U4 (insights) against an editable install of the library worktree; pins switch to `@v0.4.0` and locks refresh after the tag.
4. Real enrich export of an opinion becomes U4's committed fixture; cross-repo UAT runs enrich + insights locally.
5. U6: folio-resolve SCHEDULE.md after U5 merges.

## Implementation Units

### U1. folio-propositions v0.4.0 identity + lifecycle
- **Repo/worktree:** folio-propositions, `~/worktrees/folio-propositions-drain-bridge`.
- **Files:** `src/folio_propositions/{identity,lifecycle,signing,models,interchange,__init__}.py`, `tests/test_{identity,lifecycle,models,interchange}.py`, `docs/{migration-0.4.0,shard-mapping}.md`, `README.md`, `pyproject.toml`.
- **Covers:** R1–R6, AE1, AE2. **Worker brief:** `.codex-task/P1-prompt.md` (local, untracked).
- **Verification:** `.venv/bin/pytest -q`, `ruff check .`, `mypy src`.

### U2. Enrich identity stamping + shared-schema export
- **Repo/worktree:** folio-enrich, `~/worktrees/folio-enrich-drain-bridge`.
- **Files:** `backend/app/models/document.py`, `backend/app/models/job.py`, `backend/app/services/proposition/{identity,source,extractor}.py`, `backend/app/pipeline/stages/proposition_stage.py`, `backend/app/api/routes/enrich.py`, `backend/app/services/export/propositions_exporter.py` (+ registry import), `backend/scripts/export_insights_fixture.py`, `backend/pyproject.toml`, `backend/tests/test_proposition_content_identity.py`, `backend/tests/test_propositions_export.py`.
- **Covers:** R7–R10, AE3. **Depends on:** U1.

### U3. Enrich corpus-status proxy + Propositions-tab panel
- **Files:** `backend/app/config.py`, `backend/app/main.py`, `backend/app/services/insights_client.py`, `backend/app/api/routes/insights.py`, `frontend/index.html`, `backend/tests/test_insights_*.py`.
- **Covers:** R17–R19, AE5. **Depends on:** U1; codes against the KTD7 contract.

### U4. Insights bridge-ingest + read API
- **Repo/worktree:** folio-insights, `~/worktrees/folio-insights-drain-bridge`.
- **Files:** `src/folio_insights/bridge_ingest/**`, `api/routes/bridge.py`, one line in `api/main.py`, one command block in `src/folio_insights/cli.py`, `tests/bridge_ingest/**`, `pyproject.toml` pin, `docs/bridge-ingest.md`.
- **Covers:** R11–R16, AE4. **Depends on:** U1.

### U5. Retire sys.path bridges
- **Repo/worktree:** folio-insights, `~/worktrees/folio-insights-drain-retire`.
- **Files:** `src/folio_insights/services/bridge/{folio_bridge,mapper_bridge,ingestion_bridge}.py`, new vendored/adapter modules under `src/folio_insights/services/`, their tests, `docs/bridge-retirement-2026-10-09.md`.
- **Covers:** R20, R21.

### U7. Post-job review/push flow
- **Repo/worktree:** folio-enrich, same worktree, after U2 and U3 land.
- **Files:** settings/preferences store and routes, a new `backend/app/services/post_job/` module, the job-completion hook, the `/enrich` request model (override fields), `backend/app/services/insights_client.py` (push), `frontend/index.html` (submission + completion controls, status chips), `backend/tests/test_post_job_*.py`.
- **Covers:** R23–R28. **Depends on:** U2, U3, U4's ingest route.

### U6. folio-resolve SCHEDULE.md
- **Files:** `docs/migration/SCHEDULE.md` in folio-resolve. **Covers:** R22. **Depends on:** U5.

## Verification Contract

- folio-propositions: `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy src`.
- folio-enrich: `cd backend && .venv/bin/python -m pytest tests/ -q -n 8 -p no:cacheprovider` (baseline 1105 passed on origin/main 510a652 with `en_core_web_sm` installed).
- folio-insights: `.venv/bin/python -m pytest -m "not gate5" -q -p no:cacheprovider --timeout 300 --ignore=tests/bench`, plus `tests/bridge_ingest`; `ruff check` on touched files (CI runs ruff `--exit-zero`).
- Cross-repo UAT: run enrich locally with proposition extraction on an opinion, export `?format=propositions`, `folio-insights bridge-ingest` into a scratch corpus, serve insights, point `FOLIO_ENRICH_INSIGHTS_API_URL` at it, and screenshot the Propositions tab with Playwright. Evidence goes to `docs/plans/evidence/` in folio-enrich.

## Definition of Done

- U1 merged and tagged `v0.4.0`; enrich and insights pin `@v0.4.0` with refreshed locks.
- U2–U5 merged with green suites; U6 merged.
- AE1–AE5 each demonstrated by a test or the UAT evidence.
- No worker scratch (`.codex-task/`) or abandoned-attempt code in any diff.
