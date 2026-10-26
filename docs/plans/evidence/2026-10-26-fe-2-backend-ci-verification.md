# fe-2 backend CI verification — 2026-10-26

## Result and scope

The existing backend CI promotion is present, and its exact default-suite command
passed locally: **1,230 passed, 10 skipped, 0 failed in 18.47 seconds**. This
completes the local verification and documentation work in U1/U2 of
[`2026-10-26-1038-test-fe-2-backend-ci-verification-plan.md`](../2026-10-26-1038-test-fe-2-backend-ci-verification-plan.md).
Hosted acceptance remains controller-owned and pending.

The tested revision was `32c6afbc2e42e0d6adc4d3f349b1a0b4523ef95f` on
`drawdown/fe-2`. The tracked working tree was clean throughout setup and test
execution. This revision contains baseline `26e5c61b44e3165d3f2bfad5214516a6d6dcede3`,
the already-landed backend lane in `fe7f46249ecb19cebda42e7efe509c6dc499ea11`
(PR #45), and the fe-2 plan commit. It was not compared with live `origin/main`:
the supplied clone has no remote or local `main` ref.

Only `README.md` and this receipt were changed after testing. Workflow,
application, test, dependency, and lock files are unchanged. No new test is
needed for these documentation changes; existing regression coverage was used
unchanged. No frontend change or screenshot is part of fe-2.

## Environment and setup

| Component | Observed version or condition |
|---|---|
| Runner | Local sandbox, Ubuntu 26.04.1 LTS, Linux x86_64; not a GitHub runner |
| Python | CPython 3.13.11 |
| uv | 0.9.22 |
| pytest / xdist / timeout | 9.0.2 / 3.8.0 / 2.4.0 |
| spaCy / model | 3.8.11 / `en_core_web_sm` 3.8.0 |
| Shared proposition library | 0.4.0 at locked commit `bb62e5b6defdccd8d552b794e16bdc2267720628` |
| Optional tooling | `[embeddings]` not installed; browser helper found no usable Playwright/Chromium package |

Commands executed from `backend/`, in order:

```sh
UV_PYTHON=3.13 uv sync --frozen --extra dev
uv pip install --no-cache https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
uv run --no-sync python -m pytest tests/ -q -n 2 -ra -p no:cacheprovider
uv run --no-sync python -m pytest tests/ --collect-only -q -p no:cacheprovider
```

Frozen sync created a fresh `backend/.venv`, installed 99 packages, and exited
0. The pinned model installation also exited 0. `UV_PYTHON=3.13` supplies the
Python selection that the hosted setup action supplies; the test invocation is
identical to the workflow. No dependency pins were changed and no credentials
were supplied.

The uv invocations emitted `Failed to create stream fd: Permission denied`;
installation also warned that hardlinks were unavailable and copied files
instead. These warnings did not prevent setup, collection, or the two-worker
run from completing. No sandbox exception or test modification was needed.

## Test results

| Check | Result |
|---|---|
| Exact CI test invocation | Exit 0; 1,230 passed, 10 skipped, 5 warnings; 18.47 seconds |
| Separate collection check | Exit 0; 1,240 selected out of 1,283, with 43 deselected; 0.22 seconds |
| Failures / errors / xfails / xpasses | None reported |
| Default marker expression | `not slow and not demo_regen and not eval`, unchanged |

The xdist summary does not print deselection totals, so those counts come from
the separate collection check with the same default marker configuration.

All ten skips were existing optional browser tests:

| Test file | Skips | Reported reason |
|---|---:|---|
| `backend/tests/test_fast_gold_browser.py` | 8 | Playwright package not found; suggests `FOLIO_ENRICH_PLAYWRIGHT_MODULE` |
| `backend/tests/test_post_job_browser.py` | 1 | No Playwright package with a launchable Chromium; suggests the same variable |
| `backend/tests/test_insights_browser.py` | 1 | Playwright package not found; suggests the same variable |

Warnings were one PyJWT short-HMAC-key warning in the rejected-assertion test,
three FAISS/SWIG deprecation warnings, and one citeurl invalid-escape warning.
They were reported without suppression. The optional browser and excluded
`slow`, `demo_regen`, and `eval` tiers were not certified by this run.

Collection explicitly included both prior CI regression cases, and neither
appeared in the full run's skip list; both passed in that run:

- `backend/tests/test_cf_access.py::test_expired_jwks_fetch_failure_does_not_use_stale_keys`
  expires the cache relative to the monotonic clock and verifies denial when
  fetching replacement keys fails.
- `backend/tests/test_ontology_ingestion.py::TestUrlGate::test_accepts_allowlisted_github`
  exercises the public-IP gate with a DNS stub rather than a live lookup.

## Workflow and documentation checks

`actionlint` was unavailable. PyYAML 6.0.3 `BaseLoader` successfully parsed
`.github/workflows/tests.yml` while preserving the literal `on` key. Explicit
structural assertions verified the unfiltered `pull_request` event, push to
`main`, read-only contents permission, `backend` working directory, 20-minute
job timeout, checkout without persisted credentials, Python/uv selection,
setup-command order, and exact pytest command. The job and steps have no `if`
gate or `continue-on-error`, and the run commands have no success override.
The existing concurrency policy cancels superseded runs.

This is YAML and configuration evidence, not actionlint validation or a hosted
workflow result. Under ordinary GitHub event eligibility and approval rules,
the configuration includes documentation-only PRs. A cancelled run is not a
completed passing check.

README instructions now match the existing workflow, manifest, browser helper,
and separate eval workflow. The undated test totals in Testing and Project
Structure were replaced with scope descriptions and this dated evidence link.
The eval workflow's path-filtered and scheduled triggers and its execution of
both tiers on every triggered run are documented; that workflow was not changed
or run as part of fe-2.

## Controller acceptance still required

- Publish the branch and record the final PR revision, a completed
  `backend-tests` job URL, and its conclusion. A cancelled or merely configured
  check is insufficient. No push, PR creation, workflow dispatch, or hosted-run
  inspection occurred in this clone.
- Reconcile the chief campaign plan's Goal Capsule and campaign R11, R15, R16,
  R17, R19, and R20, plus
  `docs/handoffs/2026-10-26-unified-proposition-engine-brainstorm.md`. These sources
  are absent from the provided workspace; their constraints were not
  independently reviewed. The supplied standing lane rules were followed, and
  the available Phase A plan and Palsgraf reconciliation were consulted. Human
  gold review, U6 validation, and deferred proposition fields remain untouched.
- If publication changes workflow, test, dependency, or application files,
  repeat affected verification. Documentation-only edits after this measured
  revision require diff review, not an invented new test result.

These are controller checks, not requests for Damien or claims that the campaign
item has already passed hosted acceptance.
