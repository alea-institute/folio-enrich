# Code-quality findings

## 1. Derive the per-task LLM selection once

- **Location:** `backend/app/pipeline/orchestrator.py:142` (duplicated at `backend/app/pipeline/orchestrator.py:208`)
- **What to change:** Extract the repeated `concept_llm` through `document_type_llm` resolution into one small internal helper, and have both `build_pipeline_config()` and `build_stages()` consume its result.
- **Why:** The two pipeline constructors currently maintain parallel copies of the same task-to-field/fallback mapping. Phase A added `proposition_llm` to both copies, demonstrating the ongoing synchronization cost: every new task must be wired twice, and a future one-sided edit could make sequential and parallel pipeline construction behave differently. A named resolved-provider object or mapping removes that redundant state without merging the two pipeline builders.
- **Concrete sketch:** Add a private frozen dataclass such as `_ResolvedTaskLLMs` and a `_resolve_task_llms(llm, task_llms)` helper whose fields use the exact existing expressions (for example, `proposition=(task_llms.proposition if task_llms else llm) or llm`). At the start of each builder, call it once and replace local names with `resolved.proposition`, `resolved.concept`, and so on. Keep stage construction and ordering unchanged.
- **Confidence:** high

## 2. Centralize deterministic proposition identity construction

- **Location:** `backend/app/services/proposition/extractor.py:116` (duplicated at `backend/app/pipeline/stages/proposition_stage.py:86`)
- **What to change:** Put the deterministic proposition-ID calculation behind one proposition-domain helper and call it from both the lexicon extractor and LLM-assist adapter.
- **Why:** Both paths independently encode the same identity contract: UUIDv5, `NAMESPACE_URL`, and the exact `folio-enrich:{job.id}:{start}:{end}` name. This is a meaningful domain invariant used by downstream deduplication, not incidental formatting. Keeping two copies makes it easy for one candidate source to drift and stop deduplicating with the other.
- **Concrete sketch:** Define `proposition_id(job_id, start, end) -> str` in a small shared module under `app.services.proposition` (or export it from that package), implemented with the exact current UUID namespace and f-string. Replace only the two UUID expressions with calls to it; retain all candidate ordering, model construction, and deduplication behavior.
- **Confidence:** high

## 3. Give full proposition-session reset a single owner

- **Location:** `frontend/index.html:6516` (duplicated at `frontend/index.html:12403`)
- **What to change:** Extract the identical five-assignment reset of `propositionSession`, `propositionDraft`, `propositionCompleteness`, `propositionAddArmed`, and `propositionBlindArmed` into a small function used by both the new-job/reset path and `clearAll()`.
- **Why:** These five variables form one lifecycle unit, but the complete reset sequence is copied in two places. Future annotation-mode state is likely to be added beside them and could be cleared on one lifecycle path but retained on the other. This helper should cover only the full lifecycle reset; the smaller mode/draft transitions elsewhere have distinct behavior and should remain separate.
- **Concrete sketch:** Add `function resetPropositionSessionState() { ... }` containing the five assignments in their current order, then replace each complete five-line block with a call at the same point. Do not include `accumulatedPropositions`, settings, rendering, or any DOM updates in the helper, so outputs and side-effect ordering remain unchanged.
- **Confidence:** high
