# Task — apply simplify-review findings (folio-enrich, branch feat/proposition-system-phase-a)

Apply the following six behavior-preserving simplifications. Rules: **no git commands, no network**; run the named tests after each change; every change must preserve outputs, errors, side effects, and ordering exactly. Write your report to `.codex-task/simplify-apply-report.md` (summary, per-finding applied/skipped + reason, final test output tails).

1. `backend/app/services/gold/store.py` (~line 57): in `migrate_proposition_payload`, drop the wrapper-side `deepcopy` and pass `data` straight to `folio_propositions.migrate_record` (the library already deep-copies; its docstring guarantees a migrated copy). Keep every other deepcopy (wrapper migrations) untouched.

2. Shared deterministic proposition-ID helper: both `backend/app/services/proposition/extractor.py` (~116) and `backend/app/pipeline/stages/proposition_stage.py` (~86) inline `str(uuid5(NAMESPACE_URL, f"folio-enrich:{job.id}:{start}:{end}"))`. Add `proposition_id(job_id, start, end) -> str` in `backend/app/services/proposition/identity.py` (exact same namespace/format), export from the package `__init__`, and call it from both sites. IDs must be byte-identical to before.

3. `backend/app/pipeline/orchestrator.py`: `build_pipeline_config` (~142) and `build_stages` (~208) duplicate the per-task LLM resolution (`concept_llm = (task_llms.concept if task_llms else llm) or llm`, etc.). Extract one private helper (e.g. `_resolve_task_llms(llm, task_llms)` returning a small frozen dataclass or dict) using the exact existing expressions, and consume it in both builders. Stage construction and ordering unchanged.

4. `frontend/index.html`: the five-assignment reset of `propositionSession`, `propositionDraft`, `propositionCompleteness`, `propositionAddArmed`, `propositionBlindArmed` appears at ~6516 and ~12403. Extract `function resetPropositionSessionState()` with the five assignments in current order; call it from both sites. Nothing else (no DOM updates, no accumulatedPropositions) goes in the helper. After editing, extract the inline <script> blocks and `node --check` them.

5. `backend/app/storage/job_store.py` `cleanup_expired` (~130): replace the per-job `_has_unexported_gold_session` call with a single upfront scan of `gold_sessions/*.json` building a set of unexported job_ids, then set-membership in the loop (O(S+J) instead of O(J*S)). Preserve the malformed-session skip behavior. Update/keep `_has_unexported_gold_session` only if still referenced; remove it if now dead (check tests).

6. `backend/app/services/gold/store.py` `_density` (~470): precompute `gold_starts = sorted(p.start_char for p in gold if p.start_char is not None)` before the element loop and count per-element via `bisect_left` bounds instead of the inner scan. Keep the sequential `full_text.find(element.text, offset)` logic and bucket order unchanged.

Verification (run all, include tails in the report):
- `cd backend && .venv/bin/python -m pytest tests/test_gold_store.py tests/test_gold_validity.py tests/test_proposition_stage.py tests/test_proposition_byte_neutral.py tests/test_job_retention.py -q`
- `cd backend && .venv/bin/python -m pytest tests/ -q` (full suite)
- node --check on the extracted frontend script blocks.
