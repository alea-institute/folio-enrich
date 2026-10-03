---
title: Proposition System Phase B — zero-LLM extraction recall, benchmarked
type: feat
date: 2026-10-03
status: planned
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Proposition System Phase B — zero-LLM extraction recall, benchmarked

## Goal Capsule

- **Objective:** A reviewer opening a judicial opinion in annotation mode sees most of the opinion's propositions already pre-selected, instead of hand-adding 92% of them. A reproducible benchmark proves this on held-out text before anything about propositions reaches the public site.
- **Means:** extend the zero-LLM `EarlyPropositionStage` extractor beyond reporting-verb frames to assertion-level patterns, scored by an offline benchmark against the committed Palsgraf gold set.
- **Product authority:** Damien Riehl (annotator-taxonomist). This plan covers Phase B's extraction engine and its benchmark only. The public Propositions tab, LLM refinement (Phase C) and the gold-ladder annotation cycles are not active scope.
- **Open blockers:** none.
- **Stop conditions:** stop and report if a pattern change can only raise recall by changing the v0.3.0 schema or taxonomy (R10), or if held-out recall stalls below the Success Criteria after U5–U6. Report the numbers; do not tune against held-out text to close the gap.
- **Execution profile:** one branch (`feat/proposition-cycle-2`), units in order U1→U7. The agent implements, verifies and opens the PR. Merging follows the repo's standing authorization. No production deploy.

**Product Contract preservation:** Product Contract unchanged. The three Outstanding Questions deferred to planning are resolved in the Planning Contract (KTD2, KTD3, KTD5).

## Product Contract

### Summary

The Phase A lexicon finds attribution frames ("the plaintiff contends that…") but almost no direct judicial assertions, so it pre-selected 8 of Palsgraf's 104 gold propositions (recall proxy 0.077). This work adds assertion-level extraction (copular, modal, deontic and generic-rule sentences, plus quoted authority), makes it negation-safe, and builds an offline benchmark with a held-out split so the gain is measured rather than tuned into the gold set. The feature flag stays off by default throughout.

### Problem Frame

Cycle 1 falsified the Phase A assumption that roughly fifty reporting verbs cover most judicial propositions. Cardozo and Andrews assert law directly ("Negligence is…", "The risk reasonably to be perceived defines the duty…", "There must be…"). Reporting verbs cluster where the court reports others' speech, so the lexicon surfaced party contentions and arguendo markers but few holdings (`../folio-propositions/docs/cycle-1-palsgraf-learnings.md`). The Phase A exit record names this the Phase B critical risk and makes assertion-level patterns a Phase B design constraint (`../folio-propositions/docs/exit-record-phase-a.md`, condition 3).

Two further defects surfaced. Negated frames ("has no claim that X") produced candidates asserting X, inverting polarity. And the gold record's canonical text exists only in a local job file under the 30-day job sweep, so no one can re-score the gold today.

### Key Decisions

- **Engine and benchmark first; the public tab waits for evidence.** Phase B's settled intent also includes a user-facing Propositions tab. That ships only after this plan's benchmark clears its bar. (session-settled: user-approved — chosen over deploying the proposition work to production now: Damien wants it proven good before the public sees it.) Governs R11, R14.
- **Zero-LLM stays.** LLM refinement is Phase C. Phase B promotes the deterministic stage, per Phase A KTD3. Governs R12.
- **Measure on held-out text, not on what was tuned.** One AI-annotated opinion is a small, single-author-per-section gold set, and tuning patterns against it while reporting on it would overstate recall. Governs R3, R4.
- **Negation-safe without a schema change.** Damien deferred the `polarity` field pending more cycle evidence (2026-08-17; reconfirmed 2026-09-30). The extractor must not produce inverted candidates within the v0.3.0 schema. Governs R8.
- **No taxonomy or schema change.** Candidates use the v0.3.0 `WORKING_TAXONOMY` and existing fields only. Vocabulary changes happen between ladder cycles under Damien's authority (`../folio-propositions/docs/review-disposition-v2.0.md`). Governs R10.

### Requirements

**Benchmark**

- R1. One offline command scores the extractor against the committed proposition gold and reports recall, precision and F1, overall and per proposition type. It needs no network and no LLM.
- R2. The canonical text each gold record was annotated against is committed beside the gold. A check fails if any gold span's offsets no longer reproduce its recorded text.
- R3. The gold is split into a development portion (the Cardozo majority) and a held-out portion (the Andrews dissent). Pattern work is tuned only against development, and every report states both numbers separately.
- R4. Each future ladder opinion joins the held-out portion by default when its gold lands.
- R5. Scoring counts a candidate as a match when its span overlaps a gold span substantially. The report also shows exact-span matches, so boundary quality stays visible.
- R6. Benchmark reports are written as committed files. The Phase A lexicon (`phase-a-v1`) is recorded as the baseline.

**Extraction**

- R7. The extractor proposes court-asserted propositions expressed without reporting verbs: copular definitions and characterizations, modal and deontic statements of duty or permission, and generic rule statements.
- R8. A candidate's text never asserts the opposite of what the source sentence asserts. A negated assertion keeps its negation inside the span, or is not emitted.
- R9. Quoted or attributed treatise and precedent assertions are proposed as `cited-authority proposition` with a secondary-source or court asserter, as fits.
- R10. Every candidate's type, asserter role, validator mode and disposition come from the v0.3.0 vocabularies. Unknown cases fall back to the conservative existing defaults rather than new values.
- R11. Existing reporting-verb and arguendo frames keep working. Their precision on the development portion does not drop below the baseline.
- R12. Extraction stays deterministic and zero-LLM, using the single spaCy parse the stage already performs.
- R13. The lexicon version recorded in session and gold-export provenance changes with this work, so cycle metrics remain attributable to the extractor that produced them.

**Safety**

- R14. `proposition_extraction_enabled` stays off by default. The flag-off byte-neutral harness keeps passing unchanged.

### Acceptance Examples

- AE1. Covers R7. Given "The risk reasonably to be perceived defines the duty to be obeyed", the extractor proposes the sentence's assertion as a court proposition, though no reporting verb is present.
- AE2. Covers R8. Given "The plaintiff has no claim that the guard was negligent", no candidate's text reads "the guard was negligent" as an assertion. Either the span carries the negation or no candidate is produced.
- AE3. Covers R3, R6. When a pattern change raises development recall but lowers held-out recall, the report shows both moves, and the held-out number is the one quoted as the result.
- AE4. Covers R2. If someone edits the committed canonical text so one gold span shifts by a character, the gold-text check fails and names the span.

### Success Criteria

- Held-out recall reaches at least 0.50 with precision at least 0.60, against the 0.077 / 0.615 baseline. These thresholds are provisional, set by the agent, and Damien may adjust them. They gate Phase B's public-tab work, not this plan's merge.
- Development and held-out results are both reported, and the gap between them is small enough that tuning hasn't simply memorized the majority opinion. The plan sets the tolerance.

### Scope Boundaries

- Deferred to later Phase B work: the user-facing Propositions tab, thread-style rendering, and any production deploy of proposition features.
- Deferred to Phase C: LLM refinement, grounding-as-filter, near-miss capture.
- Not in scope: a `polarity` field, per-opinion validator stance, or any taxonomy revision. These are Damien's between-cycle decisions.
- Not in scope: annotating new ladder opinions or human review of cycle 1. That is Damien's parallel track. This plan only makes new gold slot into the held-out portion (R4).

### Dependencies / Assumptions

- Assumption: the cycle-1 gold, AI-annotated under delegation and not yet human-validated, is good enough to steer pattern work. Human review of cycle 1 or a human-annotated second opinion may later revise the numbers. The benchmark reruns cheaply when that happens.
- Assumption: *Palsgraf v. Long Island R.R. Co.*, 248 N.Y. 339 (1928), is in the public domain, so committing its text is unencumbered.
- Dependency: `folio-propositions` v0.3.0 stays pinned. No library release is needed.

<!-- ce-section: work-relationships -->
### How This Work Fits Together

This plan covers the extraction engine and benchmark slice of Phase B. The breakdown below is current understanding, not a committed roadmap.

- **Phase B public surface:** the Propositions tab and thread rendering. Depends on this plan's benchmark clearing its bar. Reuses the review workspace merged in PR #40.
- **Gold ladder cycle 2+:** Damien picks and annotates the next opinion. Can proceed independently of this plan. Enables a stronger held-out test via R4.
- **Phase C LLM refinement:** depends on Phase B. Its filter-vs-union test uses this plan's benchmark.

### Outstanding Questions

- Resolved in planning: the R5 matching rule (KTD2), the split encoding (KTD3) and the gap tolerance (KTD5).

## Planning Contract

### Key Technical Decisions

- KTD1. **Commit the canonical text as a plain `.txt` beside the gold, plus manifest pointers.** The text comes from job `6ae5e29d-728c-475d-875c-a4ece3d5d9ec` (31,920 characters). All 104 gold spans were verified on 2026-10-03 to reproduce their recorded text from it. The job store's 30-day sweep makes the job file an unsafe source of truth. Governs R2.
- KTD2. **Match by overlap coefficient ≥ 0.5, one-to-one.** A candidate matches a gold span when their character overlap is at least half the shorter span's length. Pairs are assigned greedily by largest overlap, so one candidate never credits two gold spans. Exact matches are counted separately. The threshold follows the repo's NER harness, which already uses overlap rather than equality (`backend/eval/metrics.py`), tightened to one-to-one because proposition spans are long and nest. Governs R5.
- KTD3. **Encode splits as character ranges in the manifest.** Palsgraf: development `[0, 13488)` (the majority), held-out `[13488, 31920)`, starting at "ANDREWS, J. (dissenting):". This gives 46 development and 58 held-out gold propositions. A manifest entry without `splits` is wholly held-out, which is how R4 is satisfied with no further code. Governs R3, R4.
- KTD4. **Precision counts every unmatched candidate as a false positive.** Cycle 1 recorded a complete full-text coverage pass, so the gold is exhaustive within each opinion. Candidates overlapping the blind segment (offsets 19912–20935) are scored the same way. Governs R1.
- KTD5. **Gap tolerance: held-out recall within 0.15 of development recall.** A wider gap is reported as a tuning-overfit warning in the report, not a failure. Governs Success Criteria.
- KTD6. **The server stamps the lexicon version.** A `LEXICON_VERSION` constant lives with the lexicon. Session creation fills `pre_selector.lexicon_version` when the client omits it, which today it always does (`frontend/index.html` sends none). This work bumps the version from `phase-a-v1` to `phase-b-v1`. Governs R13.
- KTD7. **Negation: widen to the governing clause, else drop.** When a complement or assertion sits under a negation (a `neg` dependent, or a negative determiner such as "no" or "never" on the frame), the span widens to the clause that carries the negation. Where widening would cross the sentence, the candidate is dropped. Governs R8.
- KTD8. **Assertion patterns are dependency-parse rules, not regexes.** They run on the stage's single spaCy parse (`app/services/nlp/spacy_singleton.py`) and live as named frames beside the reporting-verb table in `app/services/proposition/lexicon.py`. Each frame records which pattern fired, so the benchmark can attribute hits and misses per pattern. Governs R7, R9, R12.

### High-Level Technical Design

Directional only:

```text
gold/*.jsonl + gold/*.txt + manifest(splits)
        │
        ▼
eval/proposition_benchmark.py ── runs PropositionExtractor on each .txt (no pipeline, no LLM)
        │                       ── scores per split: recall, precision, F1, exact, per-type, per-pattern
        ▼
eval/reports/propositions/<lexicon_version>.json (+ printed table)
```

The benchmark builds a minimal in-memory `Job` carrying the canonical text and an empty individuals list, so it exercises the extractor exactly as the stage does, minus citation linking.

### Sequencing

U1 → U2 → U3 establish the measuring stick and the baseline before any extractor change. U4 → U5 → U6 change the extractor, each rerunning the benchmark on development. U7 records the final held-out result.

## Implementation Units

### U1. Commit gold canonical text with an integrity check

- **Goal:** make the Palsgraf gold re-scorable without the job store.
- **Requirements:** R2.
- **Files:** `backend/eval/gold/propositions/palsgraf-248-ny-339.txt` (new), `backend/eval/gold/propositions/manifest.json`, `backend/tests/test_proposition_gold_text.py` (new).
- **Approach:** export `result.canonical_text.full_text` byte-exact. Add `text_file` and `splits` (KTD3) to the Palsgraf manifest entry. `demo-smoke` gets its text too if its job is available; otherwise it is skipped by the benchmark with a printed note.
- **Test scenarios:** every exported annotation's offsets reproduce its `proposition.text` from the `.txt`; a deliberately shifted copy fails and names the span (AE4); split ranges cover the whole text without overlap; the counts per split are 46 and 58.
- **Verification:** `pytest tests/test_proposition_gold_text.py`.

### U2. Offline proposition benchmark

- **Goal:** one command that scores the extractor per split.
- **Requirements:** R1, R3, R4, R5, R6.
- **Dependencies:** U1.
- **Files:** `backend/eval/proposition_benchmark.py` (new), `backend/tests/test_proposition_benchmark.py` (new).
- **Approach:** pure scoring functions (matching per KTD2, precision per KTD4, gap warning per KTD5) separated from the CLI entry point (`python -m eval.proposition_benchmark [--write]`). Report fields: per split, the counts (gold, candidates, matched, exact), recall, precision, F1, per-type recall, per-pattern hits, and type agreement on matches. Follow the existing `eval/` module layout.
- **Test scenarios:** synthetic gold plus candidates covering: partial overlap at exactly 0.5 matches and at 0.49 does not; one candidate overlapping two gold spans credits one; an entry without `splits` is all held-out (R4); the overfit warning fires at a gap of 0.16 and not at 0.15; empty candidates yield recall 0 with no division error.
- **Verification:** `pytest tests/test_proposition_benchmark.py`, then a CLI run printing the Palsgraf table.

### U3. Baseline report and lexicon version stamping

- **Goal:** record where Phase A stands, and make future gold attributable.
- **Requirements:** R6, R13.
- **Dependencies:** U2.
- **Files:** `backend/eval/reports/propositions/phase-a-v1.json` (new), `backend/app/services/proposition/lexicon.py`, `backend/app/services/gold/store.py`, `backend/tests/test_gold_store.py`.
- **Approach:** run the benchmark on the unchanged extractor and commit the report as the baseline. Add `LEXICON_VERSION` and stamp it per KTD6.
- **Test scenarios:** a session created without `lexicon_version` records the current constant; a client-supplied value is preserved.
- **Verification:** the baseline report exists; `pytest tests/test_gold_store.py`.

### U4. Negation-safe candidates

- **Goal:** no candidate inverts its source's polarity.
- **Requirements:** R8, R11.
- **Dependencies:** U3.
- **Files:** `backend/app/services/proposition/extractor.py`, `backend/tests/test_proposition_stage.py`.
- **Approach:** per KTD7, applied to the existing reporting-verb path first; U5's patterns reuse the same guard.
- **Test scenarios:** AE2 ("The plaintiff has no claim that the guard was negligent"); "No human foresight would suggest that X" yields no bare "X"; a non-negated "The plaintiff contends that X" still yields "X"; the Palsgraf offsets 16109 and 29213 named in the cycle learnings no longer produce inverted text.
- **Verification:** unit tests pass, and development precision does not fall below the U3 baseline (R11).

### U5. Assertion-level court patterns

- **Goal:** raise recall on direct judicial assertions.
- **Requirements:** R7, R10, R12.
- **Dependencies:** U4.
- **Files:** `backend/app/services/proposition/lexicon.py`, `backend/app/services/proposition/extractor.py`, `backend/tests/test_proposition_stage.py`.
- **Approach:** named dependency frames per KTD8: copular characterization or definition (subject + "be" + attribute or complement), modal and deontic (must, shall, may not, cannot, is bound to, is liable, owes a duty), existential obligation ("There must be…"), and generic rules ("One who…", "If/where X, Y" with a general subject). Spans are clause-level, trimmed by the existing `_trim_span`. Default types are `Judicial Legal Conclusion` with a court asserter, `ruled` validator mode and `accepted` disposition. Inside the dissent, the existing dissent modeling applies (asserter name carries the dissenting judge; the type is unchanged). Tuning uses the development split only.
- **Test scenarios:** AE1; a pronoun-only copular clause ("It is so.") is not emitted; a modal inside a quotation is left to U6; each new frame has one positive and one negative fixture sentence.
- **Verification:** unit tests pass; the development benchmark rerun shows recall rising and precision holding.

### U6. Cited-authority propositions

- **Goal:** propose quoted treatise and precedent assertions.
- **Requirements:** R9, R10.
- **Dependencies:** U5.
- **Files:** `backend/app/services/proposition/extractor.py`, `backend/app/services/proposition/lexicon.py`, `backend/tests/test_proposition_stage.py`.
- **Approach:** quoted spans that make an assertion (they contain a finite verb) and sit next to a citation or attribution (a reporter citation pattern, "said", "J., in", or a treatise name) become `cited-authority proposition` with asserter `secondary_source`. Without such an anchor they fall back to `court`.
- **Test scenarios:** the Willes, J. negligence quotation in Palsgraf; a quoted single word or title is not emitted; an unattributed quotation does not become cited-authority.
- **Verification:** unit tests pass; development benchmark rerun.

### U7. Held-out result and documentation

- **Goal:** state the result honestly.
- **Requirements:** R3, R6, R14, Success Criteria.
- **Dependencies:** U6.
- **Files:** `backend/eval/reports/propositions/phase-b-v1.json` (new), `backend/eval/gold/propositions/README.md`.
- **Approach:** run the benchmark once more and commit the report. Document the benchmark command and the split rule in the gold README, and correct its blanket "human-reviewed" wording for the AI-annotated Palsgraf cycle, per the 2026-09-30 reconciliation.
- **Verification:** the report shows development and held-out results, with any overfit warning; the byte-neutral harness passes.

## Verification Contract

- Full suite: `cd backend && .venv/bin/python -m pytest tests/ -q` (the repo's default markers exclude slow/eval runs).
- Byte neutrality: `pytest tests/test_proposition_byte_neutral.py` passes unchanged (R14).
- Benchmark: `cd backend && .venv/bin/python -m eval.proposition_benchmark` prints both splits. `--write` produces the committed report.
- Success Criteria are judged from the held-out row of `phase-b-v1.json` against `phase-a-v1.json`.

## Definition of Done

- U1–U7 are complete with their tests passing, and the full suite and byte-neutral harness are green.
- Baseline and Phase B reports are committed, and the PR description quotes the held-out numbers, including any overfit warning.
- `proposition_extraction_enabled` still defaults to off. No production deploy happens.
- Abandoned patterns and experiment scaffolding are removed from the diff.
