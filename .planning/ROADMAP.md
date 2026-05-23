# Roadmap: FOLIO Enrich

## Milestones

- ✅ **v1.0 Three-Mode Theme System** — Phases 1-3 (shipped 2026-04-05)
- ✅ **v1.1 Post-v1.0 Verification & Polish** — Phase 01 (shipped 2026-05-21)
- 🚧 **v1.2 Header & Status UX** — Phases 02-03 (in progress)

## Phases

- [ ] **Phase 02: Robust translation flags** - Replace unrendered Unicode emoji flags with self-contained inline SVG flags that display on every OS and survive content blockers.
- [ ] **Phase 03: Consolidated system status chip** - Collapse Backend / FOLIO / Embedding / spaCy into one accessible "System" chip with worst-status rollup and click-to-expand detail.

<details>
<summary>✅ v1.1 Post-v1.0 Verification & Polish (Phase 01) — SHIPPED 2026-05-21</summary>

- [x] Phase 01: Post-v1.0 Verification — UAT 21 dev-branch commits + 2 follow-up fixes, deployed to PROD

**Archive:** [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) · [phases/01-post-v1.0-verification/01-UAT.md](phases/01-post-v1.0-verification/01-UAT.md)

</details>

<details>
<summary>✅ v1.0 Three-Mode Theme System (Phases 1-3) — SHIPPED 2026-04-05</summary>

- [x] Phase 1: CSS Variable Foundation (3/3 plans) — completed 2026-04-04
- [x] Phase 2: Theme Switching & JS Integration (2/2 plans) — completed 2026-04-05
- [x] Phase 3: Accessibility & Component Polish (3/3 plans) — completed 2026-04-05

**Archive:** [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) · [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) · [v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md)

</details>

## Phase Details

### Phase 02: Robust translation flags

**Goal**: Translation flags render reliably on every operating system and browser configuration, with no broken glyphs and no dependence on external resources.
**Depends on**: Nothing (independent of Phase 03; first phase of v1.2)
**Requirements**: FLAG-01, FLAG-02, FLAG-03, FLAG-04
**Success Criteria** (what must be TRUE):

  1. On Windows (and macOS/Linux), the user sees actual rendered flag graphics next to translation pills — never boxed "GB"/"ES" letters or empty placeholders.
  2. With a content/privacy blocker enabled (e.g., Privacy Badger), every flag still displays — confirming flags make no external image requests (inline SVG only).
  3. A screen-reader user hears an accessible label naming the locale/country for each flag.
  4. For any FOLIO locale without a bundled SVG, the user sees a graceful styled country-code pill instead of a broken glyph.

**Plans**: 1 plan
Plans:

- [x] 02-01-PLAN.md — Vendor 12 inline-SVG flags (flag-icons MIT), wire flagMarkup into translation pills, theme-aware box + fallback pill + Intl.DisplayNames labels; manual UAT for OS render & blocker resilience

**UI hint**: yes

### Phase 03: Consolidated system status chip

**Goal**: Passive subsystem health (Backend, FOLIO, Embedding, spaCy) is presented as one clear, accessible "System" chip so problems are obvious, clutter is gone, and the header no longer overlaps the layer chips.
**Depends on**: Phase 02 (sequential within milestone; no technical coupling, ordered for delivery)
**Requirements**: STATUS-01, STATUS-02, STATUS-03, STATUS-04, STATUS-05, STATUS-06, STATUS-07
**Success Criteria** (what must be TRUE):

  1. The user sees a single "System" chip in the header in place of the four separate Backend / FOLIO / Embedding / spaCy chips, and it shows a quiet green state when all four subsystems are healthy.
  2. When any subsystem is degraded or errored, the chip reflects the worst status (red > orange > green) and names the failing subsystem.
  3. The user can click/expand the chip to reveal per-subsystem detail, preserving today's metrics (concepts loaded, vectors indexed, etc.).
  4. The user perceives each status via icon + text (not color alone); the chip meets WCAG AA and is fully keyboard- and screen-reader-accessible.
  5. The LLM chip remains a separate, actionable control with its configure behavior unchanged, and the header status chips no longer overlap the layer chips (Nouns/Verbs/Individuals/POS).

**Plans**: 4 plans (Wave 1: 03-01 ∥ 03-02 · Wave 2: 03-03 · Wave 3: 03-04)
Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Pure tested rollup module (scripts/system-rollup.mjs + .test.mjs): normalizeSubsystems (D-05/D-06 Standby/Update→green), computeRollup (worst-of-four), chipLabel ("System" / "System: {X} +N") — STATUS-02/03
- [x] 03-02-PLAN.md — Extend scripts/contrast-audit.mjs: status-icon 3:1 graphical-object checks (green/orange/red on surface2/surface3, all themes) + fix stale report path; assertions in contrast-audit.test.mjs — STATUS-05

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-03-PLAN.md — index.html markup/CSS: replace 4 chips with System disclosure chip + anchored popover, inline-SVG status glyphs (--text stroke fallback), re-home FOLIO Manage (D-08), byte-identical inline rollup copy — STATUS-01/05/07

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-04-PLAN.md — index.html JS: refactor checkHealth()→normalize/rollup/render, accessible non-modal disclosure (open/close/focus/Escape/outside-click, D-04), live in-place rows (D-03), preserve metrics + LLM branch + FOLIO toast; manual UAT — STATUS-01/03/04/05/06/07

**UI hint**: yes
