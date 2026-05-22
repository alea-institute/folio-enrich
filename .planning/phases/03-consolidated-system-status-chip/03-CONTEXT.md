# Phase 03: Consolidated system status chip - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Collapse the four separate passive health chips — **Backend, FOLIO, Embedding, spaCy** — into a single accessible **"System"** chip in the header. The chip shows a quiet green state when all four are healthy, rolls up to the worst status (red > orange > green) and names the failing subsystem when degraded/errored, and expands on click to reveal per-subsystem detail (status + today's metrics: concepts loaded, vectors indexed, spaCy version, etc.). The chip is perceivable by icon + text (not color alone), meets WCAG AA, and is fully keyboard- and screen-reader-accessible. Covers STATUS-01..STATUS-07.

**In scope:** the consolidated System chip (collapsed + expanded), its status rollup logic, accessibility, and resolving the header overlap between the status chips and the layer chips (Nouns/Verbs/Individuals/POS).

**Not in scope (locked elsewhere):**
- The **LLM chip** stays a separate, actionable control with its current configure behavior unchanged (STATUS-06). It is NOT folded into the System chip.
- No new backend health/telemetry endpoints — uses the existing `/health` and `/health/detail` data.
- Restyling/regrouping the layer chips (Nouns/Verbs/Individuals/POS) — separate concern, deferred.
- Responsive/mobile header layout — deferred.

</domain>

<decisions>
## Implementation Decisions

### Expand mechanism
- **D-01:** Detail reveals via an **anchored popover** that drops down directly below the System chip, listing one row per subsystem (Backend / FOLIO / Embedding / spaCy) with each row's status + metrics. Keeps the header layout stable (no reflow), matches the common status-chip pattern. (Chosen over inline header expansion and a centered modal.)
- **D-02:** The chip is **always expandable**, even when all four subsystems are green. The popover shows all four healthy rows with their metrics so users can check state at any time; the affordance never appears/disappears.
- **D-03:** Popover rows **update live** while open — they reflect the latest health poll (e.g. FOLIO `Standby → green` updates in place as enrichment finishes), and the collapsed chip's worst-status rollup updates with it.
- **D-04:** Standard popover accessibility (Claude's discretion on exact mechanics): open via click and Enter/Space, close on Escape / outside-click / re-activate, move focus into the popover on open and restore it on close, with appropriate ARIA (e.g. `aria-expanded`, `role` for the disclosure).

### Status rollup mapping (worst-status: red > orange > green)
- **D-05:** **Standby / lazy-not-loaded counts as healthy (green).** FOLIO and Embedding report orange "Standby" before first enrichment — this is normal, not a fault — so it must NOT trip the rollup. The System chip is **quiet green at rest on a fresh page load** (satisfies STATUS-02). The popover row still labels it "Standby — loads on first use" so the nuance is visible.
- **D-06:** **FOLIO "Update Available" / "Updating…" count as healthy (green).** These are informational, not degraded; they do not trip the chip to orange. The FOLIO popover row carries the update note/badge. Keeps the chip's color reserved for actual problems (avoids alert fatigue).
- **D-07:** Resulting mapping:
  - **Red** — any subsystem errored/offline: Backend offline, FOLIO error, Embedding error, spaCy error.
  - **Green** — all subsystems ready, OR in a non-alarming state (FOLIO/Embedding Standby, FOLIO Update-Available/Updating).
  - **Orange** — reserved for genuine degradation/warnings (no current subsystem state maps here after D-05/D-06; keep the tier available for future partial-degradation signals). Popover rows MAY still annotate Standby/Update distinctly without escalating the chip.

### FOLIO management action
- **D-08:** The "manage FOLIO ontology" affordance (today the clickable FOLIO chip + gear → `openFolioModal()`) moves to a **"Manage" action inside the FOLIO row of the popover**, opening the existing FOLIO modal unchanged. Keeps the affordance discoverable and contextual next to FOLIO's status/metrics. (Chosen over a gear on the aggregate System chip — ambiguous — and over settings-only — removes quick access.) FOLIO is the only subsystem with a management action; the others get no per-row action.

### Collapsed chip text & icons (icon + text, not color alone — STATUS-05)
- **D-09:** The colored dot becomes a real **status icon** so status is conveyed by icon + text, not color alone. Exact glyphs are Claude's/ui-phase's discretion within intent: a **check** for healthy, and distinct **error (red)** / **warning (orange)** icons for degraded.
- **D-10:** **Healthy collapsed state:** status (check) icon + the word **"System"**. Quiet and minimal; metrics live in the popover.
- **D-11:** **Degraded/errored collapsed state:** worst-status icon + **"System: {Subsystem}"** naming the failing subsystem (e.g. "System: FOLIO", "System: Backend"). If more than one subsystem fails, show the worst one plus a **"+N"** overflow (e.g. "System: FOLIO +1"); the full list is in the popover. (Satisfies STATUS-03.)

### Header overlap (STATUS-07)
- **D-12:** Collapsing four chips into one is expected to free enough header width to **resolve the overlap with the layer chips** (Nouns/Verbs/Individuals/POS) on its own. The System chip occupies the former status-chip area; the LLM chip remains to its right as a separate control. Any residual layout work (flex/wrap behavior) is left to planning / `/gsd:ui-phase` to confirm and finalize.

### Claude's Discretion
- Exact icon glyphs (check/warning/error) and the popover's visual design — to be specified by `/gsd:ui-phase` and refined in planning, within the icon+text + theme-aware + WCAG AA intent above.
- Popover open/close/focus mechanics and ARIA attribute choices (D-04).
- Internal refactor of `setChip()` / `checkHealth()` to drive the consolidated chip vs. five independent chips.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` § "Phase 03: Consolidated system status chip" — goal + 5 success criteria.
- `.planning/REQUIREMENTS.md` § "System Status Chip (STATUS)" — STATUS-01..STATUS-07, plus Out-of-Scope (LLM not folded in; no new backend endpoints; no per-subsystem config UI).

### Carried-forward project context
- `.planning/PROJECT.md` § "Context" / "Constraints" — single-file `frontend/index.html`, no build step, no new dependencies, three-mode theme (Dark/Light/Mixed) via CSS vars, WCAG AA.

No external specs/ADRs — requirements fully captured in decisions above. A `/gsd:ui-phase` design contract (UI-SPEC.md) is expected before planning and will become an additional canonical ref.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/index.html:2959-2987` — the `#statusBar` header markup: five `.status-chip` divs (`chipBackend`, `chipFolio` [clickable, gear → `openFolioModal()`], `chipEmbedding`, `chipSpacy`, `chipLLM` [clickable → `onLLMChipClick()`]). Backend/FOLIO/Embedding/spaCy collapse into one System chip; **`chipLLM` stays as-is** (STATUS-06).
- `frontend/index.html:4038-4130` — `checkHealth()`: fetches `/health` (basic up/down → Backend) then `/health/detail` and maps `d.folio_ontology`, `d.embedding`, `d.llm`, `d.spacy` to chip states via `setChip(id, dotColor, detailText, tooltip)`. This is where the worst-status rollup + per-subsystem rows must be derived.
- `setChip(id, color, detailText, tooltip)` (~line 4020) — current per-chip updater (dot color + label + detail + tooltip). Will be refactored/replaced to drive the consolidated chip's icon/text and the popover rows.
- `frontend/index.html:536-584` — `.status-chip` CSS (dot colors `green/orange/red/gray/blue`, hover, fixed-position `data-tooltip`). Icon styling (D-09) extends this.
- `frontend/index.html:1270-1296` — `.status-chip.clickable` + `.chip-gear` styles, and `.folio-status-row` / `.folio-status-dot` used inside the FOLIO modal — a per-row status pattern to mirror in the popover.

### Established Patterns
- All colors are CSS variables (`--green`, `--orange`, `--red`, `--text-dim`, `--accent`, …) across Dark/Light/Mixed themes — the System chip + popover MUST use theme-aware vars (v1.0 token system).
- Existing modals (FOLIO modal `openFolioModal()`, settings) provide established accessibility/overlay patterns the popover can borrow from.
- The app already polls health on an interval (drives D-03 live-updating rows).

### Integration Points
- `/health` and `/health/detail` response shapes: `folio_ontology` {status, concepts, labels_indexed, update_status{update_in_progress, update_available, last_update_at, concepts_before/after}}, `embedding` {status, provider, index_size}, `spacy` {status, version}, `llm` {provider, status, model}. No new fields/endpoints needed (locked).
- Header sibling: `.header-controls` / `#layerToggleBar` (layer chips Nouns/Verbs/Individuals/POS, ~line 2988+) — the overlap target for STATUS-07.

</code_context>

<specifics>
## Specific Ideas

- "Quiet green at rest" is the bar: on a fresh page load, before any enrichment, the chip should read as healthy green — not orange — even though FOLIO/Embedding are technically in Standby (D-05).
- Preserve today's per-subsystem metrics verbatim in the popover (concepts loaded, labels indexed, vectors indexed, provider, spaCy version) — consolidation must not lose information (STATUS-04).

</specifics>

<deferred>
## Deferred Ideas

- Folding the LLM chip into the System chip — explicitly out of scope; LLM is an actionable control, not a passive health indicator (would muddy its affordance).
- Restyling/regrouping the layer chips (Nouns/Verbs/Individuals/POS) — separate concern from system health.
- Responsive/mobile header layout — not in scope for this milestone.
- A dedicated orange/"degraded" subsystem signal — the rollup keeps the orange tier available (D-07) but no current subsystem state populates it; a future partial-degradation signal could.

None other — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-consolidated-system-status-chip*
*Context gathered: 2026-05-22*
