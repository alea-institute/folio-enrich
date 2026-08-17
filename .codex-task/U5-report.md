# U5 — Instrument-validity controls report

## Summary

Implemented the Phase A validity instrument controls for R15 and R16:

- Blind segments are persisted, validated before designation, and masked server-side until reveal. Reveal persists an overlap-based anchoring diff with matched, tool-only, and annotator-only records plus count/fraction metrics.
- Explicit full-text coverage attestation and a separate completeness check now enforce all three first-opinion conditions without changing the existing export gate.
- Baseline sessions force lexicon-only provenance and re-run the deterministic `PropositionExtractor` against canonical text instead of accepting LLM-assisted job candidates.
- Gold exports include the blind-segment record/diff; manifest entries include `blind_segment`, `baseline`, and `completeness`.
- The Propositions tab now supports baseline selection, blind-segment designation, masked/hatch rendering, reveal/diff, hidden-count feedback, explicit coverage attestation, and endpoint-driven completeness status.

The worktree was left uncommitted. No network or Git commands were used.

## Changed files

- `backend/app/services/gold/store.py`
- `backend/app/api/routes/gold.py`
- `backend/tests/test_gold_validity.py` (new)
- `frontend/index.html`
- `.codex-task/U5-report.md` (new)

## Red/green evidence

Tests were authored before the store implementation. Initial focused run:

```text
FFFFFFF                                                                  [100%]
7 failed in 0.34s
```

The failures were the expected missing U5 contracts: no blind-segment methods, no coverage field/action, and no baseline argument.

After implementing the store controls:

```text
.......                                                                  [100%]
7 passed in 0.31s
```

After routes, export assertions, and route-level integration coverage:

```text
.................                                                        [100%]
17 passed in 0.30s
```

## Final verification tails

Required backend verification:

```text
$ cd backend && .venv/bin/python -m pytest tests/test_gold_store.py tests/test_gold_validity.py tests/test_proposition_byte_neutral.py tests/test_proposition_stage.py -q
..........................                                               [100%]
26 passed in 0.38s
```

The environment also emitted three benign `Failed to create stream fd: Operation not permitted` lines before pytest output; they did not affect collection or results.

Frontend script and ID verification:

```text
2
propositionBaselineToggle 1
blindSegmentBtn 1
revealBlindBtn 1
blindPendingChip 1
propositionBlindBanner 1
coveragePassBtn 1
propositionCompletenessStatus 1
propositionBlindDiff 1
```

Both inline `<script>` blocks were extracted to a managed `/tmp` directory and passed `node --check`. Every U5 element ID occurs exactly once.

## Design decisions

- Public session reads return a deep-copied, masked model; internal mutations use a separate full-session loader. This prevents hidden candidate spans from leaking while retaining them for reveal, completeness, and export.
- Blind intersection uses half-open character spans (`candidate.start < segment.end && candidate.end > segment.start`) and the original pre-selected span, preserving the instrument even if later candidate boundaries change.
- Diff matching is one-to-one and overlap-based. Each tool candidate claims at most one overlapping hand-added annotation; unmatched items become tool-only or annotator-only. Fractions use tool count for match/tool-miss/anchoring-loss and annotator count for annotator novelty, with defined zero-denominator values.
- Completeness is computed from the full stored candidate set, so masked candidates still count as unreviewed. Export remains gated only by zero unreviewed candidates, exactly as U3 specified.
- The visible “unreviewed remaining” total adds `blind_pending`, preventing masked candidates from making the client appear export-ready.
- While a blind segment is pending, all proposition marks intersecting it—including hand-added marks—are suppressed in the document view, while hand-added cards remain editable. The neutral hatch communicates the range without exposing suggestions.
- Baseline mode preserves lexicon version/config metadata but clears LLM provider/model and always regenerates candidates from canonical text.

## Browser-smoke walkthrough for the orchestrator

1. Start the backend and open the app. Complete an enrichment whose canonical text produces at least two proposition candidates.
2. Open **Propositions**. Before enabling annotation mode, optionally check **Lexicon-only baseline session**; enable **Annotation mode** and confirm the mode label shows the baseline when selected.
3. Click **Designate blind segment**, select text that intersects one or more candidate spans, and release. Confirm:
   - the selected range has a subtle neutral hatched background;
   - proposition marks inside the range are absent;
   - candidate cards from that range are absent;
   - the chip reads `blind segment: N hidden` with a nonzero count.
4. Click **+ Add span**, select proposition text inside the hatched range, complete the draft card (including the explicit unresolved checkbox if leaving that disposition), and save. Confirm the hand-added card persists while no mark appears inside the pending blind range.
5. Click **Reveal & diff**. Confirm the hatch is removed, hidden candidates appear as ordinary unreviewed cards/marks, and the summary block displays matched, tool-only, annotator-only, and anchoring-loss values.
6. Review every now-visible candidate with Accept, Save edit, or Discard. Confirm the completeness line still reports the missing coverage pass.
7. Click **Record full-text coverage pass**. Confirm the button changes to **Coverage pass recorded** and becomes disabled; completeness should flip to complete once there are zero unreviewed candidates and the blind segment is revealed.
8. Export the gold record and confirm success. Inspect the generated manifest entry for `blind_segment: true`, the correct `baseline` value, and `completeness.complete: true`; inspect JSONL for the `blind-segment` record and persisted diff report.

