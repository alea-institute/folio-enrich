---
title: "fix: Court Opinion demo tagging errors (root causes)"
type: fix
status: completed
date: 2026-11-08
branch: fix/court-opinion-demo-tags
requested_by: openlegalstandard.org FOLIO Tools showcase session, for Damien (2026-11-08)
---

# fix: Court Opinion demo tagging errors

## Why

The openlegalstandard.org FOLIO Tools showcase leads with Enrich's Court Opinion demo
(`?demo=opinion`, payload `frontend/demos/opinion.json`). Visitors see its tags in the video and
stills, and several tags are wrong. Fix the causes, not this one document, then re-bake the demo,
deploy, and re-record the website media.

## Where the fix lives

The matching core is the pinned `folio-resolve==0.4.0`. Every defect below is reachable from
folio-enrich's own adapter layer (`ConceptResolver`, `candidate_vetoed`, the label/lemma index,
StringMatch, the frontend), and this session's GitHub scope covers only folio-enrich. So the fixes
land here, at the boundary, without forking library code. One finding belongs upstream and is filed
as a follow-up: `PlaceNameGate.evaluate` exempts only an exact *preferred*-label match (item 1).

## Diagnosis (every wrong IRI is deterministic)

The LLM supplies only span text and a branch hint (`metadata.llm_concepts`); IRIs come from
deterministic resolution. So `scripts/replay_fix_demos.py` can re-bake without Gemini.

| # | Symptom | Root cause |
|---|---------|------------|
| 1 | "UNITED STATES COURT OF APPEALS FOR THE SEVENTH CIRCUIT" → D.C. Court of Appeals | `LabelResolver` scores the exact alt label "Court of Appeals for the Seventh Circuit" at 100, then `candidate_vetoed` drops it: the place gate (Governmental Body branch) exempts only a query equal to the *preferred* label "U.S. Ct. App. - 7th Circuit". The fuzzy fork fallback then picks D.C. Court of Appeals. Same veto kills "Central District of Illinois" → C.D. Illinois. |
| 2 | "United States District Court for the Central District of Illinois" → State Court | No canonical-form lookup for federal court names; falls to fuzzy fork search. |
| 3 | "district court" → Texas District Court | `LabelResolver` fuzzy-scores "Texas District Court" 95; nothing stops a generic court noun from latching onto a jurisdiction-specific court whose jurisdiction the text never names. |
| 4 | "non" → Non-Billable; "call" → Military Draft | Lemma index takes `doc[0].lemma_`; spaCy splits "Non-Billable"/"Call-Up" at the hyphen, so the first fragment becomes a match key. "civ" (from "CIVS") is a related too-short lemma. |
| 5 | "III" → Contact Name Suffix | Roman-numeral section enumerator ("III. ANALYSIS") matches the label "III". |
| 6 | "Monell v. Department of Social Services" → Services Agreement Practice | Case caption sent to fuzzy fallback (score 0.38); nested "Social Services" → Social Assistance Industry also tagged. |
| 7 | "domestic disturbance call" → Domestic Partner | Fuzzy fallback accepted at score 0.35; no floor. |
| 8 | Rejected "WOOD"/"grant"/"call" still drawn; "Show Uncertain" off hides nothing | `showUncertain` is assigned but never read. Pipeline-rejected single-word alt-label matches (conf 0.33-0.35) are kept for strikethrough. |
| 9 | Metadata "Resolved Concepts 58" vs Concepts "62 unique concepts" | Metadata counts `resolved_concepts` entries; Concepts tab counts unique IRIs over all annotations, rejected included. |
| 10 | Popover × titled "Remove this tag"; Escape doesn't close | One click deletes; no Escape handler on the concept tooltip. |

## Units

- **U1 resolver (backend, `app/services/folio/{search,resolver}.py`, new `court_names.py`,
  `resolution_stage.py`):** exact-any-label exemption in the place gate; federal court-name
  canonicalizer (circuits incl. bare "Seventh Circuit"/"7th Cir.", district and bankruptcy courts by
  district); jurisdiction-specificity guard for court/forum candidates; case-caption guard (no
  fuzzy resolution); fuzzy-fallback score floor (setting); generic court noun → the document's
  single matching specific court, else unresolved.
- **U2 ruler/StringMatch (backend, `folio_service.py`, `entity_ruler_stage.py`,
  `string_match_stage.py`, `scripts/replay_fix_demos.py`):** head-final hyphen lemma + minimum lemma
  length, cache-version bump; Roman-numeral enumerator guard; drop fragments nested inside a
  confirmed court span or a case-caption individual; drop pipeline-rejected single-word
  alternative matches; replay change detection on any concept IRI change.
- **U3 frontend (`frontend/index.html`):** working Show Uncertain filter (rejected + low
  confidence); one shared unique-concept count for both tabs; popover closes on Escape and ×;
  removal behind an explicit two-step "Remove tag" control.
- **U4 re-bake + ship:** replay demos, inspect diffs, PR, merge, PROD deploy per the 2026-11-07
  recipe, live checks.
- **U5 website media:** `node scripts/demos/capture.mjs enrich` in openlegalstandard.org,
  path-limited commit of media only (+ handoff note if captions drift).

Each unit carries regression tests for its items.

## Keep

"excessive force" → Excessive Force Claim with its parents must not change.

## Verification

- Backend suite green; new regression tests red before / green after.
- Replay report: before/after per-span table for `opinion`, and changed-span review for every
  other demo the replay rewrites.
- Browser: `?demo=opinion` screenshots (tags, toggle, popover Escape, counts) local and PROD.

## What the all-demo replay taught us (2026-11-08)

Replaying all 22 demos after U1-U3, then diffing confirmed tags per demo, exposed regressions the
opinion demo alone could not show. Each got its own fix and test:

- **One-word homonym alt labels.** Exempting *every* exact label from the place gate let "Florida"
  (an alternative label of Florida, Department of Uruguay), "Georgia", "District", and "LA" through.
  The exemption now covers only the preferred label and multi-word alternative/hidden labels.
- **Same-branch homonyms from the ruler.** The ruler emits every concept that carries a label. At HEAD,
  the resolver's text-only cache returned the first concept's resolution for all of them, which hid
  the homonyms by accident. Keying explicit-IRI lookups by IRI (needed for coreference) exposed them.
  Resolution now groups same-text, same-branch candidates and keeps a unique exact match: rdfs label
  first, then skos prefLabel (both "Florida" concepts carry the skos label "Florida"; only the US state
  carries the rdfs label).
- **Bluebook abbreviations.** "S.D. Fla." now canonicalizes to U.S. District Court - S.D. Florida.

## Follow-ups (not in this change)

- **Semantic ruler precision.** The embedding ruler is a separate, pre-existing noise source in every
  demo (253 confirmed semantic tags; e.g. "mg and 100" → Myasthenia Gravis, "Maria Torres" → Maria
  Trinidad Sanchez). Context similarity does not separate good from bad ("fact witnesses" → Fact
  Witness is correct at 0.09), so a threshold needs an eval set, not a guess. In the opinion demo it
  surfaces "disturbance call" → Disorderly Conduct, previously masked by the overlapping LLM span.
- **Wrong-to-wrong fuzzy churn.** Some low-quality fuzzy matches changed but stayed wrong
  ("process validation" Poultry Processing → Process Server; "District" DC Courts → Lawyer).
- **Upstream.** `folio_resolve.PlaceNameGate.evaluate` exempts only the preferred label; the adapter
  now passes the multi-word exemption. Worth upstreaming as an optional `labels` argument.
- **Packaging.** `sentence-transformers` is still absent from `pyproject.toml`/`uv.lock`; the replay
  needs it whenever the label set changes (as here).

## PROD deploy receipt (2026-11-08, `0e50843`)

- **Shipped:** PR #70 merged as `0e50843` after green CI and an independent review (two P2 findings fixed:
  the Roman guard dropped acronyms such as "LLC."; tag removal wiped the POS layer).
- **Caches:** the FOLIO and Canon v2 lemma caches and both new label-embedding caches were built locally
  under the same OWL hashes, copied ahead of restart, and checked by sha256. Startup loaded them with no
  re-encode.
- **Switch:** a dated `enrich-backup-<ts>-pre0e50843` holds HEAD (`29846fd`) and `.env`; `git merge --ff-only`;
  no dependency changes; smoke import passed; restart reached `/health` 200 in 15 s. Mapper, OntoKit
  (api, web) and Caddy stayed active.
- **Live checks:** `?demo=opinion` in a browser shows U.S. Ct. App. - 7th Circuit and U.S. District Court -
  C.D. Illinois ("district court" links to it), no "non"/"III"/rejected tags, 37 unique concepts on both
  tabs, Escape closes the popover, 0 page errors. A fresh API job tags "COURT OF APPEALS FOR THE SEVENTH
  CIRCUIT" correctly and leaves "III." untagged.
- **Rollback:** `git checkout 29846fd` and restart (the old v1 caches remain on disk).
- **Website:** openlegalstandard.org `feat/folio-tools-showcase` commit `685eb23` re-records the hub
  Enrich media; proposed caption text for still 3 is in that repo's
  `docs/handoffs/2026-11-08-enrich-demo-rerecorded.md`. Still 3's counts were updated to 37/9 there
  (`21a868b`).

## Follow-up backlog: wrong-looking tags in the re-baked PROD demos

Reported 2026-11-08 by the openlegalstandard.org session while recording role-page clips. None appears
on a clip's final frame. Most look like the semantic-ruler and homonym classes above: a one-word label
or a branch-blind match with no context check. Triage these with an eval set before tuning.

- **Cross-demo:** "Delaware" tagged as a Language (the Lenape language), in contract, merger, lease,
  and advice_regulatory. A Location/Language homonym; same family as the "Florida" fix.
- **advice_regulatory:** "Office of Regulatory Affairs" → OMB's Office of Information and Regulatory
  Affairs; Motion for Observation on Cross-Examination ×19; Chronic Heart Failure and Myasthenia Gravis
  as Legal Entity; Jail ×5 and Bananas as Asset Type; Syriac as Language; Data Poisoning; Electoral
  System; Ejectment.
- **opinion:** Concussion ×2 as Legal Entity; Residence as Actor/Player; Ethics Claim (in addition to
  "disturbance call" → Disorderly Conduct).
- **merger:** Alexander ×2 as Governmental Body; Alford Plea; Freedom of Religion; Bona Fide
  Occupational Qualification; Jury ×2.
- **lease:** "earlier termination" (security-deposit text) → Early Termination Clause; Grandparent ×3;
  Patent Assets; Associational Discrimination Claim; Time Records - Bankruptcy.
- **settlement:** Santiago Rodriguez as Location; Family Court; Clinical Trial; Futures - Assets.
- **appellate:** Schizophrenia ×2 as Legal Entity; Nepali ×4 and Arapaho as Language; Family Court ×4;
  Reverse Mortgage Foreclosure; Wild Animal.
