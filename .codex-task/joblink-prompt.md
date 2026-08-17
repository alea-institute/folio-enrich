# Task — ?job=<id> deep-link (folio-enrich frontend, branch main)

frontend/index.html supports `?demo=<slug>` deep-links (see tryLoadDemo, ~line 4915) but no way to open an existing backend job by id. Annotation sessions are job-attached, so reviewers need a URL that opens a job directly.

**No git. No network.** Report -> `.codex-task/joblink-report.md` (summary, files, verification).

## Build
1. `tryLoadJob()`: on startup (same place tryLoadDemo is consulted, before it), read `?job=<uuid>`; if present, GET `/enrich/{id}`; on success hydrate the full results UI from the completed job payload the same way demo hydration / job completion does (set currentJobId/currentJob, accumulated arrays incl. accumulatedPropositions, render all tabs); on 404 show the existing toast style and fall through to normal startup. Strip the param from the URL after load (mirroring the demo param cleanup at ~12473).
2. Optional `&tab=<name>`: after hydration, switchTab to it if it exists (e.g. tab=propositions).
3. Propositions integration: after hydrating a job with `?job=`, call the existing session-attach path (ensurePropositionSession's lookup-by-job_id branch) WITHOUT creating a new session if none exists — if a gold session exists for the job, load + render it read-only-friendly (annotation actions still require Annotation mode ON + admin token as today).
4. Keep everything inside existing conventions; no new frameworks.

## Verify
- node --check each extracted <script> block; duplicate-id grep for touched elements.
- cd backend && .venv/bin/python -m pytest tests/test_gold_store.py -q stays green (no backend change expected).
