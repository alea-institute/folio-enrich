---
title: Reconcile Palsgraf cycle-1 evidence and recorded decisions
type: audit
status: complete
date: 2026-09-30
---

# Palsgraf cycle-1 reconciliation

## Scope and outcome

Completed the bounded E1 audit from the September 30 reviewer proposal. Original card: **Review AI-run gold cycle 1 (Palsgraf) + confirm taxonomy adjudication**. This is an evidence reconciliation, not human validation of the annotations or the folio-insights adoption review. No schema, extractor, gold record, external packet, or remote state was changed.

Base: folio-enrich `bb576ac` (origin/main). This note belongs on the default branch independently of any feature branch.

## Evidence and findings

Sources read locally (sibling repositories read only):

- `backend/eval/gold/propositions/{README.md,manifest.json,palsgraf-248-ny-339.jsonl,demo-smoke.jsonl}`.
- `backend/pyproject.toml`, `backend/uv.lock`, gold store implementation and focused tests.
- Sibling repository `folio-propositions`: `docs/cycle-1-palsgraf-learnings.md` and `exit-record-phase-a.md` (September 30 working-tree snapshots, not a claim of remote currency).
- The dependency's committed source at `cb1e6a7f0e868534790b446043e9f630c380c356` in that sibling repository.
- Decision source **ANS**: maintainer decision record `folio-enrich-2026-08-17-1858-propositions-dns-and-cycle1` (kept outside this repository), specifically `q2-taxonomy-adjudication`, `q3-schema-shape`, and `q4-review-logistics`.

### Recomputed gold accounting

| Measure | Result |
|---|---:|
| JSONL rows | 127 |
| Exported annotation records | 104 |
| Pre-selected accepted / edited / deleted | 2 / 6 / 5 |
| Hand-added annotations | 96 |
| Learning records / blind-segment records | 17 / 1 |
| Recall proxy: 1 − 96 / 104 | 0.0769230769 |
| Precision: (2 + 6) / 13 | 0.6153846154 |
| Density: 104 / 5,822 × 1,000 | 17.8632772243 |

The word denominator is the recorded manifest value; the canonical opinion text was not independently reconstructed. Counts and recall/precision are independently derived from row provenance and outcomes, then checked against the manifest. `disposition` is the legal outcome, not the annotation acceptance decision: exported propositions include 55 accepted, 31 unresolved, 15 rejected, 2 assumed-arguendo and 1 revised legal dispositions. All 104 count as exported gold. Neither 127 rows nor 55 accepted legal propositions is the gold count.

The low recall supports the cycle's rejection of the reporting-verb coverage assumption for this annotated opinion. It does not establish general recall across judicial genres. The manifest labels the run lexicon-only and `baseline: false`; this is the recorded cycle proxy, not a fresh baseline experiment. Blind-segment evidence is demonstrative: the annotator saw candidates before choosing the range. The cycle learnings explicitly acknowledge this limitation.

### Taxonomy and migration

The card's v0.2.0 milestone is historical. The manifest and lock agree on v0.3.0, with lock SHA `cb1e6a7f0e868534790b446043e9f630c380c356`. Local history contains merge `f10ebec80d68590cc3e8dd2b7256a7e6c47bb88a`, implementation `d8103457fa8c32868d795cdd71bbae59d7257c5e`, and lock update `43f0fc153d6adb01aaec3802094e85de8192b534`.

The pinned taxonomy has four FOLIO labels with IRIs and six library-local types without IRIs. Cycle promotions remain cited-authority proposition, hypothetical illustration, and policy proposition. Dissent stays attribution/validation rather than a separate type; hypothetical party claim was merged; two definitional propositions remain new-type tags. All 128 nested Palsgraf payloads and all 7 demo payloads carry schema 3, including original candidates and blind-diff snapshots. The focused tests cover session migration and recursive blind-snapshot migration, wrapper/payload separation, lexicon taxonomy, settings, and disabled-feature byte neutrality.

### Decision reconciliation and limits

| Topic | Evidence and current interpretation |
|---|---|
| Taxonomy direction | ANS q2 redirects analysis toward FOLIO top-down/bottom-up reconciliation. The external exit record subsequently says **ADOPT WITH REVISIONS**, confirmed August 17, and local v0.3.0 implementation corroborates adoption. ANS itself does not enumerate the final type approvals. |
| Polarity and per-opinion validation stance | ANS q3 chooses **Defer to more cycle evidence**. Retain these as deferred structural risks; do not introduce fields or reopen the same question in this audit. |
| Review format and distribution | ANS q4 chooses **Self-review this week; stay git-pinned**. No PyPI publish is needed or authorized by this item; the manifest's comment mentioning a future v0.1.0 PyPI pin is historical, not the selected distribution policy. |
| Human validation | Cycle learnings and manifest identify Claude as the delegated AI annotator. No human session-validation receipt was established. The gold README's blanket “human-reviewed” description is not supported for Palsgraf. |
| Adoption boundary | Phase A plan R18/F3 reserves the frozen-versus-revisable insights vocabulary for its own disposition. That card is ON SHEET and is skipped in this lane; no conclusion about its current answer or completion is inferred. |

The external exit record contains an internal stale gate: its post-cycle section reports taxonomy confirmation while its Phase B conditions still request confirmation. Treat taxonomy implementation as recorded; do not equate it with completed human gold review, the corpus ladder, or the separate v2.0 adoption review. Only one opinion of the intended ladder is recorded. This resolves the earlier reviewer's cross-repo evidence gap for the two cycle documents, not for the skipped review packet as a whole.

## Proposed card correction for the orchestrator

**Title:** Reconcile Palsgraf cycle-1 evidence with FOLIO-aligned v0.3.0 and recorded decisions.

**Note:** Local reconciliation complete September 30: 104 AI-annotated gold propositions; 96 hand-adds; lexicon recall proxy 0.076923 and precision 0.615385. FOLIO-aligned v0.3.0 is already pinned and migrated. Polarity and per-opinion stance remain deferred under the recorded schema decision; self-review and git-pinned distribution are settled. Human validation is not established. The separate folio-insights adoption review stays on its existing Decision Sheet. Preserve original title lineage and ANS q2/q3/q4 links.

Do not mark the original human review complete solely from this audit. Do not repeat a cycle, publish, or create a duplicate adoption question.

## Verification

- [x] Independently count annotation outcomes/provenance and compare metrics to manifest.
- [x] Check manifest/lock consistency, pinned taxonomy, and recursively migrated payloads.
- [x] Read cycle learnings and exit record; reconcile decisions to ANS.
- [x] Run existing focused tests: **50 passed in 0.73s**.
- [x] Preserve the ON SHEET boundary and unrelated files.

System `python3 -m pytest` first failed collecting conftest because `httpx` was unavailable. No dependencies were installed. The existing backend virtualenv was used read-only with bytecode writes disabled and a clean environment:

```sh
cd backend
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 FOLIO_ENRICH_JOBS_DIR=/tmp/folio-jobs FOLIO_ENRICH_FEEDBACK_DIR=/tmp/folio-feedback .venv/bin/python -m pytest tests/test_gold_store.py tests/test_gold_validity.py tests/test_proposition_stage.py tests/test_proposition_byte_neutral.py tests/test_settings_propositions.py -q
```

Reproduce the data audit from the repository root using the existing virtualenv Python (with `PYTHONDONTWRITEBYTECODE=1`). This reads only the named records and dependency source; it does not run the application:

```python
import collections, importlib, json, math, pathlib, subprocess, tomllib
from folio_propositions import Proposition, SCHEMA_VERSION, WORKING_TAXONOMY, migrate_record
root = pathlib.Path('backend')
lock = tomllib.loads((root / 'uv.lock').read_text())
pkg = next(p for p in lock['package'] if p['name'] == 'folio-propositions')
sha = 'cb1e6a7f0e868534790b446043e9f630c380c356'
assert pkg['version'] == '0.3.0'
assert pkg['source']['git'].endswith('?rev=v0.3.0#' + sha)
assert '@v0.3.0' in (root / 'pyproject.toml').read_text()
for name in ('models', 'interchange', '__init__'):
    mod = importlib.import_module('folio_propositions' + ('.' + name if name != '__init__' else ''))
    pinned = subprocess.check_output(['git', '-C', '../folio-propositions', 'show', sha + ':src/folio_propositions/' + name + '.py'])
    assert pathlib.Path(mod.__file__).read_bytes() == pinned, name
assert SCHEMA_VERSION == 3 and len(WORKING_TAXONOMY) == 10
assert sum(v is not None for v in WORKING_TAXONOMY.values()) == 4
base = root / 'eval/gold/propositions'
rows = [json.loads(s) for s in (base / 'palsgraf-248-ny-339.jsonl').read_text().splitlines()]
gold = [r for r in rows if r['record_type'] == 'annotation' and not r.get('deleted')]
selected = collections.Counter(r['outcome'] for r in rows if r.get('origin') == 'pre-selected')
hand = sum(r.get('provenance') == 'hand-added' for r in gold)
assert len(rows) == 127 and len(gold) == 104 and hand == 96
assert selected == {'accepted': 2, 'edited': 6, 'deleted': 5}
manifest = next(o for o in json.loads((base / 'manifest.json').read_text())['opinions'] if o['slug'] == 'palsgraf-248-ny-339')
recall = 1 - hand / len(gold)
precision = (selected['accepted'] + selected['edited']) / sum(selected.values())
assert math.isclose(recall, manifest['recall_proxy'])
assert math.isclose(precision, manifest['precision'])
assert manifest['hand_added_count'] == hand
assert all(manifest['counts'][k] == v for k, v in selected.items())
assert math.isclose(len(gold) * 1000 / manifest['density']['word_count'], manifest['density']['opinion'])
def payloads(value):
    if isinstance(value, dict):
        if 'proposition_type' in value:
            yield value
        for child in value.values():
            yield from payloads(child)
    elif isinstance(value, list):
        for child in value:
            yield from payloads(child)
for file, expected in [('palsgraf-248-ny-339.jsonl', 128), ('demo-smoke.jsonl', 7)]:
    items = list(payloads([json.loads(s) for s in (base / file).read_text().splitlines()]))
    assert len(items) == expected
    for item in items:
        assert item['schema_version'] == 3
        Proposition.model_validate(item)
        assert migrate_record(item, target_version=3) == item
    print(file, len(items), 'valid schema-v3 payloads; migration idempotent')
print('PASS: 104 gold; 96 hand-added; recall', recall, 'precision', precision)
print('PASS: manifest/lock/pinned installed model source agree')
```

## Rollback and integration

Documentation-only change; revert the commit that added this note. No production staging or release applies. The orchestrator may integrate that commit onto the default branch and reconcile the card with existing receipts. The ON SHEET item requires no worker commit or new decision request.
