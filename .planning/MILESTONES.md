# Milestones

## v1.0 Three-Mode Theme System (Shipped: 2026-04-05)

**Phases completed:** 3 phases, 8 plans, 2 tasks

**Key accomplishments:**

- Two-layer CSS token system with 490+ variable definitions across three theme selectors (dark/light/mixed) plus 78 per-theme branch colors and component-level semantic tokens for modals, tooltips, graph, scrollbar, confidence tiers, and feedback
- All ~550 hardcoded CSS color values (414 hex + 135 rgba) converted to var() references; 104 data-branch rules consolidated to 52 via color-mix(); old panel variable overrides removed; mixed-mode modal/tooltip scoping added for backward compatibility

---
