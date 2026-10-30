---
title: "fix: repo-wide bug sweep (security, ingestion, exports, performance, providers, UI)"
status: completed
date: 2026-10-30
---

# fix: repo-wide bug sweep

## Context
After the citeurl fix (PR #51), a four-way sweep looked for components that silently
don't work: an end-to-end API/format probe, a static backend audit with probes, a
Playwright pass over the frontend, and a read-only probe of PROD
(enrich.openlegalstandard.org). Every item below was reproduced; repro scripts lived
in the session scratchpad.

PROD runs a build from roughly 2026-07 (between PR #20 and PR #35), up to ~95
commits behind `main`.

## Findings → units (file-disjoint so units run in parallel)

### U1 — Security: unauthenticated mutating routes (P0)
- `POST /ollama/setup|start|stop|pull` need no auth; `/setup` runs
  `curl https://ollama.com/install.sh | sh` and pulls multi-GB models. Reachable on PROD.
- `DELETE /feedback`, `DELETE /feedback/{id}` need no auth; `GET /feedback/export`
  dumps all users' feedback (57 KB on PROD).
- Fix: gate with the existing admin-token dependency in `app/api/auth.py`; keep
  local single-user use working when no admin token is configured and the deploy
  is not public. Files: `api/routes/ollama.py`, `api/routes/feedback.py`, tests.

### U2 — Dependencies and status reporting (P1)
- `openai` and `anthropic` SDKs undeclared → Ollama (default local provider),
  OpenAI, Mistral, Groq, LM Studio, xAI, Llama, GitHub Models and Anthropic fail at call time.
- `/health/detail` and `/ontologies` report embeddings "ready" when
  sentence-transformers is missing and the index build failed.
- FastAPI app version hardcoded `0.4.11`; FOLIO constructed without `llm=None`
  (OpenAI traceback on every load); `FolioService.search_by_prefix` always `[]`.
- Files: `pyproject.toml`, `uv.lock`, `THIRD-PARTY.md`, `main.py` (version only),
  `services/embedding/service.py`, `api/routes/health.py`, `api/routes/ontologies.py`,
  `services/folio/folio_service.py`.

### U3 — Ingestion and pipeline robustness (P1)
- Pre-parallel stage failure (ingestion) is logged and the job ends "completed"
  with zero output; it must fail the job.
- nupunkt 0.6 has no `SentenceTokenizer` → regex fallback splits at "Stat.", "v.", "Corp.".
- `.eml` raw text is base64-"decoded" into garbage (~25% of emails).
- C0 control characters survive normalization → malformed XML export, Excel 500.
- Request LLM provider overridden by Ollama tier mode (`_try_get_task_llm`).
- `.doc` routed to python-docx, which can't read it.
- Files: `pipeline/orchestrator.py`, `services/normalization/normalizer.py`,
  `services/ingestion/*`.

### U4 — Event-loop blocking and throughput (P1)
- Sync spaCy / Aho-Corasick / eyecite work inside `async execute` stalls the
  server (15.5 s max stall on a 65 KB doc); FOLIO ruler patterns rebuilt per job (2–3 s).
- `count_active` parses every job file per request; unbounded LLM chunk fan-out.
- Semantic ruler runs even when embeddings can't embed; PROD shows semantic spans
  that absorb neighbor words ("Corp. in the", "in damages. The").
- Forged CF Access `kid` forces a blocking JWKS refetch per request.
- Files: `pipeline/stages/*` (not orchestrator), `services/entity_ruler/semantic_ruler.py`,
  `storage/job_store.py`, `services/concept/llm_concept_identifier.py`, `api/auth.py`.

### U5 — Extraction correctness (P2)
- Money regex grabs the next word's initial ("$10 more" → "$10 m"); span not
  re-trimmed.
- spaCy `max_length` (1M chars) → long documents lose concepts, triples, NER.
- Triple subject/object text token-joined ("DEFENDANT 'S", "12(b)(6 )").
- Files: `services/individual/entity_extractors.py`, `services/dependency/parser.py`,
  `services/entity_ruler/ruler.py`.

### U6 — LLM providers (P2)
- `OpenAICompatProvider.structured` ignores the schema; the proposition prompt never
  says "JSON" → OpenAI 400s, Ollama returns wrong keys.
- Shut-down / nonexistent model IDs (gemini-3-pro-preview, gemini-3.5-flash,
  gemini-2.0-flash fallback, grok-3); Llama compat base URL.
- Anthropic/Cohere bare `json.loads`; GET /settings omits three task overrides.
- Files: `services/llm/*`, `pipeline/stages/proposition_stage.py`, `api/routes/settings.py`.

### U7 — Exports (P2)
- Parquet export concatenates four Parquet files → unreadable.
- XML/Excel exporters crash on control characters (defense in depth with U3).
- Files: `services/export/*`.

### U8 — Frontend and demo data (P2)
- Insights shows literal `${_thumbUpIcon}`; upload of PDF/DOCX resubmits extracted
  text with the binary filename → empty job; demo state persists after Demo off.
- 20 demos baked `status: "matching"` → marked failed at each startup; demo
  class_links point to missing annotations → "Failed to load lineage".
- Tabs clipped with the detail panel open (1px scrollbar, no keyboard access);
  demo title lost on reload; Escape misses three modals; export copy says 12
  formats; clashing export filenames; skipped LLM stages shown complete.
- Files: `frontend/index.html`, `frontend/demos/*.json`, `services/demo_seed.py`.

## Out of scope
- Deploying to PROD: SSH blocked (key file absent locally; port 22 closed from the
  static Hetzner IP). Needs access restored by Damien/Mike.
- Known citeurl parsing limits (documented in PR #51).

## Verification
Each unit adds regression tests; full backend suite plus a Playwright pass over the
fixed UI paths; DEV deploy and smoke test.

## Outcome (2026-10-30)
- All 8 units merged on `fix/bug-sweep`, plus integration fixes (parser Span text
  for O(n) triples, admin gate moved to `app/api/auth.py`, Word ingestor never opens
  request content as a path, Ollama tiering keyed on the request's provider,
  `nupunkt>=0.6.0`, EntityRuler warmed at startup) and review fixes (admin gate on
  every server-wide `PUT /settings` field, HTML export nesting, dropped `.doc` routed
  to extraction, embedding readiness requires a working encoder).
- Full backend suite: 1546 passed (two consecutive runs).
- Live checks on a local server: uploads via the frontend path and raw `.eml` ingest
  correctly; all 15 export formats parse with control characters in the source;
  money amounts no longer absorb the next word; `/health` max 1.17 s during a 65 KB
  job (was 7.65 s on 27 KB); public posture returns 403 for anonymous
  `PUT /settings`, `/ollama/*` mutations, and feedback export/delete.
- Model-ID choices (Google default kept at gemini-3-flash-preview; Meta provider moved
  to the Meta Model API) are recorded in the U6 commit.
- PROD deploy blocked on SSH access (see Out of scope).
