---
title: Fast Gold Annotation - Plan
type: feat
date: 2026-10-26
topic: fast-gold-annotation
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Fast Gold Annotation - Plan

## Goal Capsule

- **Objective:** Damien validates or annotates a gold record (Palsgraf first) at the speed of reading: one keystroke or one swipe per proposition, with no waiting on saves and no lost work, on a laptop or a phone.
- **Product authority:** Damien, inline on 2026-10-26: "make that annotation (e.g., rejecting, editing, adding) as easy and fast for me as possible." Builds on `docs/plans/2026-10-03-2355-feat-gold-human-validation-plan.md`, whose rule stands: every item gets a deliberate action, with no bulk approve-all.
- **Execution profile:** one branch (`feat/fast-gold-annotation`), worker-implemented, orchestrator-verified in a real browser, merged and deployed to DEV under standing authorization.
- **Stop conditions:** any change that weakens the one-deliberate-action-per-item rule, or that lets a failed save look saved, stops.
- **Open blockers:** none.

---

## Product Contract

### Summary

The validation workspace becomes keyboard-first and touch-first. Approve, discard, and type changes advance instantly while saves run in the background, an undo key reverses the last action, a missed proposition is added by selecting its text, and one link opens Damien straight into his pending validation session.

### Problem Frame

The Palsgraf validation session on DEV holds 104 unreviewed AI annotations. Today each action waits for the save round trip, a session refresh, and a full re-render before the next item appears. Editing a type means tabbing into a form, adding a missed proposition takes several clicks, and the phone layout has small buttons and no gestures. Damien works mostly through Remote Control on a phone, so every extra tap and every wait multiplies across 104 items.

### Requirements

**Speed**

- R1. Approve, discard, and type-change actions advance to the next unreviewed item immediately; the save runs in the background.
- R2. A failed background save stays visibly unsaved on its item, retries on request, and blocks export until it succeeds.
- R3. One key reverses the most recent action, including a background save already completed.

**Editing**

- R4. Number keys set the proposition type from the card's visible, numbered type list.
- R5. Keys move the span's start and end by one word in either direction, and the card shows the new quote immediately.
- R6. Selecting text in the document pane offers "Add as proposition", which creates a hand-added item with that span and focuses its type.

**Navigation and access**

- R7. The workspace shows progress (reviewed of total) and jumps to the next unreviewed item; reopening the session resumes there.
- R8. A link of the form `/?job=<job_id>&tab=propositions` opens the pending validation session directly, switching on annotation mode when access is authorized.
- R9. A help overlay lists every shortcut and gesture.

**Phone**

- R10. On narrow screens a fixed bottom bar carries large Approve, Edit, Discard, and Undo controls, and a swipe right approves while a swipe left discards.

### Acceptance Examples

- AE1. **Covers R1, R2.** With the network throttled, pressing A five times shows five successive items without waiting; when one save fails, that item shows "Not saved — retry" and Export is disabled until the retry succeeds.
- AE2. **Covers R3.** After discarding an item by mistake, pressing Z restores it to unreviewed, both on screen and on the server.
- AE3. **Covers R6.** Selecting "the risk reasonably to be perceived defines the duty to be obeyed" in the document pane and choosing "Add as proposition" creates a hand-added item whose quote equals the selection.
- AE4. **Covers R10.** At 390 px width, a right swipe on the item approves it and advances; the bottom bar stays visible while scrolling the quote.

### Scope Boundaries

- **Not built:** bulk approve-all, per the validation plan's honesty rule.
- **Not built:** server-side changes beyond what undo and resume need; the gold session API already records outcomes.
- **Deferred:** the unified-record tag editing in `docs/plans/2026-10-26-0700-feat-unified-proposition-engine-plan.md` (its U6), which will reuse these controls.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Optimistic outcomes with a per-session save queue.** The client applies the outcome locally, advances, and sends PATCHes in order; failures pin the item as unsaved (R2). The server stays the source of truth: the queue reconciles against the returned session. Governs R1, R2.
- KTD2. **Undo by inverse PATCH.** Undo sends the prior outcome (or `unreviewed`) and the prior proposition body; hand-added items undo by delete. Governs R3.
- KTD3. **Resume from session state, not browser storage.** The next unreviewed item comes from the session's outcomes; browser storage only remembers the last viewed id as a hint. Governs R7.
- KTD4. **Gestures with a cancel threshold.** A swipe commits past a horizontal threshold with visible feedback and cancels below it, and vertical scrolling never triggers it. Governs R10.
- KTD5. **Keys never fire inside inputs**, as the current handler already enforces; new keys extend that handler. Governs R4, R5, R9.

---

## Implementation Units

### U1. Optimistic save queue and undo

- **Goal:** actions advance instantly, failures stay visible, and undo works.
- **Requirements:** R1, R2, R3; KTD1, KTD2.
- **Dependencies:** none.
- **Files:** `frontend/index.html`, `backend/tests/test_frontend_assets.py`.
- **Approach:**
  1. Split `savePropositionOutcome` into a local apply-and-advance step and a queued network step.
  2. Track unsaved items; render "Not saved — retry"; disable export while any remain.
  3. Keep an undo stack of the last actions; Z pops and sends the inverse.
- **Patterns to follow:** `savePropositionOutcome`, `navigatePropositionReview`, and the existing keydown handler.
- **Test scenarios:**
  - Covers AE1. Five rapid approvals render five successive items before any PATCH resolves.
  - Covers AE1. A rejected PATCH leaves its item marked unsaved and export disabled; retry clears both.
  - Covers AE2. Z after a discard restores the item and sends an `unreviewed` PATCH.
  - Z after an edit restores the prior proposition body.
- **Verification:** Playwright run against a local server with a stubbed slow and failing gold API.

### U2. Keyboard editing and add-by-selection

- **Goal:** type, span, and missed propositions change without leaving the keyboard or the reading pane.
- **Requirements:** R4, R5, R6, R9; KTD5.
- **Dependencies:** U1.
- **Files:** `frontend/index.html`.
- **Approach:**
  1. Number the type options on the card and map keys 1–9.
  2. Add word-step span keys that recompute the quote from canonical text and mark the card edited.
  3. Show "Add as proposition" for a text selection in the document pane; create the hand-added item through the existing annotations route.
  4. Add a "?" help overlay listing all keys and gestures.
- **Test scenarios:**
  - Pressing 2 sets the second listed type and marks the item edited.
  - Moving the end one word right extends the quote by exactly one word.
  - Covers AE3. Selecting a sentence and choosing "Add as proposition" creates a hand-added item with that exact quote.
  - Keys typed inside the type input do not trigger shortcuts.
- **Verification:** Playwright keyboard run; screenshots inspected.

### U3. Progress, resume, direct link, and phone controls

- **Goal:** Damien opens one link on any device and works through the queue to the end.
- **Requirements:** R7, R8, R10; KTD3, KTD4.
- **Dependencies:** U1.
- **Files:** `frontend/index.html`.
- **Approach:**
  1. Add a progress indicator and next-unreviewed jump; resume at the first unreviewed item on load.
  2. When the page opens on `tab=propositions` and an unexported validation session exists for the job with authorized access, enable annotation mode and load it.
  3. Add the narrow-screen bottom bar and swipe handling.
- **Test scenarios:**
  - Reloading after 10 approvals opens item 11.
  - The direct link opens the validation session with annotation mode on.
  - Covers AE4. A right swipe past the threshold approves; a short swipe springs back; a vertical scroll does nothing.
  - Bottom-bar controls are at least 44 px tall and keyboard-focusable.
- **Verification:** Playwright at 1280 px and 390 px; screenshots inspected.

---

## Verification Contract

| Scope | Command or gate |
|---|---|
| Backend suite | `cd backend && .venv/bin/python -m pytest tests/ -v` |
| Browser behavior | Playwright scripts for AE1–AE4 against a local server on the repo's dev port |
| Deploy | DEV (`propositions-dev.damienriehl.com`) serves the build; the Palsgraf validation session still shows 104 items with no outcomes changed by the deploy |

## Definition of Done

- **Behavior:** AE1–AE4 pass in a real browser at desktop and phone widths.
- **Integrity:** no path marks an unsaved item as saved, and no bulk approve exists.
- **Cleanup:** no leftover debug code; screenshots deleted after inspection.
- **Deploy:** the DEV deploy is verified, and the existing validation session data is untouched.
