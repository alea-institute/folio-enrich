---
title: Canon Law-and-Morals Overlap and Dense Canon Demos - Plan
type: feat
date: 2026-11-04
topic: canon-law-morals-overlap
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Canon Law-and-Morals Overlap and Dense Canon Demos - Plan

## Goal Capsule

- **Objective:** Visitors, funders, and ontology people can watch any text enriched against FOLIO and the Catholic Semantic Canon together and see, per document, how much of its law, ethics, and moral vocabulary the two ontologies share. A new set of dense Canon demos shows the Canon's breadth at the same tag density as FOLIO's rich demos.
- **Product authority:** This plan owns the overlap ("both") mode, the identifier-based Venn, the moral-to-legal bridges, the overlap demos, and the dense Canon breadth demos. The divergence report for FOLIO/Canon cross-pollination is context only (see Scope Boundaries).
- **Open blockers:** None.

---

## Product Contract

### Summary

Add an "Enrich against both" mode that enriches a text once against the union of FOLIO and the Canon. It labels every tag as shared, Canon-only, or FOLIO-only, using the identifiers the two ontologies already share. A side panel shows the document's overlap percentage and curated moral-to-legal bridges. Ship 4–5 overlap demos from public-domain moral and religious texts, plus 2–3 dense Canon breadth demos, some real and some synthetic.

### Problem Frame

The Canon descends from FOLIO. Of its 14,972 labeled classes, 14,407 reuse a FOLIO local identifier under a different base IRI. About 565 classes are Canon-only, and FOLIO holds about 3,900 classes the Canon lacks. Damien leads both projects and will keep moving concepts between them. As the Canon adds faith-based concepts, the shared share of the whole will fall.

Nothing in the app shows this relationship today. Each job enriches against one ontology, no FOLIO↔Canon crosswalk exists, and the two exemplar pickers are separate. A naive demo that tags "murder" in both ontologies would only prove inheritance, and an ontology-literate funder would notice. The real moral-law link runs from Canon-native concepts such as "Commandment 07: You shall not steal." to FOLIO's legal concepts (Larceny, Fraud). No identifier joins those two sides.

The current Canon demos also look thin next to FOLIO's. They score 12–27 concept tags per 100 words, against 34–44 for FOLIO's `rich_*` demos.

### Key Decisions

- **Shared identity comes from the shared local identifier, not from labels.** Two classes that carry the same local identifier count as the same concept. Label matching would mis-map 659 Canon labels that match more than one FOLIO class, and the identifier join needs no stored table for the ~14,400 shared concepts. Governs R1, R2. (session-settled: user-directed — chosen over label-matching and a stored generated crosswalk: the Canon is a FOLIO fork with identical identifiers, and Damien will keep cross-pollinating, so the system should recognize the Venn directly and avoid duplicate work.)
- **One union run, not two runs.** The "both" mode enriches once against shared + Canon-only + FOLIO-only. That roughly halves cost and gives the text one consistent disambiguation, and it keeps FOLIO-only legal concepts that a Canon-only projection would lose. Governs R3, R4. (session-settled: user-approved — chosen over two independent runs joined by identifier and over a single Canon run projected onto FOLIO: Damien asked for whichever serves both today's high overlap and tomorrow's lower overlap; the union run stays one run as the Canon grows.)
- **Overlap means concept-level overlap, with shared vocabulary as the headline.** The headline shows how much vocabulary the two ontologies share. Curated moral-to-legal bridges form a secondary layer. Governs R6, R8. (session-settled: user-directed — chosen over leading with the moral-to-legal bridge and over presenting the ontologies as independent: shared vocabulary is itself the law-and-morals story.)
- **The headline number is per document, not global.** The global shared share will fall as the Canon grows. A theft or perjury passage keeps a high per-document score however large the Canon gets. Governs R6.
- **Layout: one reading surface with layered tags and an overlap side panel.** This is option B of the four sketched layouts. Governs R5, R6. (session-settled: user-directed — chosen over side-by-side twin panes, a three-column bridge board, and a toggle on the existing view.)
- **Live from day one.** The "both" mode runs on pasted text, not only on baked demos. Governs R3. (session-settled: user-directed — chosen over demos-only and demos-first-live-later.)
- **Bridges get model review; Damien's review is optional and never blocks.** Several cheap model passes draft and check each bridge. Governs R9, R10. (session-settled: user-directed — chosen over requiring Damien's or a CatholicOS maintainer's sign-off: limit his human work.)
- **Breadth demos aim at tag density.** Some breadth texts are real Catholic texts and some are synthetic, all at FOLIO's rich-demo density. Governs R13, R14. (session-settled: user-directed — chosen over branch-only, item-type-only, or subject-variety goals: "many tags per sentence and paragraph.")
- **Synthetic texts carry no badge.** Their description line says they are synthetic. Governs R15. (session-settled: user-directed — chosen over a visible "Synthetic" badge.)
- **Single-ontology jobs stay strict.** Today's no-cross-ontology-leakage rule keeps holding for FOLIO-only and Canon-only jobs. Only "both" jobs carry both namespaces. Governs R4, R12.

### Requirements

**Venn recognition**

- R1. The system classifies every concept in the two enabled ontologies into one region: shared (same local identifier in both), Canon-only, or FOLIO-only. It derives the regions from the pinned ontology versions, with no hand-maintained mapping for shared concepts.
- R2. A shared pair whose label or definition differs between the ontologies is marked "shared, drifted" rather than plain shared. Today 12 pairs share an identifier but differ in label.

**"Both" enrichment**

- R3. A visitor can choose "Enrich against both" for any text, live or baked. It is an opt-in choice beside today's FOLIO and Canon options, and FOLIO stays the default.
- R4. A "both" run enriches the text once against the union of the two ontologies, and each resulting tag carries its region from R1. FOLIO-only and Canon-only jobs behave exactly as they do today.
- R5. The results view shows one copy of the text, with each tagged span marked as FOLIO-only, Canon-only, or shared. Drifted pairs (R2) are visually distinguishable from plain shared tags.
- R6. A side panel shows this document's overlap: the share of tagged concepts that are shared, plus counts per region and the moral-to-legal bridges found in the text.
- R7. A shared concept's detail shows both IRIs and both branch paths, because a shared concept can sit under different parents in each ontology.

**Moral-to-legal bridges**

- R8. A curated set of bridges links Canon-only moral concepts to FOLIO legal concepts. Each bridge carries a match type (close or related) and a one-line rationale. The first set covers the Ten Commandments and the main sins against justice (usury, detraction, calumny, restitution), about 40–60 bridges.
- R9. Several independent, cheap model passes draft and cross-check every bridge. A bridge ships only when the passes agree. Damien's review is optional and never blocks shipping.
- R10. Each bridge records how it was reviewed (model passes only, or Damien), and that status appears in the bridge's detail.
- R11. When the pinned Canon version changes, its new Canon-only concepts are queued for a model bridge pass, so the bridge set keeps pace as the Canon grows.

**Exports**

- R12. Exports of a "both" job include both IRIs for shared concepts, each tag's region, and the bridges found in the text. Exports of single-ontology jobs are unchanged.

**Demos**

- R13. Ship 4–5 overlap demos baked in "both" mode. Their texts come from public-domain sources: the Catholic Encyclopedia (1907–14), Aquinas's Summa Theologiae II-II (1920s English Dominican translation), the Decalogue and Mosaic law (Douay-Rheims), and the Baltimore Catechism. Each passage is license-verified before it is committed.
- R14. Ship 2–3 dense Canon breadth demos, some real Catholic texts and some synthetic. Each reaches at least 35 concept tags per 100 words. Together they exercise all 7 Canon roots and every enrichment item type (concepts, individuals, properties, triples).
- R15. A synthetic demo says "synthetic" in its description line, and its picker button gets no badge.
- R16. Overlap demos appear in both the FOLIO and Canon exemplar pickers under a "Law & Morals" group. Opening one, by picker or deep link, always loads it in "both" mode, whatever ontology the URL names.

### Key Flows

- F1. Live overlap run
  - **Trigger:** A visitor pastes a text and chooses "Enrich against both."
  - **Steps:** The text is enriched once against the union, then the tags render on one surface by region. The side panel fills with the document's overlap share, the region counts, and any bridges. Clicking a shared tag shows both IRIs and both branch paths.
  - **Outcome:** The visitor sees how much of this text's vocabulary law and morals share.
  - **Covered by:** R3–R7
- F2. Canon update
  - **Trigger:** The pinned Canon version moves forward.
  - **Steps:** The regions are recomputed from the new pin, and drifted pairs are re-flagged. New Canon-only concepts queue for a model bridge pass. Bridges that pass agreement join the set, marked model-reviewed.
  - **Outcome:** The Venn and bridges stay current without Damien's time.
  - **Covered by:** R1, R2, R9–R11

### Acceptance Examples

- AE1. **Covers R1, R5.** Given the text "Thou shalt not steal," when it runs in "both" mode, then "steal" or its theft concept renders as shared if the concept's local identifier exists in both ontologies, and as FOLIO-only or Canon-only otherwise.
- AE2. **Covers R2.** Given one of the 12 pairs that share an identifier but differ in label, when it is tagged, then it renders as "shared, drifted" and its detail shows both labels.
- AE3. **Covers R6, R8.** Given an Aquinas passage on theft and robbery, when it runs in "both" mode, then the side panel lists the "Commandment 07" bridge to Larceny and Fraud, along with the document's overlap share.
- AE4. **Covers R3, R8.** Given pasted text whose moral concept has no curated bridge, when it runs in "both" mode, then that concept appears as Canon-only and no bridge is invented for it.
- AE5. **Covers R4, R12.** Given a Canon-only job, when it is exported, then the export still contains no FOLIO IRIs, exactly as today.
- AE6. **Covers R16.** Given a deep link to an overlap demo with `?ontology=folio`, when the page loads, then the demo opens in "both" mode.

### Success Criteria

- **Density bar:** every new breadth demo scores at least 35 concept tags per 100 words, measured the way this plan measured the current demos: annotations divided by the normalized text's word count.
- **Overlap readout:** every overlap demo shows a per-document overlap share and at least one moral-to-legal bridge.
- **Self-explaining:** a first-time visitor who opens an overlap demo can tell, without a guide, which tags come from law, which from morals, and which from both.

### Scope Boundaries

- **Deferred:** the divergence report for cross-pollination. It would list drifted pairs, diverged definitions, Canon-native concepts FOLIO might adopt, and FOLIO additions since the fork that the Canon lacks. It grows more useful as the Canon diverges, and it would reuse R1's region computation.
- **Deferred:** publishing the bridges upstream to CatholicOS as formal mapping statements.
- **Deferred:** overlap demos from other religious or ethical traditions.
- **Deferred:** "both" mode for ontologies other than FOLIO and the Canon.
- **Not in scope:** changing FOLIO's default status, or the strictness of single-ontology jobs and exports.
- **Not in scope:** Damien's mandatory review of bridges or demo texts.

### Dependencies / Assumptions

- **Identifiers keep meaning:** future cross-pollination keeps a moved concept's local identifier, so a concept shared between the projects keeps reading as shared.
- **Visitor pays live:** live "both" runs use the visitor's own LLM key under PROD's BYOK rule, like any other live run.
- **Synthetic mix:** about half the breadth demos are synthetic; planning picks the exact split against the density bar.
- **Public domain:** the listed sources are US public domain (published before 1929), and each excerpt is verified before commit (R13).

### Outstanding Questions

**Deferred to Planning**

- How the union run builds its concept index and embeddings, including whether shared concepts reuse one vector.
- Which branch taxonomy drives the "both" mode's branch colors and filters, given that R7 shows both paths in detail.
- How the model bridge passes are composed, how many there are, which models they use, and what counts as agreement for R9.
- How R11's queue surfaces its work: a script run on pin bump, or a check that fails until bridges are evaluated.
- Whether the existing 4 Canon demos get re-baked toward the density bar, or stay as they are beside the new breadth demos.

### Sources / Research

- **Current demos:** `frontend/demos/canon_samples.js`, `backend/scripts/canon_exemplars.py` (4 slugs and metadata), `backend/scripts/demo_documents.py`, and `backend/scripts/generate_demos.py` (per-ontology demo paths).
- **Single-ontology jobs:** `backend/app/api/routes/enrich.py` (the `ontology` request field), `backend/app/models/job.py`, `backend/app/config.py` (`enabled_ontologies`).
- **Deep links:** `frontend/index.html` has the separate exemplar grids (`#demoExemplars` and `#demoExemplarsCanon`) and the hard-coded `CANON_EXEMPLAR_DEMO_SLUGS`. `tryLoadDemo` takes the ontology from the URL and ignores the baked demo's own ontology, which matters for R16.
- **No-leakage rule:** AC-1 in `docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md`.
- **Canon roots:** `docs/plans/2026-07-03-001-feat-canon-branch-roots-and-pos-salvage-plan.md` lists the 7 roots.
- **Demo freshness:** `docs/plans/2026-05-25-002-feat-prebaked-exemplar-demo-mode-plan.md` covers demo mode and freshness. The replay rebake (`backend/scripts/replay_fix_demos.py`) avoids LLM cost for deterministic fixes.
- **Measured overlap:** the Canon pin is `add8b2b1` and the FOLIO cache is dated 2026-10-30. Canon has 14,972 labeled classes and FOLIO 18,325. 14,407 share a local identifier, 12 of those differ in label, and 659 Canon labels are ambiguous in FOLIO. The Canon carries "Commandment 01"–"Commandment 10" classes that FOLIO lacks.
- **Measured density:** in concept tags per 100 words, Canon demos score nativity 12.4, rerum_novarum 12.6, trent_eucharist 13.3, and sacraments 26.6. FOLIO's `rich_*` demos score 33.9–44.2.
