# Requirements: v1.2 Header & Status UX

**Milestone goal:** Make the header status bar render reliably across all platforms and consolidate passive health indicators so problems are obvious and clutter is gone.

## v1.2 Requirements

### Translation Flags (FLAG)

- [ ] **FLAG-01**: User sees translation flags rendered as self-contained inline SVG (no Unicode emoji, no external image requests), so flags display on every OS including Windows.
- [ ] **FLAG-02**: User sees flags display correctly when a content/privacy blocker (e.g., EFF Privacy Badger) is enabled.
- [ ] **FLAG-03**: User (screen-reader) gets an accessible label naming the locale/country for each flag.
- [ ] **FLAG-04**: User sees a graceful fallback (e.g., styled country-code pill) for any locale without a bundled flag, never a broken glyph.

### System Status Chip (STATUS)

- [ ] **STATUS-01**: User sees Backend, FOLIO, Embedding, and spaCy consolidated into a single "System" status chip in the header.
- [ ] **STATUS-02**: User sees a single quiet green state when all four subsystems are healthy.
- [ ] **STATUS-03**: User sees the chip reflect worst-status (red > orange > green) and identify the failing subsystem when any is degraded or errored.
- [ ] **STATUS-04**: User can click/expand the chip to reveal per-subsystem detail (status plus the metrics shown today — concepts loaded, vectors indexed, etc.).
- [ ] **STATUS-05**: User perceives each status via icon + text (not color alone); the chip meets WCAG AA and is keyboard- and screen-reader-accessible.
- [ ] **STATUS-06**: User sees the LLM chip remain a separate, actionable chip with its current configure behavior unchanged.
- [ ] **STATUS-07**: User no longer sees the header status chips overlap the layer chips (Nouns/Verbs/Individuals/POS).

## Future Requirements (deferred)

- Consolidating or restyling the layer chips (Nouns/Verbs/Individuals/POS) — separate concern from system health.
- Responsive/mobile header layout — not in scope for this milestone.

## Out of Scope

- Folding the LLM chip into the consolidated system chip — it is an actionable control, not a passive health indicator (would muddy its affordance).
- Per-subsystem configuration UI beyond what exists today.
- New backend health/telemetry endpoints — consolidation uses the existing `/health` and `/health/detail` data.

## Traceability

| REQ-ID | Phase |
|--------|-------|
| FLAG-01 | Phase 02 |
| FLAG-02 | Phase 02 |
| FLAG-03 | Phase 02 |
| FLAG-04 | Phase 02 |
| STATUS-01 | Phase 03 |
| STATUS-02 | Phase 03 |
| STATUS-03 | Phase 03 |
| STATUS-04 | Phase 03 |
| STATUS-05 | Phase 03 |
| STATUS-06 | Phase 03 |
| STATUS-07 | Phase 03 |
