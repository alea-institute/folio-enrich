---
phase: 01
phase_name: post-v1.0-verification
milestone: v1.1
status: testing
created: 2026-05-20
---

# Phase 01 — Post-v1.0 Verification Summary

## Purpose

Verify all ad-hoc changes that landed on `dev` after v1.0 milestone shipped (2026-04-05) work correctly before pushing to PROD (`enrich.openlegalstandard.org`).

**Deployment under test:** https://folio-enrich-production.up.railway.app (Railway DEV)
**Source range:** `5150ede..HEAD` (21 commits, 2026-04-05 → 2026-04-08)

## Testable Deliverables

### Group A — Entity Graph: Edge Routing & Layout (5 commits)

1. **Graph edges route through node centers** (f5823b1) — edges connect at node center points, matching folio-mapper visual
2. **90° edge connections at all nodes** (9185a97) — orthogonal entry/exit at every node
3. **Cubic Bezier curves for graph edges** (08619d9) — ConceptDAG-style curves replace prior routing
4. **Rounded polylines** (cd67f51) — switched from splines
5. **No ELK crash on branch roots with seeAlso edges** (d943d2e) — graph renders without exception

### Group B — Entity Graph: Visual Refresh (3 commits)

6. **6 visual improvements applied** (07fe169) — entity graph visual refresh quick task 260407-bn9
7. **branch_root_type + child_count on GraphNode** (bd710f2) — nodes display branch root type indicator + child count badge
8. **Graph minimap background theme-aware** (99eae53) — minimap respects current theme

### Group C — Entity Graph: Theme & Layer Behavior (3 commits)

9. **Light theme for entity graph in Mixed mode** (77b42cf) — graph uses light theme inside the dark-left/light-right layout
10. **Concepts layer always active on load** (2400c36) — concepts layer defaults to enabled
11. **All core layers force-enabled on load** (8a5002b) — concepts, properties, individuals all on by default

### Group D — Detail Panel & Tab Restructure (2 commits)

12. **Detail panel header → tabbed Candidate Details / Entity Graph** (27f0942) — panel header replaced with tab nav
13. **∀ symbol replaced with nodes-and-edges SVG icon** (5188e5d) — Entity Graph tab icon redesigned

### Group E — Ontology Display (1 commit)

14. **Preferred label / synonyms / translations / see also styled as pills** (1b1e50f) — ontology metadata displays as pill chips, not plain text

### Group F — Accessibility (2 commits)

15. **Pipeline stage pills WCAG AA compliant** (edfeb09) — pill colors meet 4.5:1 contrast
16. **Green text darkened in light mode** (d4551bc) — green text passes WCAG AA on white

### Group G — LLM UX (1 commit)

17. **Friendly LLM setup banner when no AI key configured** (d0d1107) — banner appears guiding users to set up a provider

### Group H — Core Regression Sanity

18. **Document submission + SSE streaming** — submit a document, watch events flow, see annotations render
19. **Theme toggle still works** — Dark / Light / Mixed all switch correctly with no flash
20. **Health endpoint** — `/health` returns 200

## Out of Scope (this phase)

- 13 export format validation — separate concern, no exports changed since v1.0
- Backend pipeline correctness — no backend stage changes since v1.0
- Ollama setup — out of scope unless banner test surfaces issues
- Per-file deep WCAG audit — script already passes, audit not re-run
