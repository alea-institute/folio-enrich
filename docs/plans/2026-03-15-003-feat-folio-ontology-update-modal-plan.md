---
title: "feat: FOLIO Ontology Update Modal"
type: feat
status: completed
date: 2026-03-15
---

# feat: FOLIO Ontology Update Modal

## Overview

Make the FOLIO status chip in the header clickable, opening a dedicated modal dialog for managing FOLIO OWL ontology updates. The modal shows ontology stats (concept/label/property counts, file size), update status, and provides controls to check for updates from the GitHub repo, apply them, and rollback. The backend for all of this already exists — this is primarily a frontend feature with minor backend extensions.

## Problem Statement / Motivation

The FOLIO update functionality is currently buried inside the Settings modal as a small subsection. Users have no obvious way to discover it. The FOLIO chip in the header is passive — it shows status but isn't interactive. Making it clickable provides a natural, discoverable entry point for ontology management, following the same pattern as the LLM chip (which opens the Ollama setup wizard).

## Proposed Solution

1. **Make `#chipFolio` clickable** — add `clickable` class, click handler, keyboard accessibility
2. **Build a FOLIO modal** — new modal dialog following existing Settings/Ollama modal patterns
3. **Extend `/folio/update/status` API** — add label_count, property_count to response
4. **Fix `ensure_owl_fresh()` silent failure** — raise exceptions so errors surface in the UI
5. **Remove duplicate FOLIO section from Settings** — replace with a link to the new modal
6. **Auto-save settings** — toggle/interval changes save immediately via debounced POST

## Technical Considerations

### Architecture

All changes are within the existing architecture — no new services, no new dependencies.

- **Frontend**: `frontend/index.html` — new modal HTML + JS functions
- **Backend route**: `backend/app/api/routes/folio_update.py` — extend status response
- **Backend service**: `backend/app/services/folio/owl_cache.py` — fix silent failure bug
- **Backend service**: `backend/app/services/folio/folio_service.py` — expose label/property counts

### Existing Backend Endpoints (already built)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/folio/update/status` | GET | Current status + cache info |
| `/folio/update/check` | POST | HEAD probe to GitHub for freshness |
| `/folio/update/apply` | POST | Download + validate + reload |
| `/folio/update/rollback` | POST | Swap to previous version + reload |

### Key Design Decisions

1. **Modal (not page/drawer)** — consistent with Settings and Ollama modals
2. **Apply uses blocking POST + spinner** — simpler than adding SSE; show "This may take a minute" text. Revisit SSE if user feedback demands it.
3. **Pre-check job count before apply** — fetch `/health` to check active jobs; warn user if jobs are running ("Update will wait for N active jobs to finish")
4. **Auto-save settings** — toggle and interval changes save immediately (debounced 500ms) via existing `POST /settings`
5. **Remove FOLIO section from Settings modal** — replace with a single "Manage FOLIO Ontology" link/button that opens the new modal
6. **Inline rollback confirmation** — button text changes to "Confirm Rollback?" with red styling, reverts after 3s of inaction
7. **ETag hidden by default** — show under a "Technical Details" collapsible section, truncated to 8 chars with full value in tooltip

## System-Wide Impact

- **Interaction graph**: Chip click → modal open → `GET /folio/update/status`. Check → `POST /folio/update/check`. Apply → `POST /folio/update/apply` → backend waits for idle pipeline → `FolioService._reload()` → rebuilds label caches + embedding index. The existing `checkHealth()` polling loop also updates the chip independently.
- **Error propagation**: `ensure_owl_fresh()` currently swallows errors silently → fix to raise so `_do_apply()` catches and sets `_status.error` → API returns error message → modal displays it.
- **State lifecycle risks**: If modal is closed during an in-progress apply, the backend continues. Re-opening the modal re-fetches status, which reflects the completed state. No orphaned state.
- **API surface parity**: The `/folio/update/status` endpoint gains two new fields (`label_count`, `property_count`). Backward compatible (additive).
- **Post-update stale results**: After apply/rollback, existing enrichment results reference old ontology. Add a subtle banner: "Ontology updated since this document was enriched. Re-enrich for latest annotations."

## Acceptance Criteria

### Phase 1: Backend Fixes (minor)

- [x] **Extend status endpoint** — `GET /folio/update/status` returns `label_count` and `property_count` from `FolioService` caches (`folio_update.py`)
- [x] **Fix silent failure** — `ensure_owl_fresh()` raises on download failure or XML validation failure (`owl_cache.py`)
- [x] **Surface errors in apply** — `_do_apply()` catches exceptions from `ensure_owl_fresh()` and sets `_status.error` (`owl_updater.py`)
- [x] **Tests pass** — existing 17 tests (11 updater + 6 route) still pass; add tests for new error paths

### Phase 2: Frontend — Chip + Modal Structure

- [x] **Make chip clickable** — add `clickable` class, `onclick="openFolioModal()"`, `tabindex="0"`, `role="button"`, `aria-label` to `#chipFolio`
- [x] **Add gear icon** — match the LLM chip pattern with a gear span indicator
- [x] **Create modal HTML** — new `#folioModal` with overlay, following existing modal structure:
  - Header: "FOLIO Ontology" title + close button
  - Status section: colored dot + status text (Up to date / Update Available / Updating / Error)
  - Stats grid: concept count, label count, property count, OWL file size
  - Timestamps: last checked, last updated (relative time format)
  - Action buttons: Check Now, Apply Update, Rollback
  - Settings: auto-check toggle + interval
  - Collapsible "Technical Details": ETag (truncated), cache path
- [x] **Modal open/close** — Escape key closes, overlay click closes, close button closes; re-fetches status on every open

### Phase 3: Frontend — Modal Logic

- [x] **`openFolioModal()`** — fetches `GET /folio/update/status`, populates modal, shows it
- [x] **`checkFolioUpdateFromModal()`** — calls `POST /folio/update/check`, shows spinner on button, updates status on response
- [x] **`applyFolioUpdateFromModal()`** — pre-checks active jobs via `/health`, warns if jobs running, calls `POST /folio/update/apply`, shows progress state, updates stats + chip on success, shows concept delta toast
- [x] **`rollbackFolioFromModal()`** — inline two-step confirmation, calls `POST /folio/update/rollback`, refreshes modal + chip
- [x] **Auto-save settings** — toggle and interval changes debounced-save via `POST /settings`
- [x] **Button state management**:
  - Apply visible only when `update_available === true`
  - Rollback visible only when `has_previous_version === true`
  - All buttons disabled when `update_in_progress === true`
  - Check Now disabled during check request
- [x] **Error display** — network failures, download failures, validation failures, pipeline-busy timeout all show clear error messages in the modal

### Phase 4: Cleanup

- [x] **Remove FOLIO section from Settings modal** — replace `#folioUpdateSection` (lines 2736-2752) with a single "Manage FOLIO Ontology" button that calls `openFolioModal()`
- [ ] **Stale results banner** — after ontology update, show banner in results panel if results were generated with previous ontology version
- [x] **Keyboard accessible** — chip focusable via Tab, activatable via Enter/Space; modal traps focus while open

## Success Metrics

- FOLIO chip click → modal opens in <200ms (no perceptible delay)
- Check operation completes in <2s (HEAD request only)
- Apply operation succeeds with clear progress feedback
- Zero duplicate FOLIO update UI (Settings section replaced)
- All existing tests pass + new error-path tests added

## Dependencies & Risks

- **No new dependencies** — all backend infrastructure exists
- **Risk: Apply timeout** — if jobs never finish within 5min, apply fails. Mitigation: pre-check warns user about active jobs
- **Risk: Large OWL file on slow connection** — ~18MB download with no progress bar. Mitigation: "This may take a minute" text; revisit SSE streaming if users report issues
- **Risk: Stale enrichment results** — post-update annotations reference old ontology. Mitigation: subtle banner suggesting re-enrichment

## Implementation Notes

### Files to modify

| File | Changes |
|------|---------|
| `frontend/index.html` | New modal HTML, chip click handler, modal JS functions, remove Settings FOLIO section |
| `backend/app/api/routes/folio_update.py` | Extend status response with label_count, property_count |
| `backend/app/services/folio/owl_cache.py` | Fix `ensure_owl_fresh()` to raise on failure |
| `backend/app/services/folio/owl_updater.py` | Catch exceptions in `_do_apply()`, set error status |
| `backend/app/services/folio/folio_service.py` | Add `get_label_count()`, `get_property_count()` methods |
| `backend/tests/test_owl_updater.py` | Add error-path tests |
| `backend/tests/test_folio_update_routes.py` | Add test for extended status response |

### Modal HTML skeleton (pseudo-code)

```html
<!-- FOLIO Ontology Modal -->
<div id="folioModal" class="modal-overlay" style="display:none">
  <div class="modal-content" style="max-width:520px">
    <div class="modal-header">
      <h2>FOLIO Ontology</h2>
      <button class="modal-close" onclick="closeFolioModal()">&times;</button>
    </div>
    <div class="modal-body">
      <!-- Status indicator -->
      <div id="folioModalStatus"><!-- dot + text --></div>
      <!-- Stats grid -->
      <div class="folio-stats-grid">
        <div>Concepts: <span id="folioConceptCount">--</span></div>
        <div>Labels: <span id="folioLabelCount">--</span></div>
        <div>Properties: <span id="folioPropCount">--</span></div>
        <div>File size: <span id="folioOwlSize">--</span></div>
      </div>
      <!-- Timestamps -->
      <div class="folio-timestamps">
        <div>Last checked: <span id="folioLastChecked">--</span></div>
        <div>Last updated: <span id="folioLastUpdated">--</span></div>
      </div>
      <!-- Action buttons -->
      <div class="folio-actions">
        <button id="btnFolioCheck" onclick="checkFolioUpdateFromModal()">Check Now</button>
        <button id="btnFolioApply" onclick="applyFolioUpdateFromModal()" style="display:none">Apply Update</button>
      </div>
      <!-- Rollback -->
      <button id="btnFolioRollback" onclick="rollbackFolioFromModal()" style="display:none">Rollback</button>
      <!-- Auto-check settings -->
      <div class="folio-auto-settings">
        <label><input type="checkbox" id="folioAutoCheck"> Auto-check every
          <input type="number" id="folioCheckInterval" min="1" max="168" value="24"> hours</label>
      </div>
      <!-- Technical details (collapsible) -->
      <details><summary>Technical Details</summary>
        <div>ETag: <code id="folioEtag">--</code></div>
      </details>
      <!-- Error display -->
      <div id="folioModalError" style="display:none"></div>
    </div>
  </div>
</div>
```

### Existing patterns to follow

- **LLM chip click** → `onLLMChipClick()` at `frontend/index.html` — same clickable chip pattern
- **Settings modal** → `openSettingsModal()` / `closeSettingsModal()` — same open/close/overlay pattern
- **Ollama wizard modal** → `#ollamaSetupModal` — same structure for status + action buttons
- **`checkFolioUpdate()`** (line ~3606) — existing check+apply logic to reuse/adapt
- **`setChip()`** function — existing chip state management
- **`showToast()`** function — existing notification pattern

## Sources & References

### Internal References

- FOLIO update manager: `backend/app/services/folio/owl_updater.py`
- OWL cache layer: `backend/app/services/folio/owl_cache.py`
- FolioService singleton: `backend/app/services/folio/folio_service.py`
- Update API routes: `backend/app/api/routes/folio_update.py`
- Frontend FOLIO chip: `frontend/index.html:2389`
- Frontend Settings FOLIO section: `frontend/index.html:2736-2752`
- Frontend check function: `frontend/index.html:3606`
- Existing tests: `backend/tests/test_owl_updater.py`, `backend/tests/test_folio_update_routes.py`

### External References

- FOLIO OWL source: `https://github.com/alea-institute/FOLIO` (main branch)
- folio-python library: `https://github.com/alea-institute/folio-python`
