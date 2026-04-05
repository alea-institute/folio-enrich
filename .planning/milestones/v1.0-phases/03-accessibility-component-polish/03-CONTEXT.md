# Phase 3: Accessibility & Component Polish - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit WCAG AA contrast ratios across all theme/text-token pairs and all 26 branch-tinted backgrounds in Dark/Light/Mixed themes. Adjust foreground text colors for any pairs that fail. Verify modals, tooltips, and scrollbars render correctly in all three themes and fix any edge cases.

</domain>

<decisions>
## Implementation Decisions

### Audit Strategy
- **D-01:** Hybrid audit approach — automated Node.js script for WCAG math on all CSS token pairs, plus manual Chrome DevTools spot-checks for rendered elements where backgrounds are computed from mixed tokens (e.g., branch-tinted backgrounds via `color-mix()`).
- **D-02:** Adjust foreground text colors when pairs fail — backgrounds stay stable (they define the theme). Darken `--text-dim`, `--accent`, or per-element text colors until WCAG AA passes.

### Branch Color Legibility
- **D-03:** Adjust text color per branch tint — for each branch-tinted background that fails WCAG on standard `--text`, override with a darker/lighter text color for that branch context. Preserves the 26 branch hue identities.

### Contrast Margins
- **D-04:** Target 5.5:1+ for body text (1.0 margin above 4.5:1 AA threshold). Pairs between 4.5-5.4:1 are "AA tight" — acceptable if adjustment would hurt the design. Below 4.5:1 is a failure that must be fixed.
- **D-05:** Use large-text threshold (3:1) for text ≥18pt regular or ≥14pt bold — applies to panel headers, tab labels, section titles. Body text (everything else) must meet 4.5:1.

### Modal/Tooltip Scope
- **D-06:** Verify + fix gaps only — open every modal/tooltip in all 3 themes via Chrome DevTools, find dark-on-dark or light-on-light text, broken hover states, or missing borders. Fix issues found. Do NOT redesign working components.

### Claude's Discretion
- Exact adjusted values for failing `--text-dim` / `--accent` colors (Claude picks values that pass and look natural)
- Per-branch text overrides (only add overrides for branches that fail audit)
- Whether to use `color-mix()` with `--text` or introduce new `--text-on-tint-*` tokens

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — A11Y-01 through A11Y-06, CMPT-01 through CMPT-03
- `.planning/PROJECT.md` — WCAG AA is non-negotiable (legal professional audience)

### Phase 1 Output (token system)
- `.planning/phases/01-css-variable-foundation/01-CONTEXT.md` — Token architecture
- `frontend/index.html` — All tokens defined in `[data-theme=*]` blocks

### Phase 2 Output (theme switching)
- `frontend/index.html` — `data-theme` attribute, theme toggle, color-scheme already set

### External
- WCAG AA contrast requirements: 4.5:1 body text, 3:1 large text (≥18pt or ≥14pt bold)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `color-scheme` CSS already set per theme in Phase 2 (handles scrollbar theming for free)
- `.panel-right`/`.panel-detail`/`.modal`/`.concept-tooltip` already scoped under `[data-theme="mixed"]` for light styling
- All 78 branch colors defined with `--branch-*` kebab-case naming

### Established Patterns
- Branch tint pattern: `color-mix(in srgb, var(--branch-X) 12%, transparent)` for backgrounds, 22% for hover
- Text tokens: `--text` (strongest), `--text-dim` (secondary), `--accent` (links/highlights)
- Confidence badges use `--conf-high/mid/low` + `--conf-*-bg` pairs

### Integration Points
- All CSS token definitions in the three `[data-theme=*]` selectors (lines 62-450 range)
- Modal/tooltip light overrides at line ~410 (`[data-theme="mixed"] .modal, .concept-tooltip`)
- Branch rules at lines after data-theme tokens

### Phase 1 Known Risks (from PROJECT.md)
- `--text-dim` on `--bg` is marginal (5.0-5.2:1) — needs verification
- `--accent` in light mode barely passes (4.6:1) — was adjusted to #2d5ee0 for 5.1:1
- Some branch colors may fail on dark backgrounds

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-accessibility-component-polish*
*Context gathered: 2026-04-05*
