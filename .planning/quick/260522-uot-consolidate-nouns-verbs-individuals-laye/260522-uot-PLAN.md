---
phase: quick-260522-uot
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [frontend/index.html]
autonomous: true
requirements: [UOT-ANNOT-CHIP]
must_haves:
  truths:
    - "Header shows [System] [LLM] [Annotations ▾] [Parts of Speech] — the three standalone Nouns/Verbs/Individuals chips are gone"
    - "Clicking the Annotations chip opens an anchored popover containing three toggle rows (Nouns, Verbs, Individuals)"
    - "Clicking a row toggles that layer in place (highlight on/off, document spans show/hide) without closing the popover or stealing focus"
    - "The Annotations chip label reflects how many of the 3 layers are active (e.g. 'Annotations (2/3)')"
    - "Toggling layers still persists to localStorage('activeLayers') and survives reload"
    - "Parts of Speech chip + #posLegend remain a separate chip and behave exactly as before"
    - "Popover is keyboard accessible: opens via Enter/Space, closes on Escape/outside-click/re-activation, focus moves in on open and restores to chip on keyboard close"
  artifacts:
    - path: "frontend/index.html"
      provides: "Annotations disclosure chip markup, popover CSS, open/close/toggle + summary-render JS"
      contains: "annotationsPopover"
  key_links:
    - from: "#chipAnnotations"
      to: "toggleAnnotationsPopover()"
      via: "click listener + .status-chip.clickable keydown"
      pattern: "chipAnnotations.*addEventListener"
    - from: "popover toggle rows"
      to: "toggleLayer('concepts'/'properties'/'individuals', this)"
      via: "onclick, unchanged semantics"
      pattern: "toggleLayer\\('(concepts|properties|individuals)'"
    - from: "toggleLayer()"
      to: "renderAnnotationsSummary()"
      via: "summary recompute after each toggle"
      pattern: "renderAnnotationsSummary"
---

<objective>
Consolidate the three standalone layer chips (Nouns / Verbs / Individuals) in the
header into ONE "Annotations ▾" disclosure chip that opens an anchored popover
containing the three toggles. The existing "Parts of Speech" chip + #posLegend
stay as a separate, untouched chip.

Mirror the already-shipped Phase 03 "System" chip disclosure pattern
(openSystemPopover / closeSystemPopover / toggleSystemPopover, .system-popover CSS,
.status-chip.clickable keydown). Reuse the proven pattern; do not invent a new one.

Purpose: reduce header chip clutter while keeping all three toggles one click away
and preserving toggleLayer() semantics + localStorage persistence exactly.
Output: edited frontend/index.html (markup + CSS + JS). No backend, no new deps.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md

<interfaces>
<!-- Everything below is already in frontend/index.html. Use directly; the popover MUST
     mirror the System chip pattern. No codebase exploration needed. -->

Final desired header order inside the layer-toggle-bar (#layerToggleBar):
  [Annotations ▾ chip + its popover]  [layer-divider]  [Parts of Speech chip]  [#posLegend]
(The [System] [LLM] chips live in a different group, #headerStatus, and are unchanged.)

CURRENT layer-toggle-bar markup to REPLACE (frontend/index.html ~3105-3126):
  - .layer-chip.active data-layer="concepts" onclick="toggleLayer('concepts', this)"  →  "Nouns"  (--accent / blue dot)
  - .layer-chip.active data-layer="properties" onclick="toggleLayer('properties', this)"  →  "Verbs" (--purple dot)
  - .layer-chip.active data-layer="individuals" onclick="toggleLayer('individuals', this)"  →  "Individuals" (--individual-citation dot)
  - .layer-divider
  - .layer-chip data-layer="pos" onclick="toggleLayer('pos', this)"  →  "Parts of Speech"  ← KEEP UNTOUCHED
  - .pos-legend#posLegend  ← KEEP UNTOUCHED

toggleLayer (frontend/index.html ~7163) — DO NOT change its semantics:
  function toggleLayer(layer, chipEl) {
    // adds/removes layer from _activeLayers, calls chipEl.classList.toggle('active'),
    // localStorage.setItem('activeLayers', ...), _applyLayerVisibility(), pos re-render.
  }
  NOTE: it mutates chipEl.classList — so the popover rows for concepts/properties/individuals
  should themselves be the `.layer-chip[data-layer=...]` elements (keeps .active styling working).

_syncViewMode (~7204) and _restoreViewPrefs (~7143) both sync via
  document.querySelectorAll('.layer-chip[data-layer]') → chip.classList.toggle('active', _activeLayers.has(layer))
  so the popover rows MUST keep class `layer-chip` + `data-layer` to stay in sync on load/render.

System chip pattern to MIRROR (frontend/index.html):
  - Markup (~3060): <div class="status-chip system-chip clickable" id="chipSystem"
        role="button" tabindex="0" aria-haspopup="true" aria-expanded="false"
        aria-controls="systemStatusPopover" aria-label="System status"> … </div>
    immediately followed by <div class="system-popover" id="systemStatusPopover" role="region"
        aria-label="System status detail" tabindex="-1" hidden> … rows … </div>
  - CSS (~1331): .system-popover { position:fixed; top:44px; background:var(--surface3);
        border:1px solid var(--border); border-radius:6px; box-shadow:0 6px 20px rgba(0,0,0,.25);
        z-index:100; min-width:240px; max-width:calc(100vw - 16px); padding:0; }
        .system-popover[hidden]{display:none} .system-popover:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
        .system-status-row{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--border)}
        .system-status-row:last-child{border-bottom:none}
  - JS (~4213): _systemPopoverOpen flag + _systemOutsideClickHandler;
        openSystemPopover(): pop.hidden=false; chip aria-expanded=true; anchor left via
          rect=chip.getBoundingClientRect(); maxLeft=innerWidth-pop.offsetWidth-8;
          pop.style.left=Math.round(Math.max(8,Math.min(rect.left,maxLeft)))+'px';
          pop.focus(); deferred (setTimeout 0) document click listener that calls close(false)
          when click is outside both pop and chip (WR-01 outside-click passes restoreFocus=false; Pitfall 5 defer).
        closeSystemPopover(restoreFocus=true): pop.hidden=true; aria-expanded=false; remove listener;
          if (restoreFocus && chip) chip.focus().
        toggleSystemPopover(): open if closed else close.
  - Keydown (~10757): document.querySelectorAll('.status-chip.clickable') → Enter/Space → e.preventDefault(); chip.click().
        Re-querying after we add the new chip is NOT needed if the new chip ALSO has classes
        `status-chip clickable` AND this querySelectorAll block runs at load AFTER the markup exists
        (it does — script is at end of body). Verify the new chip carries `status-chip clickable`.
  - Click wiring (~10768): IIFE adds chipSystem.addEventListener('click', toggleSystemPopover).
        Add an analogous IIFE for chipAnnotations → toggleAnnotationsPopover.
  - Escape: confirm whether a global keydown closes the System popover on Escape; if a shared
    document 'keydown' Escape handler exists, extend it to also close the annotations popover,
    otherwise add a minimal Escape handler for the annotations popover mirroring the System one.

layer-chip CSS (~1881) already styles the colored dots per data-layer — reuse as-is for popover rows.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace the three standalone chips with an Annotations disclosure chip + popover (markup + CSS)</name>
  <files>frontend/index.html</files>
  <action>
    In #layerToggleBar (~3105-3126): REMOVE the three standalone .layer-chip elements for
    data-layer="concepts" (Nouns), "properties" (Verbs), "individuals" (Individuals).
    Do NOT touch the .layer-divider, the data-layer="pos" "Parts of Speech" chip, or #posLegend —
    leave them in place so the final order is [Annotations ▾] [divider] [Parts of Speech] [#posLegend].

    Insert, as the FIRST child of #layerToggleBar, a disclosure chip mirroring #chipSystem:
      a trigger element with classes `status-chip clickable` (so it inherits the existing
      .status-chip.clickable keydown Enter/Space handler), id="chipAnnotations",
      role="button", tabindex="0", aria-haspopup="true", aria-expanded="false",
      aria-controls="annotationsPopover", aria-label="Annotations layers".
      Inside it: a caret/▾ affordance and a <span class="chip-label" id="chipAnnotationsLabel">Annotations</span>
      (label text is recomputed by JS in Task 2 — initial text "Annotations" is fine).
      Mirror the System chip's caret/disclosure affordance styling so it visually reads as expandable.

    Immediately after the chip (source order, so SR users reach it naturally), add:
      <div class="annotations-popover" id="annotationsPopover" role="region"
           aria-label="Annotation layers" tabindex="-1" hidden> … three rows … </div>
    Each row is the MOVED layer chip kept as `.layer-chip[data-layer=...]` so toggleLayer's
    chipEl.classList.toggle('active') and the _syncViewMode/_restoreViewPrefs querySelectorAll
    keep working unchanged:
      Row 1: <span class="layer-chip active" data-layer="concepts" onclick="toggleLayer('concepts', this)" title="Classes"><span class="chip-dot"></span>Nouns</span>
      Row 2: <span class="layer-chip active" data-layer="properties" onclick="toggleLayer('properties', this)" title="Properties"><span class="chip-dot"></span>Verbs</span>
      Row 3: <span class="layer-chip active" data-layer="individuals" onclick="toggleLayer('individuals', this)"><span class="chip-dot"></span>Individuals</span>
    (Keep the existing `active` class presence — _restoreViewPrefs re-syncs it on load anyway.)
    Lay the rows out vertically inside the popover with comfortable row padding so each is a
    full-width clickable target; reuse the existing .layer-chip dot/color styling for the dot + name.

    Add CSS mirroring .system-popover for a new .annotations-popover selector:
      position:fixed; top:44px; background:var(--surface3); border:1px solid var(--border);
      border-radius:6px; box-shadow:0 6px 20px rgba(0,0,0,.25); z-index:100; min-width:200px;
      max-width:calc(100vw - 16px); padding:6px;  /* small padding so rows breathe (WR-04 clamp handled in JS) */
      .annotations-popover[hidden]{display:none}
      .annotations-popover:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
      Make each row display:flex full-width with ~6-8px vertical rhythm; keep :focus-visible rings
      on interactive elements (never bare outline:none — WCAG 2.4.7).
    Add a :focus-visible ring for the new #chipAnnotations (mirror .system-chip:focus-visible).
    Do NOT place any fenced code execution here — this is markup + CSS only.
  </action>
  <verify>
    <automated>cd "/home/damienriehl/Coding Projects/folio-enrich" && grep -c 'id="chipAnnotations"' frontend/index.html | grep -qx 1 && grep -c 'id="annotationsPopover"' frontend/index.html | grep -qx 1 && grep -q 'aria-controls="annotationsPopover"' frontend/index.html && grep -q 'class="annotations-popover"' frontend/index.html && grep -q 'data-layer="pos"' frontend/index.html && echo PASS</automated>
  </verify>
  <done>
    The three standalone Nouns/Verbs/Individuals chips no longer appear directly in #layerToggleBar;
    a #chipAnnotations disclosure chip + #annotationsPopover (containing the three layer-chip rows)
    exist; the Parts of Speech chip, .layer-divider, and #posLegend are unchanged; .annotations-popover
    CSS mirrors .system-popover.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire the disclosure JS (open/close/toggle, click + keyboard + Escape + outside-click) and the active-count summary</name>
  <files>frontend/index.html</files>
  <action>
    Add JS mirroring the System disclosure (near the System functions ~4213-4262, or in a clearly
    labeled block). Implement:
      let _annotationsPopoverOpen = false; let _annotationsOutsideClickHandler = null;
      openAnnotationsPopover(): get #annotationsPopover + #chipAnnotations; pop.hidden=false;
        chip.setAttribute('aria-expanded','true'); _annotationsPopoverOpen=true;
        anchor left exactly like openSystemPopover (getBoundingClientRect + maxLeft = innerWidth - pop.offsetWidth - 8;
        pop.style.left = Math.round(Math.max(8, Math.min(rect.left, maxLeft))) + 'px') — WR-04 clamp;
        pop.focus(); register a DEFERRED (setTimeout 0) document click listener that calls
        closeAnnotationsPopover(false) when the click is outside BOTH pop and chip
        (Pitfall 5 defer; WR-01 outside-click passes restoreFocus=false so focus is not yanked back).
      closeAnnotationsPopover(restoreFocus = true): pop.hidden=true; chip aria-expanded=false;
        _annotationsPopoverOpen=false; remove + null the outside-click listener;
        if (restoreFocus && chip) chip.focus()  — restore focus ONLY for keyboard/Escape/re-activation.
      toggleAnnotationsPopover(): open if closed else close.
    Wire the chip: add an IIFE mirroring the chipSystem one —
      const c = document.getElementById('chipAnnotations'); if (c) c.addEventListener('click', toggleAnnotationsPopover);
    Enter/Space already work IF #chipAnnotations carries classes `status-chip clickable` (verify Task 1 did this) —
      the ~10757 querySelectorAll('.status-chip.clickable') block runs at end of body and attaches keydown→click.
    Escape: find how the System popover closes on Escape. If there is a shared document 'keydown' Escape
      handler that closes open popovers/modals, extend it to also call closeAnnotationsPopover() when
      _annotationsPopoverOpen. If System uses its own minimal Escape handler, add an equivalent for annotations.
      Re-activation (clicking the chip while open) already closes via toggle.

    Active-count summary:
      Add renderAnnotationsSummary() that counts how many of ['concepts','properties','individuals']
      are in _activeLayers and sets #chipAnnotationsLabel textContent (textContent only — no innerHTML)
      to a concise summary, e.g. "Annotations (N/3)" (or just "Annotations" when all 3 on — your call,
      keep it simple). It is a count, NOT a worst-status rollup.
      Call renderAnnotationsSummary() (a) once at load after _restoreViewPrefs/_syncViewMode set state,
      and (b) at the END of toggleLayer() so flipping any of the three layers updates the summary live.
      Guard the call so toggleLayer('pos', ...) does not break — the function just recounts the three
      annotation layers and ignores 'pos'. Clicking a row must NOT close the popover or steal focus
      (toggleLayer mutates the row's own classList in place; do not add any popover teardown to it).
    No fenced code execution blocks in markup; this is plain JS in the existing <script>.
  </action>
  <verify>
    <automated>cd "/home/damienriehl/Coding Projects/folio-enrich" && grep -q 'function openAnnotationsPopover' frontend/index.html && grep -q 'function closeAnnotationsPopover' frontend/index.html && grep -q 'function toggleAnnotationsPopover' frontend/index.html && grep -q "chipAnnotations').addEventListener\|getElementById('chipAnnotations'" frontend/index.html && grep -q 'function renderAnnotationsSummary' frontend/index.html && grep -q 'restoreFocus' frontend/index.html && echo PASS</automated>
  </verify>
  <done>
    Clicking #chipAnnotations (or Enter/Space) opens/closes the popover; Escape, outside-click, and
    re-activation close it; outside-click does not steal focus back (restoreFocus=false) while
    keyboard/Escape close restores focus to the chip; popover is left-anchored + viewport-clamped;
    each row toggles its layer in place via the unchanged toggleLayer(); the chip label updates to an
    active-count summary at load and after every toggle of the three annotation layers.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    The header now shows [System] [LLM] [Annotations ▾] [Parts of Speech]. The three layer toggles
    moved into a click-to-expand "Annotations" popover that mirrors the System chip disclosure; the
    Parts of Speech chip + legend are untouched; the Annotations label shows an active-layer count.
  </what-built>
  <how-to-verify>
    1. Start the frontend (frontend/index.html via the project's usual static serve; backend on :8731 if needed)
       and load a document so the annotated text + header controls are visible.
    2. Confirm the header reads [System] [LLM] [Annotations ▾] [Parts of Speech] — no standalone
       Nouns/Verbs/Individuals chips remain.
    3. Click "Annotations ▾" → popover opens anchored under the chip with three rows (Nouns, Verbs,
       Individuals), each showing its colored dot and on/off state.
    4. Click each row in turn → the corresponding annotation spans in the document show/hide and the
       row's highlight flips, WITHOUT the popover closing. The "Annotations (N/3)" label updates live.
    5. Reload the page → your on/off choices persist (localStorage('activeLayers')).
    6. Keyboard: Tab to the Annotations chip, press Enter/Space to open, Tab into rows, toggle with
       Enter/Space, press Escape → popover closes and focus returns to the chip. Confirm visible
       :focus-visible rings (no bare outline removal). Click outside → popover closes without focus jumping back.
    7. Confirm "Parts of Speech" still toggles the spaCy POS overlay + legend exactly as before.
  </how-to-verify>
  <resume-signal>Type "approved" or describe issues</resume-signal>
</task>

</tasks>

<verification>
- grep checks in Task 1 & 2 confirm the new markup, CSS, and JS functions exist and the POS chip remains.
- Manual checkpoint confirms disclosure behavior, in-place toggling, persistence, keyboard a11y, and POS untouched.
- No backend changes; no new dependencies; single-file frontend edit only.
</verification>

<success_criteria>
- Header shows [System] [LLM] [Annotations ▾] [Parts of Speech]; the three standalone chips are gone.
- Annotations chip opens an anchored, viewport-clamped popover with three working in-place toggles.
- toggleLayer() semantics and localStorage('activeLayers') persistence are unchanged.
- Parts of Speech chip + #posLegend are untouched and still functional.
- Popover is keyboard accessible (Enter/Space open, Escape/outside-click/re-activation close, focus
  in-on-open + restore-on-keyboard-close, :focus-visible rings).
- Annotations label reflects the active-layer count.
</success_criteria>

<output>
Create `.planning/quick/260522-uot-consolidate-nouns-verbs-individuals-laye/260522-uot-SUMMARY.md` when done
</output>
