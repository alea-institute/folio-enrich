---
status: resolved
phase: 03-consolidated-system-status-chip
source: [03-VERIFICATION.md]
started: 2026-05-22
updated: 2026-05-22
evidence: "Live Chrome DevTools UAT at http://localhost:8731/ across Dark/Light/Mixed + product-owner approval (+ two UAT-driven refinement rounds: flat dots, 6px sizing, and 4 disclosure warning fixes)"
---

## Current Test

[complete — all items verified live and approved]

## Tests

### 1. STATUS-02 quiet green at rest
expected: chip shows "System" (green) at fresh load; FOLIO/Embedding "Standby" stay green
result: passed

### 2. STATUS-03 degraded rollup
expected: chip updates to "System: {subsystem} +N" when /health/detail reports failures
result: passed (verified: single spaCy error → "System: spaCy"; +2nd → "System: Embedding +1")

### 3. STATUS-04 popover metrics + Manage FOLIO
expected: four rows show live metrics; "Manage FOLIO" opens the existing modal
result: passed (18,326 concepts / 68,412 labels / vectors / spaCy 3.8.x; Manage FOLIO closes popover + opens modal — WR-02 fix)

### 4. STATUS-05 keyboard + focus management
expected: Enter/Space open, Escape/outside-click close, focus moves in on open and restores to chip on keyboard close
result: passed (Escape restores focus to chip; outside-click no longer steals focus — WR-01 fix)

### 5. STATUS-06 LLM chip
expected: LLM/Ollama chip separate and clickable in the header
result: passed (untouched, byte-for-byte)

### 6. STATUS-07 no header overlap
expected: status bar and layer toggle bar have a visible gap with a document loaded
result: passed (statusBar right 385px vs layerToggleBar left 401px — 16px gap at 1221px desktop)

### 7. STATUS-05 light-theme dot clarity
expected: green/orange/red dots are visually clear at 6px on the light surface
result: passed (deeper --status-dot-* shades clear WCAG 3:1; dots normalized to 6px to match the LLM/layer dots)

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None. All seven STATUS requirements verified live and approved by the product owner.
