# Handoff: unified proposition engine brainstorm

## State
- **Brainstorm done:** requirements-only plan at `docs/plans/2026-10-26-0700-feat-unified-proposition-engine-plan.md` (uncommitted when written).
- **Decisions recorded:** Cockpit asks `folio-enrich-2026-10-25-2017-insights-into-enrich-scope`, `folio-enrich-2026-10-25-2022-insights-propositions-combine`, `folio-enrich-2026-10-25-2046-insights-single-doc-surface` (all answered by Damien).
- **Next:** `ce-plan` on that plan, after Damien picks from the Phase 4 menu.

## Key decisions
- **Repo roles:** folio-propositions = shared record; folio-enrich = the one per-document engine + webapp; folio-insights = corpus and governance, running the engine as a pinned in-process library on every document (single doc = corpus of one).
- **KnowledgeUnit retires;** its quote/anchor, flat FOLIO tags, and lineage move into the folio-propositions record.
- **Extractor chosen by Palsgraf gold-set score** (R9).

## In-flight folio-insights work
- **Continue freely:** Phase 13 storage, U17/R18, Phase 11 SHACL, governance, minter/kernel, Phase 9, U6 polysemy, retiring sibling bridges.
- **Realign before new build:** Phase 10 pipeline re-plan (extraction logic waits for R9) and the review UI re-scope annotator (becomes the shared per-document view).
