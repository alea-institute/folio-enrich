# Handoff — Optimize backup-candidate search (Option C: A + B) (2026-07-01)

**Goal:** cut resolution's dominant cost (backup-candidate search) and fix a misleading
confidence display, without hurting precision/recall of the primary annotations.

## Context / prior state
- Streaming fix (PR #5) + semantic-ruler perf (PR #6) + resolution search-cache & batched
  embedding-context (PR #7) are all merged & deployed. `main`/`dev` at `8de4077`.
- PROD deploy: `ssh -i "/home/damienriehl/Coding Projects/folio-ontokit.pem" ubuntu@54.224.195.12`
  then `cd /home/ubuntu/folio-enrich && git pull origin main && sudo -n systemctl restart folio-enrich`.
  (Home IP `97.116.181.129` is allowlisted; direct SSH works.)

## Measured "before" (PROD, real NDA doc, warm)
- `_attach_backup_candidates` → `resolve_multi` (multi-strategy search) per concept:
  **407ms/concept cold, ~41ms warm**; ~824ms warm total for 20 concepts (dominant cost).
- After PR #7's search cache, warm resolution ≈ 0.94s; **cold (fresh process) run 1 ≈ 9s**
  (backup search populating the cache is most of it).
- Backup quality (real output): mostly noise — labels sharing a word with the query
  ("Court" → "Missouri Circuit Court - Dade County", "Court Costs"; "Non" → "Non-Human
  Authorship"). Confidence is the raw multi_strategy_search score/100 (~0.95) — **higher than
  the primary** (e.g. "Supply Agreement" 0.95 vs primary "Agreements" 0.55), which is misleading.
- Backups surface behind an **"Alternatives" toggle** in the tooltip/detail panel (on-demand).

## Plan

### A — Skip backup search for definitive exact-IRI matches (biggest win, safest)
In `backend/app/pipeline/stages/resolution_stage.py::_attach_backup_candidates`, before calling
`resolve_multi`, return early when the concept already has a definitive exact FOLIO IRI (i.e.
`concept_data.get("folio_iri")` is set — EntityRuler/LLM gave a concrete IRI). Rationale: an exact
label match IS the concept; its runner-ups are just other labels sharing a word (measured noisy).
Only concepts resolved via fuzzy multi-strategy search (no input IRI, genuinely ambiguous) keep
backups — which is exactly where an alternative helps. Gate behind a config flag (default on).

- Add to `backend/app/config.py` (near `max_candidates: int = 5`, line 124):
  `skip_backups_for_exact_matches: bool = True`
- Guard:
  ```python
  if max_cand <= 1:
      return
  if settings.skip_backups_for_exact_matches and concept_data.get("folio_iri"):
      return
  ```

### B — Honest confidence (cap backups ≤ primary) + keep the list tight
Still in `_attach_backup_candidates`, when building each backup dict, cap the displayed
confidence so an alternative never looks more certain than the chosen primary:
```python
primary_conf = rd.get("confidence", 0.0)
...
"confidence": min(alt.confidence, primary_conf),
```
(Backups are runner-ups by definition; showing them above the primary is misleading.) Optionally
reduce `max_candidates` to 3. NOTE: the multi_strategy score does NOT separate signal from noise
here (noise scores ~0.95 too), so a *score* threshold won't filter the junk — deeper semantic
relevance filtering would be a larger, separate effort (documented, not in scope for C).

### Tests (`backend/tests/test_resolution_stage.py`)
- New `TestAttachBackupCandidates`:
  - A: with `skip_backups_for_exact_matches=True` and a concept that has `folio_iri`,
    `_attach_backup_candidates` does NOT call `resolver.resolve_multi` and sets no `_backup_candidates`.
  - A: with a concept that has NO `folio_iri`, it DOES call `resolve_multi` (mock it).
  - B: each backup's `confidence` ≤ the primary's `confidence`.
- Mock `resolver.resolve_multi` (return fake ResolvedConcept-likes) to avoid loading FOLIO.

## Verify (measure "after")
1. Local: `cd backend && .venv/bin/python -m pytest -q` (expect all green; ~729+ tests).
2. Deploy to PROD (pull + restart).
3. Measure: submit the NDA doc a few times; expect **warm resolution well below 0.94s** and
   **cold run-1 far below ~9s** (most concepts now skip the search). Confirm `annotations` count
   unchanged (precision/recall of primaries intact). Spot-check the "Alternatives" toggle: only
   ambiguous (no-IRI) concepts should show alternatives now, and none above the primary's confidence.

## Ship
Branch off `main` → PR → merge → deploy → measure. Sync `dev` (`git checkout dev && git merge --ff-only main && git push origin dev`). Delete the branch.

## Test doc used for measurement
"This Non-Disclosure Agreement is entered into between Acme Corporation and John Smith. The parties
agree that confidential information shall not be disclosed. The Court shall have jurisdiction over
any dispute arising under this contract. The plaintiff filed a motion to dismiss. Damages may be
awarded for breach."
