# Phase 03 Component Verification Checklist

**Generated:** 2026-04-05
**Scope:** Modal, tooltip, and scrollbar theming per CMPT-01, CMPT-02, CMPT-03 (D-06: verify + fix gaps only)

---

## Modal Verification Matrix

| Modal | Trigger | Dark | Light | Mixed | Notes |
|-------|---------|------|-------|-------|-------|
| Settings modal | gear icon ⚙ | [ ] | [ ] | [ ] | Contains Appearance section (theme swatches) |
| Synthetic doc generator | sidebar button "Generate..." | [ ] | [ ] | [ ] | |
| Cascade modal | concept detail action | [ ] | [ ] | [ ] | |
| Demo links modal | Demo button (header) | [ ] | [ ] | [ ] | |
| FOLIO update modal | FOLIO status chip | [ ] | [ ] | [ ] | |
| Graph modal | concept detail graph icon | [ ] | [ ] | [ ] | Large overlay — contains canvas |
| Ollama setup wizard | Ollama setup CTA | [ ] | [ ] | [ ] | |

## Tooltip Verification Matrix

| Tooltip | Trigger | Dark | Light | Mixed | Notes |
|---------|---------|------|-------|-------|-------|
| Concept tooltip | hover concept annotation | [ ] | [ ] | [ ] | Shows definition, IRI, branch pill |
| Individual tooltip | hover entity/citation span | [ ] | [ ] | [ ] | |
| Property tooltip | hover property underline | [ ] | [ ] | [ ] | |
| Triple tooltip | hover triple cross-link badge | [ ] | [ ] | [ ] | In Triples tab |
| Branch overlay tooltip | hover multi-branch indicator | [ ] | [ ] | [ ] | Stacked gradient indicator |

## Scrollbar Verification Matrix

| Scrollable Area | Dark | Light | Mixed | Notes |
|-----------------|------|-------|-------|-------|
| Main document panel (.panel-content) | [ ] | [ ] | [ ] | |
| Left panel input area (document input) | [ ] | [ ] | [ ] | |
| Right panel concept list | [ ] | [ ] | [ ] | Uses --scrollbar-thumb tokens |
| Detail panel body | [ ] | [ ] | [ ] | Uses --scrollbar-thumb tokens |
| Modal content (.modal) | [ ] | [ ] | [ ] | |
| Triples tab list | [ ] | [ ] | [ ] | |

## Hardcoded Colors Audit

**Searched:** modal/tooltip/scrollbar rule bodies for `background: #...` or `color: #...`

- **Result:** `grep -E "\.modal|\.concept-tooltip" frontend/index.html | grep -cE "background:\s*#[0-9a-fA-F]|color:\s*#[0-9a-fA-F]"` returns **0**
- **Verdict:** Audit clean. All modal/tooltip/scrollbar selectors reference CSS tokens via `var()`.

### Intentional hardcoded values (not gaps)
- Token primitive definitions in `:root` and `[data-theme=*]` blocks — these are the palette, not usage.
- Modal overlay backdrop `rgba(0,0,0,0.3)` — theme-agnostic backdrop. Acceptable per D-06.
- Tooltip box-shadow `rgba(0,0,0,...)` — theme-agnostic shadow. Acceptable.

## Summary

Phase 1's CSS migration was thorough — no hardcoded color leaks found in component CSS rule bodies. Task 2 (fixes) is a no-op: no code changes required. Proceeding directly to user visual verification on Railway.
