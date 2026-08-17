# U3 implementation report

## Summary

Implemented the proposition gold store end to end: atomic annotation-session persistence, complete candidate accounting, explicit unresolved discipline, hand-added annotations and cycle learnings, independent wrapper/payload migrations, cleanup protection, gated JSONL/brat/manifest export, record-only precision and recall-proxy metrics, canonical density, and the `/gold` API routes.

The standard brat exporter now appends proposition standoff entries only when propositions exist. Its empty-proposition path remains byte-identical to the pre-U3 exporter output.

## Changed files

- `backend/app/services/gold/__init__.py`
- `backend/app/services/gold/store.py`
- `backend/app/api/routes/gold.py`
- `backend/app/services/export/brat_exporter.py`
- `backend/app/storage/job_store.py`
- `backend/app/main.py`
- `backend/tests/test_gold_store.py`
- `backend/eval/gold/propositions/README.md`
- `backend/eval/gold/propositions/demo-smoke.jsonl`
- `backend/eval/gold/propositions/demo-smoke.ann`
- `backend/eval/gold/propositions/manifest.json`
- `.codex-task/U3-report.md`

## Verification evidence

### Red/green sequence

Before production implementation:

```text
$ .venv/bin/python -m pytest tests/test_gold_store.py -q
FFFFFFF
7 failed
ModuleNotFoundError: No module named 'app.services.gold'
ImportError: cannot import name 'gold' from 'app.api.routes'
```

After implementation, the focused U3 suite first reached:

```text
....... [100%]
7 passed in 0.07s
```

Two additional migration-hook and brat contract tests were then added.

### Final required gate

```text
$ .venv/bin/python -m pytest tests/test_gold_store.py tests/test_proposition_byte_neutral.py tests/test_proposition_stage.py -q
.................. [100%]
18 passed in 0.37s
```

### Touched-surface regressions

```text
$ .venv/bin/python -m pytest tests/test_tier2_exports.py tests/test_job_retention.py tests/test_demo_seed.py -q
................... [100%]
19 passed in 1.49s

$ .venv/bin/python -m pytest tests/test_property_extraction.py tests/test_individual_extraction.py -k brat -q
.. [100%]
2 passed, 102 deselected in 0.06s

$ .venv/bin/python -m compileall -q app/services/gold app/api/routes/gold.py app/services/export/brat_exporter.py app/storage/job_store.py app/main.py
(no output; success)
```

The runtime repeatedly printed `Failed to create stream fd: Operation not permitted` before pytest output; this container warning did not affect test results.

### Scripted deterministic session

The demo enabled proposition extraction, ran ingestion + normalization + deterministic lexicon proposition extraction over a short judicial text, created a gold session, recorded accepted/edited/deleted outcomes, added one hand-added new type and one `new-type` learning, then exported successfully.

Produced artifacts:

- `backend/eval/gold/propositions/demo-smoke.jsonl`
- `backend/eval/gold/propositions/demo-smoke.ann`
- `backend/eval/gold/propositions/manifest.json`
- `backend/eval/gold/propositions/README.md`

Printed metrics:

```json
{
  "density": {"opinion": 157.89473684210526, "word_count": 19},
  "precision": 0.6666666666666666,
  "recall_proxy": 0.6666666666666667
}
```

The manifest entry records one accepted, one edited, one deleted, zero unreviewed, and one hand-added proposition, with wrapper and library schema versions and the lexicon-only pre-selector configuration.

## Design decisions

- Sessions live under `<job-store>/gold_sessions/`. This keeps them in the job-store filesystem area and lets `cleanup_expired` derive protection from persisted session files after a restart, rather than relying only on the process-local `PROTECTED_JOB_IDS` set.
- A session remains cleanup-protected until `exported_at` is persisted. Export then removes the in-process exemption; the disk-derived check also stops protecting it.
- Wrapper migrations and proposition migrations are deliberately separate. `migrate_session` owns wrapper transitions and ships a v1→v2 wrapper-only stub; embedded payloads go through `folio_propositions.migrate_record` without wrapper migration rewriting them.
- Candidate `original` values are immutable snapshots. Edit classification compares offsets separately from all other proposition fields, yielding `boundary`, `field`, or `both`.
- JSONL includes kept annotations, deleted-candidate audit entries, and cycle-learning entries. Metrics filter by record type/origin, so they are computable from the exported record without session state.
- Precision is `(accepted + edited) / (accepted + edited + deleted)` for pre-selected candidates. Recall proxy is `1 - hand-added / total exported gold`. Density counts accepted, edited, and hand-added propositions only.
- Per-section density is emitted when canonical text elements carry `section_path`; otherwise only opinion density is emitted.
- The brat extension uses T entries for proposition spans and attributes for asserter, validator, and disposition. With an empty proposition list, no lines or separators are added.
- The API uses 404 for missing jobs/sessions/candidates and 422 for validation/export-gate failures, including the unreviewed count.

The tree is intentionally left uncommitted. No network or Git commands were used.
