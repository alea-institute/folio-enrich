---
title: Proposition System Phase B — zero-LLM extraction recall, benchmarked
type: feat
date: 2026-10-03
status: requirements
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

- Deferred to Planning: the overlap threshold and matching rule for R5.
- Deferred to Planning: how the development/held-out boundary is encoded, by character offset or by section marker.
- Deferred to Planning: the dev/held-out gap tolerance named in Success Criteria.
