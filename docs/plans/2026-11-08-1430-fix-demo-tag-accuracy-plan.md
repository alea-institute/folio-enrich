---
title: "fix: demo-tag accuracy pass (measure first)"
type: fix
status: completed
date: 2026-11-08
branch: session/1108-1406
requested_by: Damien (2026-11-08, "Yes, please do a demo-tag accuracy pass")
source_backlog: docs/plans/2026-11-08-1200-fix-court-opinion-demo-tags-plan.md ("Follow-up backlog")
---

# fix: demo-tag accuracy pass

## Why

The re-baked PROD demos still show wrong-looking tags ("Delaware" as the Lenape language, "NEPA" as
Nepali, "CEO" as Bananas, "Wilmington facility" as Jail). Damien approved a measure-first pass: build
a labeled eval set from the baked demos, measure false positives, fix the largest classes, re-bake,
then ship through DEV and PROD.

## Early diagnosis (from lineage in the baked demos)

The backlog guessed most bad tags came from the semantic ruler and one-word ruler homonyms. Lineage
says otherwise for most of them: the LLM supplied a sensible span and branch hint, and **resolution's
fuzzy recall fallback** mapped it to an unrelated concept. Those resolutions carry near-zero
sentence-vs-definition embedding similarity:

| Span (LLM branch hint) | Resolved to | Embedding sim |
|---|---|---|
| "CEO" (Actor / Player) | Bananas (Asset Type) | 0.00 |
| "SOP" (Legal Authorities) | Syriac (Language) | 0.00 |
| "NEPA" (Legal Authorities) | Nepali (Language) | 0.00 |
| "validation protocol" (Document / Artifact) | Electoral System | 0.00 |
| "Wilmington facility" (Location) | Jail (Asset Type) | 0.05 |
| "APA" (Legal Authorities) | Arapaho (Language) | 0.06 |
| "significantly affects" | Schizophrenia (Legal Entity) | 0.10 |

The embedding score is only blended 60/40 into confidence; nothing rejects a resolution the context
contradicts. Ruler homonyms ("Delaware" → Language) and semantic-ruler matches ("mg and 100" →
Myasthenia Gravis) are real but smaller classes.

## Units

- **U1 eval set (measurement):** a committed label file of (text, IRI) → correct/wrong verdicts
  (`backend/eval/demo_tags/labels.json`) and a stdlib scorer (`backend/scripts/demo_tag_eval.py`)
  that reports precision overall and per origin plus the false-positive and unlabeled lists.
  *Narrowed 2026-11-08:* the finer provenance classes in the baseline table (fork vs library path,
  embedding similarity, LLM branch hint) came from one-off analysis that re-ran the resolver against
  a loaded FOLIO; they are recorded here, not reproduced by committed code. Re-tuning the gate
  thresholds needs that analysis rebuilt as a script first. Labels come from LLM-assisted
  annotation, spot-checked by the orchestrator.
- **U2 fixes, largest false-positive class first:** each fix is deterministic, gated by a setting,
  and carries regression tests; candidates are set by the U1 numbers, not guessed.
- **U3 re-bake + re-measure:** `backend/scripts/replay_fix_demos.py`, then the scorer again;
  report before/after precision and every newly lost true positive.
- **U4 ship:** review, PR, CI, DEV (propositions-dev), PROD per the 2026-11-07 recipe, with receipts here.

## Keep

Every fix from the court-opinion plan ("excessive force" → Excessive Force Claim; U.S. Ct. App. - 7th
Circuit; no "non"/"III"). A fix may not lose more true positives than it removes false positives in
any class.

## Results

### Baseline (fc3c8fe demos, 1,536 unique (text, IRI) pairs, 4,704 tag occurrences)

Labels: `backend/eval/demo_tags/labels.json`, from six LLM labelers given span, context and
definition; 11 of 12 known-wrong tags came back wrong (Concussion passed: the concept fits, only its
branch looks odd). Treat single verdicts as noisy; class-level numbers are the signal.

| Class | Correct | Wrong | Unsure | Precision |
|---|---|---|---|---|
| All | 845 | 532 | 159 | 0.61 |
| LLM span, fork fallback | 176 | 355 | 73 | 0.33 |
| LLM span, library resolver | 87 | 22 | 12 | 0.80 |
| Ruler, multi-word | 307 | 11 | 15 | 0.97 |
| Ruler, single-word | 176 | 71 | 33 | 0.71 |
| Semantic ruler | 88 | 71 | 26 | 0.55 |
| Language branch (any origin) | 0 | 5 | 0 | 0.00 |

### Chosen fixes and their measured trade

- **Fork context gate:** drop a fork result when sentence-vs-definition similarity < 0.15, or
  < 0.30 without the LLM's branch hint agreeing. Grid search on the gold set: removes 197 wrong and
  31 correct items (6.4:1). The lost correct tags are mostly generic roots ("Chicago, Illinois" →
  Location, "compliance" → Compliance).
- **Delaware:** Location must beat Language; Language needs an explicit hint or the word "language".
- **Deictic courts:** "this Court" links only to the document's own court.

### After the fixes (replay `e3bbdf0`, embeddings active)

| Measure | Before | After |
|---|---|---|
| Precision, unique labeled pairs | 0.61 | 0.71 |
| Wrong tag occurrences | 1,491 | 989 (−34%) |
| Correct tag occurrences | 2,769 | 2,786 |
| Unique pairs: wrong / correct | 532 / 845 | 341 / 828 |

- **Removed:** 202 wrong and 22 unsure pairs, including every reported example (CEO → Bananas,
  NEPA → Nepali, SOP → Syriac, Wilmington facility → Jail, "This Court" → Family Court, and the 21
  wrong patent-demo tags such as "wherein" → Incest). "Delaware" and "State of Delaware" now tag the
  US state. "excessive force" → Excessive Force Claim is kept.
- **New pairs:** 29, labeled by the orchestrator (16 correct, 11 wrong, 2 unsure); several are
  multi-word ruler tags the StringMatch IRI-reuse fix unmasked ("requests for production",
  "protective order").
- **Lost true positives (33):** "21 CFR 211.68(a)" and "(b)" → U.S. Code of Federal Regulations;
  "arbitrary" → Arbitrary and Capricious; "Case No. 2024-CV-01847" → Docket Number; "cGMP
  compliance", "compliance deficiencies", "compliance provisions", "Data Integrity and Compliance
  With Drug CGMP" → Compliance; "cGMP violations" → Violation; "Chicago, Illinois", "Greenwich,
  Connecticut", "LA", "New York, NY", "Seattle, Washington" → Location; "compliance manual" → Manual;
  "conflict-of-interest disclosures" → Conflict of Interest; "expert testimony" → Expert; "FACTUAL
  ALLEGATIONS" → Factual Statement; "financial account information" → Financial Account; "impact
  assessment", "liability assessment" → Assessment; "individual", "individual misconduct" →
  Individual Person; "irreparable harm" → Injury; "judges" → Judge; "non-solicitation obligations" →
  Solicitation; "object" → Objector; "obligations of confidentiality" → Obligation; "reasonable
  attorneys' fees" → Attorney Fees; "surviving spouse" → Spouse; "Type A meeting" → Meeting;
  "valuation procedures" → Asset Valuation; "Wockhardt Ltd." → Limited Company. Mostly generic
  root or parent classes, as the grid search predicted. Every class removed far more wrong tags
  than correct ones.

### Individual class links (found in the browser check)

The Concepts tab still showed "Delaware" under LANGUAGE after the tag fixes. Individuals (OWL entities)
keep the class links baked from the original run, and replay only re-pointed their annotation ids. Replay
now mirrors the live linker:
- **Annotation-backed links:** re-derived from the surviving same-span annotation's top concept, or dropped.
- **Label-only links:** dropped when they named a concept the replay removed.
- **Change detection:** class-link changes count as demo changes.

The demos were replayed once from the original bake. Tag precision is unchanged (0.71). Links such as
Delaware → Lenape language, NEPA → Nepali, and Agreement → License (Agreement) are gone; Delaware links to
the US state. Two LLM-chosen label-only links to Family Court remain ("UNITED STATES DISTRICT COURT",
"The Court"). No tag ever backed them, so only an LLM re-bake can change them. The remaining LANGUAGE
entry is the generic word "language" → Language, a one-word ruler match left for the deferred one-word
class.

### Review (ce-code-review, 2026-11-08)

Verdict "Ready with fixes": no code defect survived; the two P1 items were this plan's missing
results and the narrowed U1, both closed above. Residual items kept as follow-ups:

- **Virtual branch hints:** `_branch_hints` keeps the literal "Document Metadata" hint, so such
  forks must clear 0.30 instead of 0.15. Expand hints through `VIRTUAL_BRANCH_TARGETS`.
- **Court coreference confidence:** coreference-linked courts now skip the 60/40 embedding blend.
- **Tests:** cover the Language filter on backup candidates and overridden gate thresholds.
- **Structure:** extract the Language/Location policy from `ResolutionStage.execute`, and split the
  fork drop out of `_apply_embedding_context_scores`.
- **DEV vs PROD:** DEV's image has no embeddings, so the fork gate runs on PROD only.

### Deferred classes (measured, no clean separator yet)

- **Semantic ruler:** raising its 0.80 threshold to 0.85 removes 64 wrong but 49 correct. Needs a
  different signal.
- **One-word ruler alt labels:** 158 correct vs 159 wrong occurrences; the wrong ones concentrate in a
  few generic alt labels ("party" → Legal Services Buyer ×69, "SOVEREIGN" → Monarch ×46) and section
  headings ("ARTICLE" → Article ×47). A targeted label-quality pass fits better than a rule.
