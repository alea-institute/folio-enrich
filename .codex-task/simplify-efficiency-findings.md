# Efficiency review findings

## 1. Build the unexported-session protection set once per cleanup

- **Location:** `backend/app/storage/job_store.py:130`
- **What to change:** Stop calling `_has_unexported_gold_session()` separately for every job file. Scan `gold_sessions/*.json` once at the start of `cleanup_expired()`, collect the `job_id` values for records without `exported_at`, and use set membership inside the job loop.
- **Why:** The current cleanup performs a complete directory scan and JSON parse of every gold session for every job. With `J` jobs and `S` sessions this is `J x S` file reads/parses, even though the answer can be derived in `S` reads followed by `J` constant-time lookups. Cleanup is recurring maintenance work, so this cost grows unnecessarily with both retained collections.
- **Concrete sketch:** Replace the per-job helper call with something equivalent to:

  ```python
  unexported_job_ids: set[str] = set()
  for session_path in (self.base_dir / "gold_sessions").glob("*.json"):
      try:
          data = json.loads(session_path.read_text())
          if not data.get("exported_at") and data.get("job_id") is not None:
              unexported_job_ids.add(str(data["job_id"]))
      except Exception:
          continue

  for path in list(self.base_dir.glob("*.json")):
      if path.stem in PROTECTED_JOB_IDS or path.stem in unexported_job_ids:
          continue
      # existing expiration logic unchanged
  ```

  This preserves the existing malformed-session skip behavior and protection decision while reducing the scan to `O(S + J)`.
- **Confidence:** high

## 2. Reuse the dependency parse for proposition extraction

- **Location:** `backend/app/services/proposition/extractor.py:33`
- **What to change:** Allow `PropositionExtractor.extract()` to consume an already parsed spaCy `Doc`, and arrange for the parallel-phase coordinator to create/reuse one parse for both `EarlyPropositionStage` and `EarlyTripleStage` when both are enabled.
- **Why:** Proposition extraction now calls `get_spacy_nlp()(text)` over the entire canonical document, while the concurrently scheduled triple stage also parses the same full text in `DependencyParser.extract_triples_and_pos()` (`backend/app/services/dependency/parser.py:42`). spaCy parsing is CPU- and memory-intensive; the new stage therefore duplicates one of the most expensive per-job transforms. These async stage bodies perform their parsing synchronously, so `asyncio.gather()` does not make the duplicate CPU work cheaper.
- **Concrete sketch:** Add `extract(job, *, doc=None)` and use `doc or get_spacy_nlp()(text)` in the proposition extractor; likewise expose a dependency-parser entry point that derives triples/POS/NER from a supplied `Doc`. In the orchestrator's parallel phase, lazily obtain one `Doc` for the canonical text and pass that same immutable parse result to those two consumers, retaining their current result assignment, error isolation, stage ordering, and feature-flag guards. Do not store the `Doc` in serialized job metadata, so the flag-off byte-neutral contract remains unchanged.
- **Confidence:** medium

## 3. Count section propositions with indexed span starts

- **Location:** `backend/app/services/gold/store.py:470`
- **What to change:** Precompute sorted non-`None` proposition start offsets once, then use binary-search bounds to count starts within each canonical element instead of rescanning every gold proposition for every element.
- **Why:** `_density()` currently executes `sum(... for p in gold)` inside the element loop. Export density therefore costs `O(E x P)` for `E` canonical elements and `P` gold propositions, despite each section count depending only on whether a proposition start lies in `[start, end)`. Large opinions with many elements and annotations pay avoidable repeated comparisons during export.
- **Concrete sketch:** Before the element loop, create `gold_starts = sorted(p.start_char for p in gold if p.start_char is not None)`. For each located element, compute `count = bisect_left(gold_starts, end) - bisect_left(gold_starts, start)` and add that count to the existing section bucket. Keep the current sequential `full_text.find(element.text, offset)` logic and bucket update order unchanged; only replace the inner proposition scan.
- **Confidence:** high
