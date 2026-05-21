# Milestones

## v1.1 Post-v1.0 Verification & Polish (Shipped: 2026-05-21)

**Phases completed:** 1 phase, 18 code commits

**Key accomplishments:**

- Entity graph parity with folio-mapper: cubic Bezier edges with 90° entry/exit through node centers, ELK crash prevented on branch roots with seeAlso edges
- Visual refresh + detail panel restructure: branch_root_type + child_count, theme-aware minimap, CANDIDATE DETAILS / ENTITY GRAPH tab nav with new SVG icon
- A11y polish: pipeline stage pills WCAG AA (~12:1), green text darkened in light mode
- LLM UX: friendly setup banner when no key configured, chip now shows "Not Configured" instead of the default model name
- Ontology pill styling for synonyms, translations, see-also; favicon shipped; full UAT against Railway DEV and PROD

**Archive:** [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) · [phases/01-post-v1.0-verification/01-UAT.md](phases/01-post-v1.0-verification/01-UAT.md)

---

## v1.0 Three-Mode Theme System (Shipped: 2026-04-05)

**Phases completed:** 3 phases, 8 plans, 2 tasks

**Key accomplishments:**

- Two-layer CSS token system with 490+ variable definitions across three theme selectors (dark/light/mixed) plus 78 per-theme branch colors and component-level semantic tokens for modals, tooltips, graph, scrollbar, confidence tiers, and feedback
- All ~550 hardcoded CSS color values (414 hex + 135 rgba) converted to var() references; 104 data-branch rules consolidated to 52 via color-mix(); old panel variable overrides removed; mixed-mode modal/tooltip scoping added for backward compatibility

---
