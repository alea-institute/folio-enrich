# Code Quality Review — Proposition System Phase A

## `backend/app/services/gold/store.py:181` — GoldStore mutates JobStore's module-global protection set

### What to change

Stop importing and mutating `PROTECTED_JOB_IDS` directly from `GoldStore`. Put the mutation behind a small `JobStore` method and let `GoldStore` ask its injected store to update protection.

### Why

`GoldStore` currently reaches through the `JobStore` abstraction and changes storage-layer process state itself. That couples gold persistence to an internal implementation detail and makes the injected `JobStore` only partially authoritative: cleanup derives protection from disk, while `_save()` separately maintains the module-global set. Encapsulating the existing mutation preserves the current in-memory and on-disk behavior while giving `JobStore` one boundary at which those mechanisms can later be reconciled safely.

### Concrete sketch

Add a method such as `JobStore.set_gold_session_protected(job_id: str, protected: bool)`, whose body performs the current `PROTECTED_JOB_IDS.add(...)` / `.discard(...)`. Replace lines 181–184 with `self.job_store.set_gold_session_protected(session.job_id, session.exported_at is None)`. Keep `_has_unexported_gold_session()` and the cleanup condition unchanged, so outputs, cleanup decisions, and side effects remain identical.

**Confidence:** high

## `backend/app/services/gold/store.py:69` — Gold outcome and learning vocabularies are declared more than once

### What to change

Define named type aliases for the wrapper-owned vocabularies and reuse them in the store models, store method signatures, and API request models.

### Why

The candidate outcome union appears in `CandidateRecord.outcome`, `GoldStore.record_candidate_outcome()`, and `CandidateOutcomeRequest.outcome`; the learning-kind union similarly appears in `CycleLearning.kind` and `LearningRequest.kind`. These are wrapper concepts, so the gold store should be their source of truth. Copying the raw strings into the route layer makes additions or renames prone to partial updates while providing no boundary benefit. This change does not touch the separate library proposition schema or its migration path.

### Concrete sketch

In `store.py`, introduce aliases such as `CandidateOutcome = Literal["accepted", "edited", "deleted", "unreviewed"]` and `CycleLearningKind = Literal["new-type", "unclassifiable", "forced-fit", "structural-misfit"]`. Use them for `CandidateRecord.outcome`, `CycleLearning.kind`, and `record_candidate_outcome(..., outcome: CandidateOutcome)`, then import those aliases in `api/routes/gold.py` for the request models. Leave defaults, validation, serialized strings, and ordering unchanged.

**Confidence:** high

## `backend/app/pipeline/orchestrator.py:108` — Per-task LLM resolution is copy-pasted between pipeline builders

### What to change

Extract the repeated task-provider resolution block used by `build_pipeline_config()` and `build_stages()` into one internal helper.

### Why

Both builders independently resolve the same eight local variables with the same fallback expression; Phase A had to add `proposition_llm` to both blocks. Every new task now has two places where a missed line can make sequential and parallel pipeline construction behave differently. A helper keeps the two public construction paths and their exact stage ordering intact while making provider fallback semantics a single source of truth.

### Concrete sketch

Add an internal resolver that accepts `(task_llms, fallback)` and returns a small named value object (for example a frozen `ResolvedTaskLLMs` dataclass) with `concept`, `branch_judge`, `classifier`, `extractor`, `individual`, `property_llm`, `proposition`, and `document_type`. Populate each field with the current expression `(task_llms.<field> if task_llms else fallback) or fallback`. Have both builders read locals from that object; do not merge the builders or alter any conditional/stage ordering.

**Confidence:** high

## `backend/app/api/routes/gold.py:60` — Store exception translation is repeated in every endpoint

### What to change

Centralize the repeated `try`/`except (ValueError, LookupError)` translation in one async route helper.

### Why

Nine endpoints repeat the same exception boundary, and `get_session()` repeats a narrower variant even though `_http_error()` already determines the status from the exception type. This is copy-paste at the API/store boundary; future endpoints or exception changes can easily drift. A small operation helper removes the duplication without changing route signatures, FastAPI schema generation, response bodies, or exception chaining.

### Concrete sketch

Add a typed internal helper that accepts a zero-argument callable, invokes and awaits it inside `try`, catches `(ValueError, LookupError)`, and raises `_http_error(exc) from exc`. Each route remains a normal explicitly declared FastAPI function and returns, for example, `await _call_store(lambda: _gold_store.<operation>(...))`. Keeping invocation inside the helper preserves the current exception boundary as well as request models, decorators, status codes, response bodies, exception chaining, and argument evaluation order.

**Confidence:** high
