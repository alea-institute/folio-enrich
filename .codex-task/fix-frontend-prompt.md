# Review-fix task (folio-enrich, branch feat/proposition-system-phase-a)

Apply the code-review findings below. Rules: **no git commands, no network**; at each file:line first confirm the evidence still matches (skip with a one-line reason if not); preserve all existing behavior not named by a finding; keep the byte-neutral contract (flag off => exports+SSE byte-identical) intact; run the named tests and keep them green. Venv: backend/.venv. Write your report to the out-file path given at the end: per-finding applied/skipped with reasons, files changed, and final test output tails.

## Batch: frontend annotation mode (findings #1, #13, #15 — apply in this order: #15, #13, #1)

### Finding #1 [P1] backend/app/api/routes/enrich.py:105 — Gold provenance records lexicon-only after LLM fallback
Why: A request-level or global fallback LLM is assigned to the proposition task, but session creation inspects only the proposition-specific settings override. The resulting manifest claims lexicon-only provenance even when LLM candidates were generated, invalidating baseline and precision comparisons.
Suggested fix: Persist the resolved per-job task configuration and derive session provenance from that immutable record, including request fallback provider and model, instead of rereading current global settings in the browser.
Evidence: [
"backend/app/api/routes/enrich.py:105:    task_llms = TaskLLMs.from_settings(fallback=fallback_llm)",
"backend/app/pipeline/orchestrator.py:356:    return fallback",
"frontend/index.html:11873:    const llm = propositionSettings.task_llm_overrides?.proposition || {};"
]

### Finding #13 [P1] frontend/index.html:12047 — Late response reattaches session to a different job
Why: Autosave responses overwrite the global propositionSession without checking which job initiated the request. If the user loads a demo, clears results, or switches jobs while PATCH is pending, the old session can be rendered and mutated alongside the new job.
Suggested fix: Capture a job/session generation before each await and discard stale responses. Reset proposition state in demo hydration and clear paths, and serialize or abort requests when changing jobs.
Evidence: [
"frontend/index.html:12047:    propositionSession = await propositionFetch(`/gold/sessions/${propositionSession.session_id}/candidates/${encodeURIComponent(card.dataset.candidateId)}`, { method: 'PATCH', body: JSON.stringify(body) });",
"frontend/index.html:4932:  currentJobId = cache.jobId;",
"frontend/index.html:4982:  currentJobId = null;"
]

### Finding #15 [P2] frontend/index.html:11972 — Hand-added draft pre-checks explicit_unresolved, defeating deliberate-unresolved gate
Why: The backend refuses an unresolved disposition unless explicit_unresolved=True precisely so 'unresolved' in gold records always reflects a deliberate annotator choice (_validate_unresolved, store.py:164-166). But the frontend creates every hand-added draft with disposition 'unresolved' (index.html:12123) and renders the draft card with explicit_unresolved: true, which pre-checks the 'Mark unresolved deliberately' checkbox. Saving the draft without touching anything therefore passes the gate automatically — the instrument-validity control is satisfied by default rather than by action, so hand-added gold records can carry unresolved dispositions nobody consciously chose.
Suggested fix: Render the draft with explicit_unresolved: false (cards.unshift(renderPropositionCard({ proposition: propositionDraft, outcome: 'hand-added', explicit_unresolved: false }, true))) so the annotator must check the confirmation box (or change the disposition) before saveHandAdded succeeds; the backend 422 already provides the error path.
Evidence: [
"frontend/index.html:11972 -- if (propositionDraft) cards.unshift(renderPropositionCard({ proposition: propositionDraft, outcome: 'hand-added', explicit_unresolved: true }, true));",
"frontend/index.html:12123 -- propositionDraft = { ... disposition: 'unresolved', citation_edges: [], triple_ids: [] };",
"backend/app/services/gold/store.py:164-166 -- if proposition.disposition == Disposition.UNRESOLVED and not explicit: raise ValueError(\"unresolved disposition requires explicit_unresolved=True\")"
]

Implementation notes:
- #15: render the hand-added draft card with explicit_unresolved: false so the annotator must actively check "Mark unresolved deliberately" (or pick another disposition) before saving; keep the inline confirm UI unchanged.
- #13: guard stale async responses: capture the active job id (and session id where applicable) before each await in the proposition fetch handlers (ensurePropositionSession, savePropositionOutcome, saveHandAdded, learnings, blind/coverage/export handlers); after the await, discard the response (no state assignment, no render) when currentJobId changed. Also call resetPropositionSessionState() in the demo-hydration and clear paths that switch currentJobId (find hydrateFromDemo ~4932 and clearResultsOnly ~4982) so a job switch clears annotation state.
- #1: compute hasLlm from the EFFECTIVE proposition-task LLM, not just the task override: treat the task as LLM-backed when the proposition override is set OR a global default provider+model is configured in the settings payload (fields llm_provider/llm_model from GET /settings). Record those effective values in pre_selector. Add a short code comment naming the residual caveat: a per-request BYOK key (never stored server-side) cannot be detected here, so provenance may still under-report request-scoped assist; server-side provenance capture is Phase B work.

Verification: extract each inline <script> block and node --check it; grep for duplicate ids among edited elements; cd backend && .venv/bin/python -m pytest tests/test_gold_store.py tests/test_gold_validity.py -q (round-trip contract unchanged).
Out-file: .codex-task/fix-frontend-report.md
