# U2 Report — Early Proposition Stage

## Summary

Implemented default-off proposition pre-selection in the parallel enrichment phase. The new
`EarlyPropositionStage` extracts dependency-framed candidate spans without an LLM, optionally
merges structured LLM suggestions routed through the `proposition` task, and stores the library's
`folio_propositions.Proposition` models on `JobResult`. SSE now emits each proposition ID once.

The feature is byte-neutral while `proposition_extraction_enabled=False` (the default): every
registered export and the completed-job SSE sequence match the pristine fixtures byte-for-byte;
job JSON differs only by `result.propositions: []`.

No network or Git commands were used. The tree is intentionally uncommitted.

## Changed files

- `.codex-task/U2-report.md`
- `backend/app/config.py`
- `backend/app/models/job.py`
- `backend/app/pipeline/orchestrator.py`
- `backend/app/pipeline/stages/proposition_stage.py`
- `backend/app/services/ollama/manager.py`
- `backend/app/services/proposition/__init__.py`
- `backend/app/services/proposition/extractor.py`
- `backend/app/services/proposition/lexicon.py`
- `backend/app/services/streaming/sse.py`
- `backend/eval/synthetic_runner.py`
- `backend/tests/test_ollama_manager.py`
- `backend/tests/test_progressive_pipeline.py`
- `backend/tests/test_proposition_byte_neutral.py`
- `backend/tests/test_proposition_stage.py`
- `backend/tests/test_synthetic_runner.py`
- `backend/tests/test_task_llms.py`
- `backend/tests/fixtures/proposition_baseline/export.brat`
- `backend/tests/fixtures/proposition_baseline/export.csv`
- `backend/tests/fixtures/proposition_baseline/export.elasticsearch`
- `backend/tests/fixtures/proposition_baseline/export.excel`
- `backend/tests/fixtures/proposition_baseline/export.html`
- `backend/tests/fixtures/proposition_baseline/export.json`
- `backend/tests/fixtures/proposition_baseline/export.jsonl`
- `backend/tests/fixtures/proposition_baseline/export.jsonld`
- `backend/tests/fixtures/proposition_baseline/export.neo4j`
- `backend/tests/fixtures/proposition_baseline/export.parquet`
- `backend/tests/fixtures/proposition_baseline/export.rag`
- `backend/tests/fixtures/proposition_baseline/export.rdf`
- `backend/tests/fixtures/proposition_baseline/export.xml`
- `backend/tests/fixtures/proposition_baseline/job.json`
- `backend/tests/fixtures/proposition_baseline/sse.json`

## Verification evidence

### Pristine characterization baseline (before production changes)

Fixture generation:

```text
FOLIO_REGEN_PROPOSITION_BASELINE=1 .venv/bin/python -m pytest tests/test_proposition_byte_neutral.py -q
.                                                                        [100%]
1 passed in 0.09s
```

Two subsequent assertion-only runs proved run-to-run determinism:

```text
.                                                                        [100%]
1 passed in 0.10s
.                                                                        [100%]
1 passed in 0.09s
```

The XLSX exporter embeds clock values in ZIP headers and `docProps/core.xml`. The harness
canonicalizes only those container metadata timestamps before byte comparison; workbook member
payloads remain unchanged. UUIDs and timestamps in the job are likewise replaced consistently
before exports, SSE, and JSON are captured.

### Extraction red/green sequence

Before implementation:

```text
FFFFFFFF                                                                 [100%]
8 failed in 0.14s
```

Seven failures were the expected missing `app.pipeline.stages.proposition_stage`; the SSE test
failed because zero `proposition_added` events existed.

After implementation, the mandatory focused command:

```text
.venv/bin/python -m pytest tests/test_proposition_byte_neutral.py tests/test_proposition_stage.py -q
.........                                                                [100%]
9 passed in 0.31s
```

### Neighboring suites

```text
.venv/bin/python -m pytest tests/test_task_llms.py tests/test_ollama_manager.py tests/test_sse.py tests/test_synthetic_runner.py tests/test_progressive_pipeline.py::TestPipelineConfig tests/test_export.py -q
......................................................                   [100%]
54 passed in 0.11s
```

The wider `tests/test_pipeline.py tests/test_progressive_pipeline.py` run reached `18 passed`,
with two unrelated existing failures caused by `alea_llm_client` attempting to write
`~/.alea/logs/alea_llm_client.log` in the read-only sandbox and one unrelated 30-second async
teardown timeout. The directly affected `TestPipelineConfig` class passes above.

Compilation also passed:

```text
.venv/bin/python -m compileall -q app/services/proposition app/pipeline/stages/proposition_stage.py app/models/job.py app/pipeline/orchestrator.py app/services/streaming/sse.py
```

### Flag-on demonstration

Input:

```text
Plaintiff contends the statute requires notice. We hold that the contract is void. We assume, without deciding, that the claim was preserved.
```

Observed candidates (abridged to ledger fields):

```json
[
  {"text":"the statute requires notice","proposition_type":"party proposition of law","asserter":{"role":"plaintiff","assumed":false},"validator":null,"disposition":"unresolved"},
  {"text":"the contract is void","proposition_type":"judicial proposition of law","asserter":{"role":"court","assumed":false},"validator":{"role":"court","mode":"ruled"},"disposition":"accepted"},
  {"text":"the claim was preserved","proposition_type":"arguendo assumption","asserter":{"role":"court","assumed":true},"validator":{"role":"court","mode":"declined"},"disposition":"assumed-arguendo"}
]
```

## Design decisions

- Candidate IDs use UUID5 over job ID plus exact content offsets, so lexicon and LLM suggestions
  for the same span share a stable identity.
- Content is the dependency complement subtree (`ccomp`, `xcomp`, or `acl`), with complementizer
  `that` and terminal punctuation excluded from the recorded source span.
- The lexicon is precision-first (roughly 55 judicial reporting lemmas plus explicit arguendo
  markers). Subject lemmas refine party/court roles; uncertain party frames default to law and
  remain unresolved.
- Citation edges use the existing substring-linking convention at confidence-policy parity:
  co-sentential Individual mention text binds to its individual ID with edge type `cites`.
- LLM assistance is optional, structured, span-bounded, deduplicated against deterministic
  candidates, and fully failure-tolerant. A keyless/no-local-model run remains functional.
- Default-off orchestration gates the proposition runner before executing or saving, preventing a
  no-op extra JobStore write and preserving the rollout's byte-neutral intent.
- SSE serializes the library model with `model_dump(mode="json")` and deduplicates by proposition
  ID, matching existing individual/property event behavior.
- Exporters were deliberately not changed; no proposition sections are added in U2.

## Simplification review

Three independent read-only passes covered reuse, quality, and efficiency. Applied: default-off
runner save gating, clearer SSE vocabulary, and removal of a redundant identity role map. Skipped
broader pre-existing orchestrator refactors and SSE cursor state because they would enlarge risk or
complicate list-replacement semantics. No reusable proposition-ID/dedup helper exists in the repo.
