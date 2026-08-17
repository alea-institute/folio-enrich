# Pipeline extraction review-fix report

## Findings

- **#10 — applied.** Evidence still matched: `proposition_id` hashed only job and
  span while stage deduplication retained proposition type. The stable UUID input
  now includes `proposition_type`; both extractor and LLM-assist call sites pass
  it. Regression coverage verifies same-span/different-type candidates receive
  distinct IDs and both remain addressable.
- **#14 — applied.** Evidence still matched: early-individual and
  early-proposition were separate `asyncio.gather` entries even though citation
  edges read `job.result.individuals`. The gather now uses a chained coroutine
  that awaits early-individual before early-proposition. Both stage closures keep
  their existing internal exception isolation, so an individual-stage failure
  does not prevent proposition extraction.
- **#8 — applied.** Evidence still matched: the only LLM routing test supplied an
  empty proposition list. Added coverage for a well-formed candidate merged with
  a lexicon candidate, an out-of-bounds span, a missing required key, a wrong
  value type, and a provider exception preserving lexicon-only output.
- **#11 — applied.** Evidence still matched: the byte-neutral characterization
  used explicit `stages=` and therefore `_run_flat`. Added a production-config
  test using `PipelineOrchestrator(store, llm=None, task_llms=TaskLLMs())` without
  `stages=`, exercising `_run_parallel` with the flag off and on and checking
  both `job.result.propositions` and `proposition_added` SSE events. Unrelated
  enrichment stages are disabled after production config construction to keep
  this wiring test focused and fast.

No findings were skipped.

## Files changed

- `backend/app/services/proposition/identity.py`
- `backend/app/services/proposition/extractor.py`
- `backend/app/pipeline/stages/proposition_stage.py`
- `backend/app/pipeline/orchestrator.py`
- `backend/tests/test_proposition_stage.py`
- `backend/tests/test_proposition_byte_neutral.py`
- `.codex-task/fix-pipeline-report.md`

## Verification

### Focused changed-area tests

Command:

```text
.venv/bin/python -m pytest tests/test_proposition_stage.py tests/test_proposition_byte_neutral.py -q
```

Final output tail:

```text
................                                                 [100%]
16 passed in 0.37s
```

### Required targeted group

Command:

```text
.venv/bin/python -m pytest tests/test_proposition_stage.py tests/test_proposition_byte_neutral.py tests/test_progressive_pipeline.py tests/test_synthetic_runner.py -q
```

Final output tail:

```text
FAILED tests/test_progressive_pipeline.py::TestStringMatchMerge::test_merges_existing_annotations
FAILED tests/test_progressive_pipeline.py::TestStringMatchMerge::test_keeps_rejected_annotations
ERROR tests/test_progressive_pipeline.py::TestEntityRulerAnnotations::test_deterministic_tags_flush_early_and_survive_semantic_failure
2 failed, 35 passed, 3 deselected, 1 error in 30.77s
```

The two failures are sandbox-environment failures from the pre-existing FOLIO
import attempting to open the read-only path
`/home/damienriehl/.alea/logs/alea_llm_client.log`. The teardown error is a
pre-existing progressive test timing out after 30 seconds in asyncio selector
shutdown. All 16 proposition tests, including every new regression, passed in
the same environment.

### Required full suite

Command:

```text
.venv/bin/python -m pytest tests/ -q
```

Final observed output before manual interruption after more than 180 seconds:

```text
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
..
```

The full run stalled near its start under the restricted sandbox and produced
no further diagnostic output, so it was interrupted (exit 130). It did not
produce a green full-suite result in this environment.
