---
phase: quick
plan: 260407-bn9
subsystem: entity-graph
tags: [frontend, backend, ux, graph-visualization]
dependency_graph:
  requires: []
  provides: [branch-root-type-classification, child-count-affordance, seealso-labels]
  affects: [entity-graph-modal, concept-detail-api]
tech_stack:
  added: []
  patterns: [post-pass-classification, flex-layout-centering, svg-edge-labels]
key_files:
  created: []
  modified:
    - backend/app/models/graph_models.py
    - backend/app/services/folio/concept_detail.py
    - backend/tests/test_concept_detail.py
    - frontend/index.html
decisions:
  - Used post-pass after all BFS phases to classify branch roots (avoids issues with incomplete ancestor_visited during BFS)
  - Used flex layout with span flex:1 and textAlign:center for node text centering (avoids justify-content conflict with child count span)
  - Catmull-Rom tension changed from /6 to /10 for tighter edge curves
metrics:
  duration: 3min
  completed: 2026-04-07
  tasks: 2
  files: 4
---

# Quick Task 260407-bn9: Entity Graph Visual Refresh Summary

GraphNode model extended with branch_root_type (ultimate/ancillary) and child_count fields, with 6 frontend visual improvements applied to entity graph rendering.

## What Changed

### Task 1: Backend -- branch_root_type and child_count (bd710f2)

- **GraphNode model**: Added `branch_root_type: str | None = None` (values: "ultimate", "ancillary", None) and `child_count: int = 0`
- **_make_node()**: Computes `child_count = len(oc.parent_class_of or [])` at node creation
- **Post-pass classification**: After all BFS phases (ancestor + descendant + seeAlso ancestor), iterates visited nodes and classifies branch roots as "ultimate" (in `ancestor_visited`) or "ancillary" (reached only via seeAlso)
- **3 new tests**: `test_graph_branch_root_type_ultimate`, `test_graph_branch_root_type_ancillary` (with separate ROOT2 fixture), `test_graph_child_count`

### Task 2: Frontend -- 6 visual changes (07fe169)

1. **Centered node text**: Label span gets `flex: 1` and `textAlign: center` for horizontal centering within available space
2. **Removed left color border**: Deleted `borderLeftColor` and `borderLeftWidth` inline style assignments
3. **Differentiated branch roots**: `.branch-root-ultimate` (dark red border) vs `.branch-root-ancillary` (gray #6b7280 border), with updated legend showing both types
4. **Child count affordance**: Unexpanded nodes show `+N` (e.g., +3) via a dynamically created span with `marginLeft: auto` for right alignment
5. **seeAlso edge labels**: SVG text element "seeAlso" placed at edge midpoint with semi-transparent background rect
6. **Tighter ELK splines**: nodeNode spacing 40->30, added edgeNodeBetweenLayers (30) and edgeEdgeBetweenLayers (15), NETWORK_SIMPLEX node placement, Catmull-Rom tension /6->/10

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- 674 tests passing (including 3 new tests), 0 failures
- All existing tests unaffected by changes

## Self-Check: PASSED

- All 5 modified/created files exist on disk
- Both commit hashes (bd710f2, 07fe169) found in git log
