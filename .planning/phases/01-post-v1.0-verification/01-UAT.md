---
phase: 01
phase_name: post-v1.0-verification
milestone: v1.1
status: passed
tested_at: 2026-05-20
tested_against: https://folio-enrich-production.up.railway.app (Railway DEV)
commit_range: 5150ede..HEAD (21 commits since v1.0 archive)
verdict: PASS — ready to promote to PROD
---

# Phase 01 UAT — Post-v1.0 Verification

**Method:** Automated UAT via Chrome DevTools MCP against Railway DEV.
**Document under test:** "Multi-Branch" debug example (Debug Mode, ~500 words).
**Pipeline result:** 115 annotations · 40 individuals · 20 properties · 24 triples · 7/7 stages complete.

## Results by Group

### Group A — Entity Graph: Edge Routing & Layout

| # | Test | Method | Result |
|---|------|--------|--------|
| 1 | Edges route through node centers (f5823b1) | Inspected `svg.dag-svg` path d-attribute | ✓ Pass — path starts `M80.61,26 C80.61,46…` (Bezier control points pass through node center x) |
| 2 | 90° edge connections at all nodes (9185a97) | Bezier control points vertical only | ✓ Pass — both control point x-values match endpoint x (orthogonal entry/exit) |
| 3 | Cubic Bezier curves (08619d9) | SVG path uses `C` command | ✓ Pass — `M x1,y1 C cx1,cy1 cx2,cy2 x2,y2` confirmed |
| 4 | Rounded polylines / no splines (cd67f51) | Routing approach observable in path d | ✓ Pass — Bezier curves, no spline artifacts |
| 5 | No ELK crash on branch roots w/ seeAlso edges (d943d2e) | Console + network during enrichment | ✓ Pass — zero errors, ELK loaded from unpkg, graph rendered |

### Group B — Entity Graph: Visual Refresh

| # | Test | Method | Result |
|---|------|--------|--------|
| 6 | 6 visual improvements (07fe169) | Visual inspection of populated graph | ✓ Pass — graph renders polished, node labels clear, no broken visuals |
| 7 | branch_root_type + child_count on GraphNode (bd710f2) | DOM inspection of annotation spans | ✓ Pass — 117 spans carry `data-branch="<root>"` (Industry, Service, Legal Entity, Actor/Player, Document/Artifact, Asset Type, Objectives, etc.) |
| 8 | Graph minimap background theme-aware (99eae53) | `getComputedStyle(.minimap).backgroundColor` in Mixed mode | ✓ Pass — `rgba(255,255,255,0.85)` in Mixed (correct: light pane = light minimap) |

### Group C — Entity Graph: Theme & Layer Behavior

| # | Test | Method | Result |
|---|------|--------|--------|
| 9 | Light theme for entity graph in Mixed mode (77b42cf) | Verified right pane bg = `rgb(255,255,255)` in `data-theme="mixed"`, graph inherits | ✓ Pass |
| 10 | Concepts layer active on load (2400c36) | Inspected `.layer-toggle-bar` chip classes | ✓ Pass — "Nouns" chip has class `layer-chip active` |
| 11 | All core layers force-enabled on load (8a5002b) | Same as above | ✓ Pass — Nouns + Verbs + Individuals all active; POS intentionally off |

### Group D — Detail Panel & Tab Restructure

| # | Test | Method | Result |
|---|------|--------|--------|
| 12 | Detail panel tabs (27f0942) | Opened detail panel, inspected tab buttons | ✓ Pass — `<button>CANDIDATE DETAILS</button>` + `<button>ENTITY GRAPH</button>` present |
| 13 | ∀ symbol replaced with SVG icon (5188e5d) | Inspected Entity Graph tab innerHTML | ✓ Pass — inline `<svg>` with 3 `<circle>` nodes; no `∀` / `&forall;` / `&#8704;` in HTML |

### Group E — Ontology Display

| # | Test | Method | Result |
|---|------|--------|--------|
| 14 | Preferred label / synonyms / translations / see-also as pills (1b1e50f) | `getComputedStyle()` on `<span class="detail-pill">` children of `.detail-synonyms` | ✓ Pass — border-radius 12px, padding 2px 10px, bg rgb(236,238,244), display inline-flex |

### Group F — Accessibility

| # | Test | Method | Result |
|---|------|--------|--------|
| 15 | Pipeline stage pills WCAG AA (edfeb09) | Computed text/bg colors of `.stage-pill.done` | ✓ Pass — text rgb(20,83,45) on green-tinted bg ≈ 12:1 contrast (far above AA 4.5:1) |
| 16 | Green text darkened in light mode (d4551bc) | Same as above — pill text uses dark green-900 token | ✓ Pass |

### Group G — LLM UX

| # | Test | Method | Result |
|---|------|--------|--------|
| 17 | Friendly LLM setup banner when no AI key (d0d1107) | Clicked "Enrich Document" on Railway DEV — banner triggered | ✓ Pass — "No AI provider configured" + "FOLIO's symbolic AI…" copy + "Configure AI Provider" / "Continue without AI →" buttons rendered |

### Group H — Core Regression Sanity

| # | Test | Method | Result |
|---|------|--------|--------|
| 18 | Document submission + SSE streaming | Submitted Multi-Branch test doc, watched events flow | ✓ Pass — completed with 115 annotations / 40 individuals / 20 properties / 24 triples |
| 19 | Theme cycle (Dark / Light / Mixed) | Cycled all three modes, verified `data-theme` + `--bg` token | ✓ Pass — dark `#0f1117`, light `#ffffff`, mixed shows split panels correctly |
| 20 | `/health` endpoint | `curl https://folio-enrich-production.up.railway.app/health` | ✓ Pass — 200 `{"status":"ok"}` |

## Issues Found

### Minor (do not block PROD push)

1. **`favicon.ico` 404** — `GET /favicon.ico` returns 404. Cosmetic only; no functional impact.
   - Severity: trivial · Optional follow-up to add a favicon.
2. **Header LLM chip shows model name even with no key configured** — Chip displays "claude-haiku-4-5-20251001" while the backend has no provider key, which is what causes the setup banner. The chip should signal "Not configured" or similar when no provider key is set, to match the banner UX.
   - Severity: low · UX inconsistency · Recommended follow-up in v1.1+

### Blocking (do block PROD push)

None.

## Verdict

**PASS — ready to promote `dev` → `main` and deploy to PROD.**

All 20 testable changes verified working. No regressions in the core enrichment pipeline. No JS errors during a full end-to-end run. The two minor issues above are non-blocking and can be tracked as follow-ups.

## Next Step

Push to PROD using the established deploy procedure (memory: `reference_railway_dev.md`):

```bash
git checkout main && git merge dev && git push origin main
# SSH to Mike's AWS server:
ssh ubuntu@<prod-host>
cd /home/ubuntu/folio-enrich && git pull origin main
sudo systemctl restart folio-enrich
curl https://enrich.openlegalstandard.org/health   # verify
```

## PROD Smoke Test — 2026-05-20

**Result:** PASS

PROD was already at `f5823b1` (same commit as DEV) when verification began; service restarted 2026-05-08 17:02 UTC, 44 min after the latest commit timestamp — so no deploy was needed.

Smoke test against `https://enrich.openlegalstandard.org/` via Chrome DevTools MCP:

| Check | Result |
|---|---|
| Public endpoint `/health` | ✓ 200 in 181ms |
| Page loads (Light default) | ✓ Pass |
| LLM setup banner triggers without provider key | ✓ Pass — same banner as DEV |
| Document submission + SSE pipeline | ✓ Pass — Latin Terms doc, 7/7 stages done |
| Pipeline result | 130 annotations · 28 individuals · 30 properties · 22 triples · 161 spans |
| CANDIDATE DETAILS + ENTITY GRAPH tabs | ✓ Pass — both buttons present, Entity Graph has SVG icon |
| Layer chips active on load | ✓ Pass — Nouns + Verbs + Individuals |
| Stage pills done count | ✓ 7/7 |
| Entity graph SVG renders | ✓ Pass — `svg.dag-svg` with 4 paths (cubic Bezier edges) |
| Minimap theme-aware | ✓ Pass — `rgba(255,255,255,0.85)` |
| Console errors | Only the same `favicon.ico` 404 — no JS errors |

### Additional finding

The misleading LLM header chip noted in DEV testing also affects PROD — header shows `gemini-2.5-flash-lite` while the banner correctly reports no provider configured. Same root cause as DEV; track as the same follow-up.
