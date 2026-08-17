# Code Reuse Review — Proposition System Phase A

## Redundant copy before the library migration

- **Location:** `backend/app/services/gold/store.py:57`
- **What to change:** Remove the wrapper-side `deepcopy` in `migrate_proposition_payload` and pass `data` directly to the imported `folio_propositions.migrate_record`.
- **Why:** `migrate_record` explicitly guarantees that it returns a migrated copy and begins by applying its own `deepcopy(data)`. The current wrapper therefore deep-copies the complete proposition payload twice. Reusing the library guarantee keeps the intentionally separate wrapper-vs-library migration boundary intact while removing duplicate work.
- **Concrete sketch:**

  ```python
  def migrate_proposition_payload(
      data: dict[str, Any], target_version: int = SCHEMA_VERSION
  ) -> dict[str, Any]:
      return migrate_record(data, target_version=target_version)
  ```

  Keep the `deepcopy` calls in `migrate_session` and its wrapper migration functions; those belong to the separate wrapper-schema mechanism and are not covered by the proposition library.
- **Confidence:** high

## Reuse the deterministic proposition-ID rule across extraction paths

- **Location:** `backend/app/pipeline/stages/proposition_stage.py:86` (duplicated at `backend/app/services/proposition/extractor.py:116`)
- **What to change:** Extract the existing `str(uuid5(NAMESPACE_URL, f"folio-enrich:{job.id}:{start}:{end}"))` rule into one proposition-domain helper and call it from both `EarlyPropositionStage._assist` and `PropositionExtractor._build`.
- **Why:** The lexicon and LLM paths independently reproduce the same namespace, prefix, field ordering, coercion, and string conversion. That identity equivalence is what lets the stage deduplicate candidates from both sources. A shared helper preserves the exact generated IDs while preventing either path from silently drifting and breaking cross-source deduplication.
- **Concrete sketch:**

  ```python
  # app/services/proposition/identity.py
  from uuid import NAMESPACE_URL, UUID, uuid5

  def proposition_id(job_id: UUID | str, start: int, end: int) -> str:
      return str(uuid5(NAMESPACE_URL, f"folio-enrich:{job_id}:{start}:{end}"))
  ```

  Then replace both inline expressions with `proposition_id(job.id, start, end)`. Do not move proposition model construction into the helper: the two paths intentionally populate different fields and side effects.
- **Confidence:** high
