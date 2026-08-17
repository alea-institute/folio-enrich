# Task U2 — EarlyPropositionStage, lexicon, and task registration (folio-enrich)

You are implementing unit U2 of the Proposition System Phase A plan in the folio-enrich repo (branch `feat/proposition-system-phase-a`). Goal: the backend pre-selects candidate proposition spans in the parallel pipeline phase, **byte-neutral when flagged off** (the default).

## Hard constraints

- **No network. No git commands.** Leave the tree uncommitted.
- Venv: `backend/.venv/`. Run tests as `cd backend && .venv/bin/python -m pytest tests/<file> -q`. The venv already has `folio-propositions==0.1.0` installed (`from folio_propositions import Proposition, ActorRef, AdjudicatorRef, CitationEdge, Disposition, ...`).
- **Do NOT touch** `.planning/`, `AGENTS.md`, `.codex/`, `docs/plans/`, or any exporter other than what byte-neutral proof requires (exporters gain NO propositions sections in this unit — that is later work).
- **Final report** → `.codex-task/U2-report.md`: summary; full changed-file list; verification evidence (byte-neutral baseline built first and observed green pre-implementation, red/green sequence for extraction tests, final test output tails); design decisions.

## Sequencing (mandatory): byte-neutrality FIRST

Before writing ANY pipeline/stage/model code:

1. Author `backend/tests/test_proposition_byte_neutral.py` — a pipeline-output baseline harness (a new thing; `TestFolioByteNeutral` tests prompt strings, not pipeline output). Design:
   - Run the deterministic, keyless pipeline (no LLM providers configured) on one or two small fixed input texts. Study `backend/eval/synthetic_runner.py` (campaign U10a) for the existing deterministic-run recipe — reuse its approach to seeding/config so output is reproducible run-to-run (deterministic IDs; if the pipeline emits random UUIDs, canonicalize them in the harness the way the eval runner does, or via a stable id-substitution pass).
   - Capture the byte-neutral surface: (a) every export format's bytes for the job (use the existing exporter registry), (b) the full SSE event sequence (drive `backend/app/services/streaming/sse.py`'s generator to completion for the finished job), (c) the job/result JSON.
   - Baseline mode: generate fixtures into `backend/tests/fixtures/proposition_baseline/` (small — trim inputs so fixtures stay a few KB) with a regeneration entry point (e.g. `python -m tests... --regen` or a pytest marker/env var).
   - Assertion mode (the actual test): regenerate live output and compare — exports and SSE **byte-identical** to fixtures; job JSON identical **except** an added `propositions` key whose value is `[]` (before your implementation exists, assert either exact identity or the one-key diff, so the same test is valid pre- and post-change).
2. **Generate the fixtures and run the test on the pristine tree NOW** — it must pass before you change anything (this is the characterization baseline). Run it twice to prove run-to-run determinism. Record the output in your report.
3. Only then implement the stage. Re-run the byte-neutral test after implementation with `proposition_extraction_enabled` at its default (False): exports + SSE must still match the fixtures byte-for-byte; the job JSON diff must be exactly the added empty `propositions` list.

## Implementation

Follow the existing `property`/`triple` patterns throughout — read them first:
- `backend/app/pipeline/orchestrator.py`: `LLM_TASKS` (line ~31), `_TASK_FIELD_MAP`, `TaskLLMs`, `PipelineConfig` (~82-92), `build_pipeline_config` (~125+), the parallel `run_*` closures (~454-495).
- `backend/app/pipeline/stages/triple_stage.py` (~line 28): flag check inside `execute()`.
- `backend/app/pipeline/stages/property_stage.py` + `backend/app/services/property/` for service layout.
- `backend/app/pipeline/stages/dependency_stage.py`: the substring linker (confidence 0.8) used to bind spans to already-extracted Individuals.
- `backend/app/services/nlp/spacy_singleton.py`: shared spaCy model.
- `backend/app/services/streaming/sse.py` (~107-125): the property_added emission loop.
- `backend/app/services/ollama/manager.py`: `TASK_TIER_MAP` for tier registration.

### New files

- `backend/app/services/proposition/__init__.py`
- `backend/app/services/proposition/lexicon.py` — a curated ~50-entry reporting-verb / discourse-marker lexicon for judicial prose. Each entry: lemma (e.g. contend, argue, assert, allege, maintain, claim, urge, concede, stipulate, hold, conclude, find, rule, determine, reason, note, observe, assume, presume, acknowledge, admit, deny, dispute, contest, object, testify, aver, submit, insist, suggest, counter, reply, respond, move, request, petition, appeal, affirm, reverse, remand, vacate, overrule, sustain, grant, deny(motion), declare, opine, emphasize, reiterate, caution, agree, disagree...) mapped to: proposition-type guess, asserter-role guess (party vs. court vs. secondary_source), and disposition guess. Include discourse markers for arguendo ("assuming, without deciding", "we assume, arguendo", "even if", "assuming arguendo") mapped to `arguendo assumption` / disposition `assumed-arguendo`. Curate for precision; tuning comes later from provenance data.
- `backend/app/services/proposition/extractor.py` — the zero-LLM extraction core: sentence-level dependency parse (shared spaCy singleton); a lexicon frame-verb hit classifies type + asserter role; the **content span is the reporting verb's complement subtree** (`ccomp`/`xcomp`/`acl` children) using the dependency parser's existing subtree-span helpers (see `app/services/dependency/parser.py`); subject of the frame verb refines the asserter guess (we/court → court; plaintiff/defendant/party names → party roles). Co-occurring eyecite-extracted Individuals in the same sentence attach as `CitationEdge` candidates (edge_type `cites`, bound by individual id) via the substring-linker pattern. Emit `folio_propositions.Proposition` objects with deterministic ids (uuid5 over job id + span offsets, mirroring the demo-id precedent) and sensible ledger guesses:
  - party-verb frames → `party proposition of law`/`...of fact` (default law when uncertain), asserter party-role, validator None, disposition `unresolved` (open position until adjudicated)
  - court-holding frames (hold/conclude/rule...) → `judicial proposition of law`, asserter court, validator court (mode ruled), disposition `accepted`
  - arguendo markers → `arguendo assumption`, asserter court (assumed=True), validator court (mode declined), disposition `assumed-arguendo`
  - stipulation verbs → `stipulation`, asserter both_parties, validator None, disposition `accepted`
- `backend/app/pipeline/stages/proposition_stage.py` — `EarlyPropositionStage(PipelineStage)`, name `early_proposition`, parallel-phase; first line of `execute()` returns the job untouched unless `settings.proposition_extraction_enabled`; optional LLM assist: when an LLM for task `proposition` is configured, run an assist pass proposing additional candidate spans/fields (merge + dedupe with lexicon candidates; lexicon-only MUST work with no key and no local model). Follow the existing LLM-stage prompt/JSON-parse conventions used by the property/individual stages; degrade gracefully on any LLM failure.
- `backend/tests/test_proposition_stage.py`, `backend/tests/test_proposition_byte_neutral.py`.

### Wiring changes

- `backend/app/config.py`: `proposition_extraction_enabled: bool = False` (byte-neutral off by default) + per-task LLM settings for `proposition` mirroring the property task's settings fields.
- `backend/app/pipeline/orchestrator.py`: add `"proposition"` to `LLM_TASKS`; `TaskLLMs.proposition`; `PipelineConfig.early_proposition`; construct `EarlyPropositionStage` in `build_pipeline_config`; a `run_early_proposition` parallel closure alongside the others.
- `backend/app/models/job.py`: `propositions: list[Proposition] = Field(default_factory=list)` on `JobResult`, imported from `folio_propositions` (this is the R9 requirement — enrich consumes the library models).
- `backend/app/services/streaming/sse.py`: emit `proposition_added` once per proposition (dedup by id, mirroring the property loop ~107-125); include the ledger fields the frontend will need (id, span, proposition_type, asserter, validator, disposition, provenance-free — serialize via `model_dump(mode="json")`).
- `backend/app/services/ollama/manager.py`: register `proposition` in `TASK_TIER_MAP` (complex tier, like individual/property).
- Check for any exhaustive task-name/field-map tests (e.g. `tests/test_agents_ratchet.py`-style completeness tests over LLM_TASKS/TaskLLMs) and update them.

### Test scenarios (`test_proposition_stage.py`) — author before the implementation where practical; observe red, then green

- Flag off (default): stage returns job unchanged; `JobResult.propositions == []`.
- "Plaintiff contends the statute requires notice" → one candidate: `party proposition of law`, asserter role plaintiff/party, content span = the complement clause ("the statute requires notice").
- "We hold that the contract is void." → `judicial proposition of law`, asserter court.
- "We assume, without deciding, that the claim was preserved." → arguendo: asserter court (assumed=True), validator mode declined, disposition `assumed-arguendo`.
- A sentence with no reporting verb → no candidate.
- Keyless + no local model: lexicon-only pre-selection still produces candidates (no LLM configured; stage must not raise).
- LLM assist configured: assist pass invoked under the `proposition` task (mock the provider; assert task routing + provider override env respected, mirroring existing per-task override tests).
- SSE emits `proposition_added` exactly once per proposition id across repeated polls.

## Verification before writing your report

1. `cd backend && .venv/bin/python -m pytest tests/test_proposition_byte_neutral.py tests/test_proposition_stage.py -q` — green.
2. Run the neighboring suites you touched wiring for: `tests/` files covering orchestrator config, SSE, job models, config (find them with grep; run those files). Full-suite run is the orchestrator's job afterwards — do not run the entire suite if it exceeds your time budget, but DO run every test file whose subject you edited.
3. A quick flag-on demonstration: a short script or test that runs the extractor on two or three sentences of judicial prose and prints the resulting Proposition list — include the output in the report.
