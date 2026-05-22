# Phase 03: Consolidated System Status Chip - Research

**Researched:** 2026-05-22
**Domain:** Accessible disclosure UI (vanilla JS / inline SVG / WCAG AA) in a single-file frontend
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Detail reveals via an **anchored popover** dropping down directly below the System chip, one row per subsystem (Backend / FOLIO / Embedding / spaCy), each with status + metrics. `position: fixed` to avoid header reflow.
- **D-02:** Chip is **always expandable**, even when all four are green. Popover always shows all four rows. Affordance never appears/disappears.
- **D-03:** Popover rows **update live** while open from the latest health poll; the collapsed chip rollup updates with them.
- **D-04:** Standard popover accessibility (Claude's discretion on mechanics): open via click + Enter/Space; close on Escape / outside-click / re-activate; move focus into popover on open and restore on close; appropriate ARIA (`aria-expanded`, role for the disclosure).
- **D-05:** **Standby / lazy-not-loaded counts as healthy (green).** FOLIO/Embedding `not_loaded` is normal, NOT a fault. Chip is **quiet green at rest on a fresh page load** (STATUS-02). Popover row still labels it "Standby — loads on first use".
- **D-06:** **FOLIO "Update Available" / "Updating…" count as healthy (green).** Informational, not degraded. FOLIO row carries the update note/badge.
- **D-07:** Mapping — **Red:** any subsystem errored/offline. **Green:** all ready, OR FOLIO/Embedding Standby, OR FOLIO Update-Available/Updating. **Orange:** reserved for future partial-degradation (no current state maps here). Rollup = worst of four: red > orange > green.
- **D-08:** "Manage FOLIO ontology" affordance moves to a **"Manage" action inside the FOLIO row** of the popover, opening the existing FOLIO modal unchanged. FOLIO is the only subsystem with a per-row action.
- **D-09:** Colored dot becomes a real **status icon** (icon + text, not color alone). Glyphs are Claude's/ui-phase discretion: check (healthy), distinct error (red) / warning (orange).
- **D-10:** **Healthy collapsed state:** status (check) icon + the word **"System"**.
- **D-11:** **Degraded/errored collapsed state:** worst-status icon + **"System: {Subsystem}"**; if >1 fails, show worst + **"+N"** overflow (e.g. "System: FOLIO +1"). Full list in popover (STATUS-03).
- **D-12:** Collapsing four chips into one is expected to free header width and **resolve the overlap with the layer chips** on its own. System chip occupies the former status-chip area; LLM chip remains to its right. Residual layout work left to planning / `/gsd:ui-phase`.

### Claude's Discretion
- Exact icon glyphs (check/warning/error) and popover visual design — within icon+text + theme-aware + WCAG AA intent. (UI-SPEC has now specified these.)
- Popover open/close/focus mechanics and ARIA attribute choices (D-04).
- Internal refactor of `setChip()` / `checkHealth()` to drive one consolidated chip instead of five.

### Deferred Ideas (OUT OF SCOPE)
- Folding the LLM chip into the System chip — LLM stays a separate actionable control (STATUS-06).
- Restyling/regrouping the layer chips (Nouns/Verbs/Individuals/POS).
- Responsive/mobile header layout.
- A dedicated orange/"degraded" subsystem signal — orange tier kept available (D-07) but unpopulated.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATUS-01 | Backend/FOLIO/Embedding/spaCy consolidated into one "System" chip | Replace 4 of 5 `.status-chip` divs (`index.html:2960-2980`) with one chip; keep `chipLLM` (`:2981-2986`). Refactor `checkHealth()` to set one chip from the existing `/health/detail` response (§ Refactor Approach). |
| STATUS-02 | Single quiet-green state when all four healthy | Rollup function maps Standby/Update→green (D-05/D-06); fresh page load = green (§ Worst-Status Rollup). |
| STATUS-03 | Worst-status (red>orange>green) + identify failing subsystem | Pure `computeRollup()` returning `{tier, worstName, failCount}`; collapsed label "System: {Subsystem} +N" (§ Worst-Status Rollup). |
| STATUS-04 | Click/expand to per-subsystem detail (preserve today's metrics) | Anchored popover with 4 rows; metrics copied verbatim from current `setChip()` tooltip strings (§ Metric Preservation Map). |
| STATUS-05 | Icon + text (not color alone); WCAG AA; keyboard + SR accessible | Inline-SVG glyphs with distinct silhouettes + stroke fallback for Light theme (§ Inline-SVG Status Icons, § Contrast Findings); disclosure ARIA + focus mgmt (§ Accessible Disclosure Pattern). |
| STATUS-06 | LLM chip stays separate, actionable, unchanged | Do NOT touch `chipLLM` markup, `onLLMChipClick()`, or its branch of `checkHealth()` (incl. `updateOllamaChip()`). LLM is excluded from the rollup. |
| STATUS-07 | Status chips no longer overlap layer chips | 4→1 reduction frees width; verify `#statusBar` vs `#layerToggleBar`; residual fix = `flex-wrap`/`min-width:0` on `.status-bar` (§ Header Overlap). |
</phase_requirements>

## Summary

This is a **frontend-only, no-new-dependency, no-backend-change** refactor of an existing five-chip header status bar into one consolidated, accessible "System" disclosure chip plus a four-row anchored popover. All the data already exists in the `/health` and `/health/detail` responses (verified in `backend/app/api/routes/health.py` — no changes needed). The work is concentrated in `frontend/index.html`: replace four chip divs with one, add popover markup + CSS, write a pure rollup function, and refactor `checkHealth()`/`setChip()` to drive the new structure while leaving the LLM chip's code path untouched.

The two highest-risk areas are **accessibility mechanics** and **WCAG-AA contrast of the status icons**. For accessibility: the correct primitive is the **WAI-ARIA disclosure pattern** (a `role="button"` toggle with `aria-expanded`/`aria-controls`), augmented with the non-modal-dialog conventions D-04 asks for (move focus in on open, restore on close, Escape/outside-click dismissal). A full focus trap is **not** required and would be wrong for a non-modal popover. For contrast: I computed the actual ratios — in the **Light theme** the green and orange status icons FAIL the 3:1 non-text-contrast floor (2.5–2.8:1), so the UI-SPEC's "render the glyph stroke at `var(--text)`" fallback is **mandatory, not optional**, for Light-theme green/orange. Dark and Mixed themes pass everywhere.

**Primary recommendation:** Implement the chip as a disclosure button (`role="button"` + `aria-expanded` + `aria-controls`), the popover as a non-modal `position: fixed` region placed in the DOM immediately after the chip, drive both from a single pure `computeRollup(detail)` function, render status icons as inline SVG with a `var(--text)` stroke outline + status-color fill (so the shape carries 3:1 in every theme), and confirm STATUS-07 is resolved by the 4→1 width reduction with a `flex-wrap`/`min-width:0` safety net on `.status-bar`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Subsystem health data | API / Backend (`/health`, `/health/detail`) | — | Already implemented and locked; phase consumes it read-only. |
| Status rollup (worst-of-four) | Browser / Client (pure JS) | — | Pure presentation logic over the health payload; no server state. D-07 mapping lives entirely client-side. |
| Disclosure chip + popover rendering | Browser / Client | — | DOM + inline SVG + CSS vars in `frontend/index.html`. |
| Live update while open | Browser / Client (existing 10 s poll) | — | `setInterval(checkHealth, 10000)` at `index.html:4011` already drives updates; popover re-renders in place (D-03). |
| FOLIO management action | Browser / Client (`openFolioModal()`) | — | Existing modal, unchanged; popover row just calls it (D-08). |

**Why this matters:** Every capability in this phase is client-side. Any task that proposes a backend edit, a new endpoint, or new server state is misassigned and contradicts the locked scope (CONTEXT.md "no new backend health/telemetry endpoints"). The plan-checker should reject backend tasks.

## Project Constraints (from CLAUDE.md)

- **Frontend:** single-file `frontend/index.html` (vanilla JS, inline `<style>`, **no build step**). All new CSS/JS lives in that file.
- **No new runtime dependencies.** Status icons MUST be inline SVG — no icon font, no emoji, no external image requests (mirrors Phase 02's vendored-SVG flag approach; survives content blockers).
- **Backend:** Python/FastAPI in `backend/`, venv at `backend/.venv/`. Tests: `cd backend && .venv/bin/python -m pytest tests/ -v`. (No backend test changes expected this phase.)
- **Three-mode theme** (Dark/Light/Mixed) via `data-theme` on `<html>`; ALL colors are CSS variables. Reuse `--green/--orange/--red/--surface2/--surface3/--border/--text/--text-dim/--accent/--accent-dim`. Do NOT introduce a new token set.
- **WCAG AA is mandatory.** Automated audit at `scripts/contrast-audit.mjs` (`node scripts/contrast-audit.mjs`).
- **Run server:** `cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8731 --reload`; frontend at `http://localhost:8732`.

## Standard Stack

No packages are installed in this phase. The "stack" is platform primitives already present in the file.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Vanilla DOM API | platform | Chip/popover markup + event handling | No build step; matches existing `frontend/index.html` patterns `[VERIFIED: codebase index.html:4021-4130, 10388-10411]` |
| Inline SVG | platform | Status glyphs (check / triangle-bang / cross-circle) | Survives content blockers; matches Phase 02 flag precedent `[CITED: STATE.md "vendored inline flag-icons SVGs"]` |
| CSS custom properties | platform | Theme-aware color across Dark/Light/Mixed | Existing v1.0 token system `[VERIFIED: codebase index.html:17-453]` |
| WAI-ARIA disclosure pattern | ARIA 1.2 APG | Accessible expand/collapse semantics | Authoritative pattern for show/hide-on-trigger `[CITED: w3.org/WAI/ARIA/apg/patterns/disclosure/]` |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `scripts/contrast-audit.mjs` | repo, zero-dep Node | WCAG AA contrast verification | Run after CSS changes; see § Contrast Findings for a required script gap `[VERIFIED: codebase scripts/contrast-audit.mjs]` |
| `node` | system | Run the audit script | `node scripts/contrast-audit.mjs` |
| Chrome DevTools MCP | per global CLAUDE.md | Visual + interaction verification | Manual UAT across the three themes (§ Validation Architecture) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Disclosure (`role=button` + `aria-expanded`) | `role=menu` / menubutton | Menu semantics imply a list of *actions* with arrow-key navigation; this popover is mostly *status display* with one action. Disclosure is the correct, simpler pattern. `[CITED: w3.org/WAI/ARIA/apg/patterns/disclosure/]` |
| Non-modal popover (no focus trap) | Modal dialog (`aria-modal`, focus trap) | A modal would make the rest of the header inert and require a trap — overkill and worse UX for a passive status panel. Non-modal is correct. `[CITED: accessuse.eu/en/non-modal-dialogs.html]` |
| `position: fixed` popover | inline header expansion | Inline expansion reflows the header (rejected in D-01). |
| Native `popover` attribute / Popover API | manual show/hide | Tempting, but the native `popover` API's top-layer + light-dismiss is newer and would change focus semantics; the existing `data-tooltip` already uses `position: fixed` (`index.html:570-583`) so manual matches the codebase and is safest for no-build vanilla JS. `[ASSUMED]` — manual approach recommended for consistency. |

**Installation:** None. No `npm install`, no `pip install`. This phase adds zero dependencies.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages (single-file vanilla JS, no build step, explicit "no new dependencies" constraint). slopcheck/registry verification is moot. Any plan task proposing a package install contradicts the locked scope and should be rejected.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────────┐
   10s poll               │  checkHealth()  (index.html ~4038)        │
   setInterval ──────────▶│   1. GET /health        → backend up/down │
   (index.html:4011)      │   2. GET /health/detail → subsystem JSON  │
                          └───────────────┬───────────────┬──────────┘
                                          │               │
                          backend down ◀──┘               │ detail JSON
                          (red, all rows offline)         ▼
                                          ┌───────────────────────────────────┐
                                          │ normalizeSubsystems(detail)         │
                                          │  → [{key,name,tier,statusWord,      │
                                          │      metric,annotation,action?}]    │
                                          │  (LLM EXCLUDED — STATUS-06)         │
                                          └───────────────┬─────────────────────┘
                                                          │
                              ┌───────────────────────────┴──────────────────┐
                              ▼                                               ▼
                  ┌───────────────────────────┐                 ┌────────────────────────────┐
                  │ computeRollup(subsystems)  │                 │ renderPopoverRows(subsystems)│
                  │  worst of 4: red>orange>grn│                 │  4 rows, fixed order,        │
                  │  → {tier, worstName, +N}   │                 │  live re-render in place (D-03)│
                  └────────────┬───────────────┘                 └──────────────┬───────────────┘
                               ▼                                                ▼
                  ┌──────────────────────────┐                   ┌──────────────────────────────┐
                  │ renderCollapsedChip()     │                   │ #systemStatusPopover          │
                  │ [icon][System / System:X +N]                  │ role=region, position:fixed   │
                  │ role=button aria-expanded  │◀── toggle ───────│ FOLIO row → openFolioModal()  │
                  │ aria-controls=popover      │   open/close      │ (D-08, unchanged)             │
                  └──────────────────────────┘                   └──────────────────────────────┘

   ── UNCHANGED, separate path ────────────────────────────────────────────────────────
   chipLLM (index.html:2981-2986) ── onLLMChipClick() ──▶ LLM config   [STATUS-06: do not touch]
   d.llm branch of checkHealth() + updateOllamaChip()    [keep as-is]
```

### Recommended Component Responsibilities

| Function (new or refactored) | Responsibility | Notes |
|------------------------------|----------------|-------|
| `normalizeSubsystems(detail)` (new) | Map raw `/health/detail` JSON → array of 4 normalized row objects | Pure; LLM excluded. One place to encode D-05/D-06 status-word + annotation copy. |
| `computeRollup(subsystems)` (new) | Reduce 4 rows → `{tier:'green'|'orange'|'red', worstName, failCount}` | Pure; encodes D-07 worst-of-four. Unit-testable. |
| `renderSystemChip(rollup)` (new) | Set chip icon (rollup glyph) + label ("System" / "System: X +N") + `aria-expanded` | Replaces 4 `setChip()` calls. |
| `renderPopoverRows(subsystems)` (new) | Render/update the 4 rows in place (D-03) | Idempotent so live polls don't tear down focus. |
| `openSystemPopover()` / `closeSystemPopover()` (new) | Disclosure toggle + focus management | See § Accessible Disclosure Pattern. |
| `checkHealth()` (refactor) | Fetch + call normalize→rollup→render; **keep the `d.llm`/Ollama branch untouched** | `index.html:4038-4130`. |
| `setChip()` (keep) | Still used by `chipLLM` (and Ollama). **Do not delete** — LLM depends on it. | `index.html:4021`. |

### Pattern 1: WAI-ARIA Disclosure (the collapsed chip)
**What:** A toggle button that shows/hides associated content.
**When to use:** Show/hide a region on activation — exactly this chip.
**Required semantics** `[CITED: w3.org/WAI/ARIA/apg/patterns/disclosure/]`:
- The trigger has `role="button"` (or is a `<button>`).
- `aria-expanded="true|false"` reflects popover visibility.
- `aria-controls="systemStatusPopover"` (optional but recommended) points at the region.
- Keyboard: **Enter** and **Space** toggle. (The existing handler at `index.html:10405-10410` already does Enter/Space → `.click()` for `.status-chip.clickable`; reuse it.)

```html
<!-- Source: WAI-ARIA APG disclosure pattern, adapted to existing .status-chip -->
<div class="status-chip system-chip" id="chipSystem"
     role="button" tabindex="0"
     aria-haspopup="true" aria-expanded="false"
     aria-controls="systemStatusPopover"
     aria-label="System status">
  <span class="chip-status-icon"><!-- inline SVG rollup glyph --></span>
  <span class="chip-label" id="chipSystemLabel">System</span>
</div>
<div class="system-popover" id="systemStatusPopover"
     role="region" aria-label="System status detail" hidden>
  <!-- 4 rows injected here -->
</div>
```

### Pattern 2: Non-Modal Popover focus & dismissal (D-04)
**What:** A `position: fixed` region that does NOT trap focus and does NOT make the page inert.
**Authoritative conventions** `[CITED: accessuse.eu/en/non-modal-dialogs.html]`:
- **DOM placement:** put the popover **immediately after** the trigger in source order so screen-reader users arrow/tab into it naturally.
- **Focus on open:** D-04 asks to move focus in — set focus to the popover container (`tabindex="-1"` on the region) or to its first focusable element (the FOLIO "Manage" action). Either is acceptable per the guidance.
- **Focus on close:** restore focus to `#chipSystem`.
- **Dismissal:** Escape, outside-click, or re-activating the chip. (Escape is not part of the bare disclosure spec, but D-04 requires it and it is standard for popovers.)
- **No focus trap.** Tab may leave the popover; that is correct for non-modal. A trap is only for modal dialogs `[CITED: w3.org/WAI/ARIA/apg/patterns/dialog-modal/]`.

```javascript
// Source: synthesized from WAI-ARIA disclosure + Access&Use non-modal dialog guidance
function openSystemPopover() {
  const chip = document.getElementById('chipSystem');
  const pop  = document.getElementById('systemStatusPopover');
  pop.hidden = false;
  chip.setAttribute('aria-expanded', 'true');
  // move focus in (D-04): region is focusable via tabindex="-1"
  pop.focus();
  document.addEventListener('keydown', _systemPopoverKeydown);
  // defer so the opening click doesn't immediately close it
  setTimeout(() => document.addEventListener('click', _systemPopoverOutside), 0);
}
function closeSystemPopover() {
  const chip = document.getElementById('chipSystem');
  const pop  = document.getElementById('systemStatusPopover');
  pop.hidden = true;
  chip.setAttribute('aria-expanded', 'false');
  document.removeEventListener('keydown', _systemPopoverKeydown);
  document.removeEventListener('click', _systemPopoverOutside);
  chip.focus(); // restore focus (D-04)
}
function _systemPopoverKeydown(e) { if (e.key === 'Escape') closeSystemPopover(); }
function _systemPopoverOutside(e) {
  const chip = document.getElementById('chipSystem');
  const pop  = document.getElementById('systemStatusPopover');
  if (!pop.contains(e.target) && !chip.contains(e.target)) closeSystemPopover();
}
```

### Pattern 3: Pure worst-status rollup (STATUS-03 / D-07)
```javascript
// Source: synthesized from D-05/D-06/D-07 mapping; pure + unit-testable
const TIER_RANK = { green: 0, orange: 1, red: 2 };
// subsystems: [{name, tier}] where tier already encodes D-05/D-06
function computeRollup(subsystems) {
  let worst = { name: null, tier: 'green' };
  let failCount = 0;
  for (const s of subsystems) {
    if (TIER_RANK[s.tier] > TIER_RANK['green']) failCount++;
    if (TIER_RANK[s.tier] > TIER_RANK[worst.tier]) worst = s;
  }
  // "+N" overflow counts the OTHER non-green subsystems beyond the worst
  const overflow = Math.max(0, failCount - 1);
  return { tier: worst.tier, worstName: worst.name, overflow };
}
function chipLabel(rollup) {
  if (rollup.tier === 'green') return 'System';                 // D-10
  let label = `System: ${rollup.worstName}`;                    // D-11
  if (rollup.overflow > 0) label += ` +${rollup.overflow}`;     // D-11
  return label;
}
```
The D-05/D-06 nuance (Standby/Update→green) is encoded in `normalizeSubsystems` when it assigns each subsystem's `tier`, NOT in `computeRollup`. Keep that mapping in one place.

### Anti-Patterns to Avoid
- **Treating Standby/Update as orange in the rollup.** That re-introduces the alert-fatigue D-05/D-06 explicitly forbid; the collapsed chip must be green at rest. Standby/Update affect only the *row annotation*, never the *tier*.
- **Color-only status.** Every status MUST have a distinct icon shape AND a status word (STATUS-05). Never rely on `--green/--orange/--red` alone.
- **Focus trap on the popover.** It is non-modal; trapping focus is wrong and harms keyboard users.
- **Tearing down + rebuilding the popover DOM on every poll.** That would steal focus and break D-03's live update. Update text in place; only toggle visibility on open/close.
- **Touching `chipLLM`, `onLLMChipClick()`, `updateOllamaChip()`, or the `d.llm` branch.** STATUS-06 is a hard boundary.
- **`aria-live` storm.** Do not wrap the live-updating rows in an aggressive `aria-live="assertive"` — polls every 10 s would spam the SR. See § Live-Update SR considerations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Show/hide semantics | Custom `aria-*` guesswork | WAI-ARIA disclosure pattern (`role=button`, `aria-expanded`, `aria-controls`) | Standardized, SR-tested `[CITED: APG]` |
| Keyboard activation of the chip | New keydown listener | Existing `.status-chip.clickable` Enter/Space handler at `index.html:10405-10410` (add `system-chip` to its selector or the `.clickable` class) | Already correct; reuse |
| Escape-to-close | New global listener | Extend the existing Escape handler at `index.html:10389-10401` (add a System-popover branch alongside FOLIO/graph modals) | Single source of Escape handling |
| Fixed-position overlay above the header | New positioning math | Mirror the existing `data-tooltip` `position: fixed; top: 44px; z-index: 100` pattern at `index.html:570-583` | Proven in this exact header |
| Per-row status visual | New row component | Mirror `.folio-status-row` / `.folio-status-dot` at `index.html:1284-1296` | Established per-row status pattern |
| WCAG contrast checking | Eyeballing colors | `node scripts/contrast-audit.mjs` (+ extend it — see § Contrast Findings) | Deterministic, theme-aware |
| Theme colors | New hex literals | Existing CSS vars (`--green/--orange/--red/--surface2/--surface3/--border/--text/--text-dim/--accent`) | Three-theme correctness for free |

**Key insight:** Almost everything this phase needs already exists in the file in a slightly different form. The discipline is *reuse and refactor*, not *invent*. The only genuinely new logic is the pure `computeRollup`/`normalizeSubsystems` pair.

## Runtime State Inventory

This is a frontend refactor of presentation logic — but it touches DOM IDs and an event-handler selector that other code may reference, so a state check is warranted.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore stores chip IDs or status strings. Verified by scope (client-only). | None |
| Live service config | None — `/health` and `/health/detail` are read-only and unchanged. Verified in `backend/app/api/routes/health.py`. | None |
| OS-registered state | None. | None |
| Secrets/env vars | None. | None |
| Build artifacts | None — no build step (single-file frontend). | None |
| **DOM-ID / selector references (code-level)** | Removing `chipBackend`/`chipFolio`/`chipEmbedding`/`chipSpacy` and their `*Detail` IDs. `setChip('chipBackend'…)` etc. in `checkHealth()` (`index.html:4043-4126`). The `chipFolio` markup currently carries `onclick="openFolioModal()"` + gear (`index.html:2965-2970`) — this affordance MUST be re-homed into the popover FOLIO row (D-08), not lost. The `.status-chip.clickable` keydown registration (`index.html:10404`) currently binds `chipFolio` and `chipLLM`. | **Code edits:** (1) remove the 4 chip divs + add the System chip + popover; (2) rewrite the 4 subsystem branches of `checkHealth()` to use the new render functions while leaving the `d.llm` branch intact; (3) re-home the FOLIO Manage action; (4) ensure the new chip is wired to the disclosure toggle, not to `openFolioModal()`. Grep for `chipBackend`, `chipFolio`, `chipEmbedding`, `chipSpacy`, `chipBackendDetail` etc. across the file before deleting, to catch any other references. |

**Canonical question — after every file edit, what still references the old IDs?** Only `checkHealth()` and the `.status-chip.clickable` keydown selector should reference the old subsystem chips; both are in `index.html` and edited in this phase. There is no persisted or external reference. Verified by grep plan above.

## Common Pitfalls

### Pitfall 1: Light-theme green/orange icons fail 3:1 non-text contrast
**What goes wrong:** Status icons rendered as a solid `var(--green)` or `var(--orange)` fill look fine in Dark/Mixed but fail WCAG 1.4.11 (3:1 for graphical objects) in the Light theme.
**Why it happens:** Light theme green `#16a34a` on chip `#eceef4` = **2.84:1**; on popover `#e2e5ee` = **2.62:1**. Orange `#d97706` = **2.75:1 / 2.53:1**. Both < 3:1. `[VERIFIED: computed via scripts/contrast-audit.mjs contrastRatio()]`
**How to avoid:** Render each glyph with a **`var(--text)` stroke/outline** (Light `--text` = `#1a1d27` → **13–14:1**, easily ≥ 3:1) and use the status color as a secondary fill. The *shape* then carries the contrast in every theme; color is redundant reinforcement (which STATUS-05 wants anyway). Dark/Mixed green/orange/red and all-theme red already pass ≥ 3:1, so the stroke also harmonizes those.
**Warning signs:** A pure `fill="var(--green)"` SVG with no stroke; a passing Dark-theme screenshot but no Light-theme check.

### Pitfall 2: `contrast-audit.mjs` does not currently check status-icon contrast
**What goes wrong:** Running the audit returns "zero FAILs" yet the icons still fail 3:1, because the script only audits `--text/--text-dim/--accent` foregrounds on `--bg/--surface/--surface2/--surface3`, plus branch tints. It has **no** `--green/--orange/--red`-as-graphical-object check and uses the 4.5/3.0 *text* thresholds. `[VERIFIED: scripts/contrast-audit.mjs:99-115, 234-275]`
**Why it happens:** The script predates this phase's status-icon requirement.
**How to avoid:** Extend the audit (small, additive) to test `[--green, --orange, --red]` against `[--surface2 (chip), --surface3 (popover)]` at a **3:1** threshold across all themes, OR add an asserting unit test in `scripts/contrast-audit.test.mjs`. Also fix the stale hardcoded report path `03-accessibility-component-polish/03-AUDIT-REPORT.md` (`contrast-audit.mjs:200`) which points at a non-existent dir — should be the Phase 03 dir. Treat this as a planned task, not an afterthought.
**Warning signs:** Audit prints "0 failures" but you never see green/orange in the FAIL list because they were never tested.

### Pitfall 3: Live polls steal focus or spam the screen reader
**What goes wrong:** The 10 s `checkHealth` poll re-renders the popover while it's open; a naive rebuild moves focus to the top of the page, or an `aria-live` region announces unchanged status every 10 s.
**Why it happens:** D-03 requires live updates, but the existing poll fires regardless of popover state.
**How to avoid:** Update row text **in place** (set `textContent` on existing nodes; never replace the row container while focus is inside). Keep rows `aria-live="off"`; if a tier-change announcement is desired, use a single `aria-live="polite"` region that only updates when the *rollup tier* changes, not on every poll. (UI-SPEC § Interaction grants implementer discretion "within no announcement spam".)
**Warning signs:** Focus jumps when a poll lands; SR reads "Backend running" repeatedly.

### Pitfall 4: Losing a metric during consolidation (STATUS-04)
**What goes wrong:** A metric currently shown in a `setChip()` tooltip (e.g. "labels indexed", "vectors indexed", spaCy version) is dropped because the new row copy is rewritten from memory.
**Why it happens:** The metrics live in tooltip strings scattered through `checkHealth()` (`index.html:4043-4126`), not in a single model.
**How to avoid:** Use the § Metric Preservation Map below as the contract; copy each string's data verbatim into the row. Diff against the current tooltips during verification.
**Warning signs:** Popover FOLIO row shows concepts but not "labels indexed".

### Pitfall 5: Outside-click handler closes the popover on the opening click
**What goes wrong:** Registering the `document` click listener synchronously inside `openSystemPopover()` catches the same click that opened it → popover never opens.
**How to avoid:** Defer the outside-click listener with `setTimeout(…, 0)` (shown in Pattern 2), or check `e.target` against the chip.

## Code Examples

### Inline-SVG status glyphs (D-09, stroke-fallback for contrast)
```html
<!-- Source: hand-authored; stroke=currentColor carries 3:1, fill is status color.
     Set the SVG's color via CSS (.is-green{color:var(--green)} etc.) so currentColor
     drives the stroke; OR stroke="var(--text)" for the guaranteed-contrast outline. -->

<!-- Healthy: check in circle -->
<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
  <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
  <path d="M5 8.2 7 10.2 11 5.8" fill="none" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>

<!-- Warning: exclamation in triangle (reserved tier, D-07) -->
<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
  <path d="M8 2 14.5 13.5H1.5Z" fill="none" stroke="currentColor"
        stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M8 6.5V9.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
  <circle cx="8" cy="11.6" r="0.9" fill="currentColor"/>
</svg>

<!-- Error: cross in circle -->
<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false">
  <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
  <path d="M5.5 5.5 10.5 10.5 M10.5 5.5 5.5 10.5" stroke="currentColor"
        stroke-width="1.6" stroke-linecap="round"/>
</svg>
```
Notes: `aria-hidden="true"` + `focusable="false"` on every glyph (the status WORD provides the accessible text — STATUS-05). Three distinct silhouettes (round-check / triangle / cross) read in grayscale. To guarantee Light-theme 3:1, set the SVG `color` to `var(--text)` (drives `currentColor` stroke) and add the status hue as a thin secondary fill, OR keep stroke `var(--text)` and apply the status color only to a fill region — verify with the extended audit (Pitfall 2).

### Metric Preservation Map (STATUS-04 — copy verbatim from current tooltips)
```
Source strings: index.html:4043-4126 setChip() tooltips/details
Backend  ready    : "Running"                              (chip: green)        ← /health 200
Backend  offline  : "Offline — cannot reach backend"       (chip: red)          ← /health !ok
FOLIO    ready     : "{concepts} concepts, {labels_indexed} labels indexed" (green)   ← f.concepts, f.labels_indexed
FOLIO    standby   : "Standby — loads on first use"        (green; annotation)  ← f.status==='not_loaded'
FOLIO    update-av : "Update available" + existing note    (green; annotation)  ← update_status.update_available
FOLIO    updating  : "Updating…"                           (green; annotation)  ← update_status.update_in_progress
FOLIO    error     : "FOLIO error — {f.message}"           (red)                ← f.status==='error'
Embedding ready    : "{provider}, {index_size} vectors indexed" (green)         ← e.provider, e.index_size
Embedding standby  : "Standby — loads on first use"        (green; annotation)  ← e.status==='not_loaded'
Embedding error    : "Embedding error — {e.message}"       (red)                ← e.status==='error'
spaCy    ready     : "spaCy {version} — EntityRuler ready" (green)              ← s.version
spaCy    error     : "spaCy error — {s.message}"           (red)                ← s.status!=='ready'
```
Note the **status enum** from the backend (verified in `health.py`): every subsystem returns `status: "ready" | "not_loaded" | "error"`; FOLIO additionally nests `update_status.{update_in_progress, update_available, last_update_at, concepts_before, concepts_after}`. The toast-on-completed-update logic (`index.html:4074-4081`) must be **preserved** during the refactor (it uses `_lastFolioUpdateAt`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Four passive dots + label chips | One consolidated disclosure chip + popover | This phase | Less clutter, clear worst-status, relieves header overlap |
| Color-only status dot (`.chip-dot.green`) | Icon shape + status word | This phase (D-09/STATUS-05) | WCAG-AA non-color status |
| Native HTML `popover` attribute / Popover API | Available in modern browsers | ~2024 broad support | Not used here — manual `position: fixed` matches the existing `data-tooltip` pattern and avoids top-layer/focus-semantics changes in a no-build file. `[ASSUMED]` |

**Deprecated/outdated:** Nothing being removed is deprecated; the four-chip pattern is simply being consolidated by product decision.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Manual `position:fixed` show/hide is preferable to the native Popover API for this no-build file | Standard Stack / State of the Art | Low — both work; manual matches existing tooltip pattern. If planner prefers native `popover`, focus/dismiss semantics differ and must be re-derived. |
| A2 | Header in Mixed theme uses the dark (`:root`/`[data-theme="mixed"]`) tokens, so Mixed icon contrast = Dark | Contrast Findings | Low — verified the header is a top-level element; Mixed's light overrides apply to `.panel-right` only (`contrast-audit.mjs:217-219`). If a Mixed *light* surface ever hosts the chip, re-check green/orange. |
| A3 | No code outside `index.html` references the four subsystem chip IDs | Runtime State Inventory | Low — grep before delete (planned). If a test or script references them, update it. |

**Note:** Items A1–A3 are low-risk and verifiable during planning/execution; none block. All hard facts (contrast ratios, ARIA pattern, backend response shape, code anchors) are VERIFIED or CITED.

## Open Questions (RESOLVED)

1. **Exact glyph fill vs. stroke styling to clear 3:1 in Light theme.**
   - What we know: stroke at `var(--text)` clears 3:1 in all themes (computed); status color alone fails for Light green/orange.
   - What's unclear: whether ui-phase wants a fully-status-colored glyph (then stroke must dominate) or a neutral-stroke glyph with a small colored fill.
   - Recommendation: implement stroke=`var(--text)` + status-color secondary fill; verify with the extended audit; let ui-phase tune within that 3:1-safe envelope.
   - RESOLVED: stroke = var(--text), status color as secondary fill (per Pattern 3 + UI-SPEC + PATTERNS.md — enforced in 03-03 Task 2).

2. **Should a polite `aria-live` region announce rollup tier changes?**
   - What we know: D-03 requires live row updates; UI-SPEC grants discretion "within no announcement spam".
   - Recommendation: rows `aria-live="off"`; add ONE `aria-live="polite"` region that fires only when `computeRollup().tier` changes (e.g., a subsystem goes red). Cheap and avoids spam.
   - RESOLVED: popover rows use aria-live="off"; a single polite live region announces ONLY rollup tier changes (per Pitfall 3 + UI-SPEC Interaction Contract — implemented in 03-04).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `node` | `scripts/contrast-audit.mjs` (WCAG check) | ✓ (script is zero-dep, ran successfully this session) | system | — |
| Running backend (`/health/detail`) | Manual UAT + degraded-state sim | ✓ via `uvicorn … :8731` | — | Mock responses (§ Validation) for degraded states without real failures |
| Chrome DevTools MCP | Visual UAT across themes | per global CLAUDE.md | — | None mandated — global CLAUDE.md forbids headless fallback |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Degraded/errored subsystem states are hard to produce live (you'd have to break FOLIO) — mock `/health/detail` responses in the browser (override `fetch`, or a temporary local JSON) to drive the chip into red / multi-failure / +N states for UAT.

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node built-in test runner / assertion (existing `scripts/*.test.mjs` use `.test.mjs` siblings); plus manual UAT via Chrome DevTools MCP |
| Config file | none — test files are `scripts/contrast-audit.test.mjs`, `scripts/flags.test.mjs` run via `node --test` |
| Quick run command | `node --test scripts/` (runs the `.test.mjs` files) and `node scripts/contrast-audit.mjs` |
| Full suite command | `node --test scripts/` + `cd backend && .venv/bin/python -m pytest tests/ -v` (backend unchanged — should stay green as a regression guard) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATUS-02/03 | `computeRollup` returns green at rest; red when any errors; worst-of-four; correct `+N` | unit | `node --test scripts/system-rollup.test.mjs` | ❌ Wave 0 |
| STATUS-02/03 | `normalizeSubsystems` maps Standby/Update→green (D-05/D-06) | unit | `node --test scripts/system-rollup.test.mjs` | ❌ Wave 0 |
| STATUS-05 | Status-icon contrast ≥ 3:1 (green/orange/red on surface2/surface3) all themes | unit | `node --test scripts/contrast-audit.test.mjs` (extend) | ⚠️ exists, must extend |
| STATUS-05 | Body text in popover ≥ 4.5:1 all themes; report path correct | automated | `node scripts/contrast-audit.mjs` | ✅ (extend coverage + fix path) |
| STATUS-01/04/05/06/07 | Chip renders; popover opens/closes; metrics present; LLM untouched; no overlap; keyboard + SR | manual UAT | Chrome DevTools MCP across Dark/Light/Mixed (steps below) | n/a manual |

To make the pure logic unit-testable in a no-build file, extract `computeRollup`/`normalizeSubsystems`/`chipLabel` into a small **exported** form a `.test.mjs` can import — either a sibling `scripts/system-rollup.mjs` that `index.html` `<script type="module">`-imports, OR duplicate the pure functions into a test file. Prefer the importable module to avoid drift (mirrors `scripts/flags.mjs` ↔ `frontend` precedent — Phase 02 used `scripts/flags.mjs`).

### Sampling Rate
- **Per task commit:** `node --test scripts/` (rollup + contrast unit tests) — < 5 s.
- **Per wave merge:** `node scripts/contrast-audit.mjs` (zero FAILs incl. new status-icon pairs) + `node --test scripts/`.
- **Phase gate:** full suite green + manual UAT checklist complete across the three themes before `/gsd:verify-work`.

### Manual UAT checklist (for VALIDATION.md)
1. **Healthy/quiet-green (STATUS-02):** fresh load → chip shows check icon + "System", green; popover lists all 4 rows; FOLIO/Embedding show "Standby — loads on first use" but chip stays green.
2. **Expand/detail (STATUS-04):** click + Enter/Space both open; all metrics present (diff vs. § Metric Preservation Map); FOLIO row has "Manage FOLIO" → opens existing modal unchanged (D-08).
3. **Degraded (STATUS-03):** mock `/health/detail` with `spacy.status:"error"` → chip turns red, label "System: spaCy"; add a 2nd failure → "System: spaCy +1"; popover names all failures.
4. **Live update (D-03):** with popover open, let a poll change FOLIO Standby→ready → row + rollup update in place; focus not stolen; no SR spam.
5. **Accessibility (STATUS-05):** keyboard-only open/navigate/close (Enter/Space/Escape/outside-click/Tab); focus moves in on open, restores to chip on close; SR announces label + expanded state + each row "{Subsystem}: {status}, {metric}"; status conveyed by icon shape + word, not color.
6. **Contrast (STATUS-05):** `node scripts/contrast-audit.mjs` → zero FAILs; visually verify icons in **Light theme** specifically (Pitfall 1).
7. **LLM untouched (STATUS-06):** LLM chip still separate, still configures via `onLLMChipClick()`.
8. **No overlap (STATUS-07):** at the normal desktop header width, `#statusBar` does not overlap `#layerToggleBar` after a document loads (layer chips appear once `headerControls` is shown).

### Wave 0 Gaps
- [ ] `scripts/system-rollup.mjs` (+ `scripts/system-rollup.test.mjs`) — extract pure `computeRollup`/`normalizeSubsystems`/`chipLabel`; covers STATUS-02/03.
- [ ] Extend `scripts/contrast-audit.mjs` + `scripts/contrast-audit.test.mjs` — add status-icon 3:1 checks; fix stale report path (`contrast-audit.mjs:200`).
- [ ] No framework install needed (Node built-in test runner already used by existing `.test.mjs`).

## Security Domain

No `security_enforcement` key in `.planning/config.json` (treated as enabled), but this phase has a **minimal** security surface: frontend-only, no auth, no new endpoints, no user-supplied input persisted. The only relevant control:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation / Output Encoding | yes (lightly) | The popover renders values from `/health/detail` (`f.message`, `e.message`, `s.message`, provider names). Inject them via `textContent` / safe DOM APIs, **never** `innerHTML` with interpolated message strings, to avoid DOM-XSS from a backend error string. The existing `setChip` uses `textContent` (`index.html:4028`) — keep that discipline. |
| V2/V3/V4/V6 (auth/session/access/crypto) | no | No auth, session, access control, or crypto in a client-side status chip. |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected backend error string into DOM | Tampering / Info-disclosure | Render with `textContent`; do not `innerHTML` the `message` fields. |

## Sources

### Primary (HIGH confidence)
- `frontend/index.html` (codebase) — chip markup `:2960-2987`, `.status-chip` CSS `:536-584`, `.status-chip.clickable`/`.chip-gear` `:1270-1296`, `.folio-status-row` `:1284-1296`, `checkHealth()`/`setChip()` `:4021-4130`, Escape handler `:10389-10401`, chip keydown `:10404-10411`, theme tokens `:17-453`.
- `backend/app/api/routes/health.py` — `/health`, `/health/detail` response shapes and status enums (`ready`/`not_loaded`/`error`, FOLIO `update_status`).
- `scripts/contrast-audit.mjs` — what the audit covers (text tokens + branch tints), thresholds (4.5/3.0), stale report path `:200`.
- Computed contrast ratios (via `contrast-audit.mjs` `contrastRatio()`) — Light green/orange icons fail 3:1; Dark/Mixed pass; `--text` stroke clears 3:1 everywhere.
- WAI-ARIA APG, Disclosure pattern — https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/ (role=button, aria-expanded, aria-controls, Enter/Space).
- WAI-ARIA APG, Dialog (Modal) pattern — https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ (focus trap is modal-only).

### Secondary (MEDIUM confidence)
- Access & Use, Non-modal dialogs — https://accessuse.eu/en/non-modal-dialogs.html (DOM placement after trigger, focus-in optional, close on outside-click/focus-out/Escape, no focus trap).

### Tertiary (LOW confidence)
- Native Popover API maturity (background only; not used) — general ecosystem knowledge `[ASSUMED]`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all platform primitives verified present in the file; no packages.
- Architecture / refactor: HIGH — exact code anchors and the backend response shape verified.
- Accessibility pattern: HIGH — grounded in WAI-ARIA APG + non-modal-dialog guidance.
- Contrast findings: HIGH — ratios computed with the repo's own audit math.
- Pitfalls: HIGH — Pitfalls 1 & 2 are computed/verified, not assumed.

**Research date:** 2026-05-22
**Valid until:** 2026-06-21 (stable; ARIA patterns and the codebase change slowly)
