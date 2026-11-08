# fe-1 stranded-branch triage receipt

Date: 2026-10-26. Item: `fe-1` (planned). Branch: `drawdown/fe-1`.
Authority: [fe-1 implementation plan](../2026-10-26-0949-chore-fe-1-branch-triage-plan.md).

## Outcome and boundary

All five mandate families have landing commits in the supplied target and
matching current implementation. No still-needed source change was established,
so no recovery patch or duplicate landing PR is justified by this checkout.
The bounded local audit and verification are complete; full campaign closure
still needs the controller's source inventory and authority
inputs. Missing tips are not evidence that every historical variant landed.

Only this receipt is added by the build stage. No application, test, workflow,
dependency manifest, lockfile or gold data changes are required. The existing
plan remains the execution contract; `fe-2` through `fe-5` are separate items.

## U1: refreshed target and source inventory

The clean starting `HEAD` was `00090d068789ace35746ec4435c23785eda8cb18`, the
committed fe-1 plan. Its parent is the provided target snapshot
`26e5c61b44e3165d3f2bfad5214516a6d6dcede3` (PR #47). The sole difference from
that target at build intake was the plan. This evidence and the U2 test results
were captured at `26e5c61`; the branch was later rebased onto a newer base.
At review refresh, `HEAD` is `cf8b1ac6690e0724ce4f8eda9516202f3caf3b99`
and its merge base with `origin/main` is
`f0accec27b779ea11c87d57dbd58bde2df5666db`, a descendant of `26e5c61`.
The refreshed ancestry checks below use the available remote-tracking
`origin/main` at `cffe049c51bc7197a8354c783af3d1843285479d`.
`git ls-remote origin` failed because DNS resolution was unavailable, so this
refresh does not verify the live remote head or rerun U2 on the newer base.

At capture, `git for-each-ref` found two local heads: `drawdown/fe-1` and
`codex/proposition-review-workspace-final`, with no remote-tracking refs.
The review refresh now has the remote-tracking refs listed below; both the local
and origin workspace-final refs currently point to `d9ebbf9`. Tags are not
source-branch inventory. Historical merge parents remain available Git objects.

| Family / exact known source | Available source identity | Landing on supplied target | Comparison and disposition |
| --- | --- | --- | --- |
| `ci/drain-backend-tests` | `origin/ci/drain-backend-tests` at `033f1b9851be413ce1bbf38546c89e8d1c8c4b50` | `fe7f46249ecb19cebda42e7efe509c6dc499ea11` (#45) | Landing remains an ancestor of checked `origin/main`. `git diff --stat fe7f462 033f1b9` is empty (also `--quiet` exit 0): identical trees, fully reconciled; no recovery. |
| `feat/drain-insights-bridge` | `origin/feat/drain-insights-bridge` at `ba9e8830a39556801c8a95c502f2ad56b668e977` | `d42487630c67b2ce7b4723348b105b2ab521f0ed` (#44) | Landing remains an ancestor of checked `origin/main`. `git diff --stat d424876 ba9e883` is empty (also `--quiet` exit 0): identical trees, fully reconciled. Cross-repository acceptance remains separate. |
| `codex/scoped-annotation-access-release` | No live ref; historical merged tip `f48ed168eeb30c90f950f97155cb345e8d397bf5` is the second parent of #37 | `f5364365346d93a3aa01fd5fecf219090afe5410` (#37) | Both merged tip and landing are ancestors. That exact historical tip is included. Current auth, route and UI code evolved afterward; scoped access survives. Current tip and other wildcard variants remain unknown. |
| `codex/proposition-review-workspace-final` | Local ref at capture: `a6e713cc289cb833cbced2d71df8f9b9d9e80dd0`; current local and `origin/codex/proposition-review-workspace-final`: `d9ebbf92c92730e8aa90bbdbbf77a67b10296531`; historical merged tip `7ea40ea1d5f42def8c278e6591c07d8ce2bf9938` | `a6e713cc289cb833cbced2d71df8f9b9d9e80dd0` (#40) | The local ref supplied at capture (`a6e713c`), merged tip and workspace implementation `737ecb5964547092c8e45a2de083c3bebb2b1929` remain ancestors of checked `origin/main`. Only that historical local ref is fully included. Current tip `d9ebbf9` is a child of `a6e713c`, is not an ancestor, and is auto-save state, not recovery work (see below). Other wildcard variants remain unknown. |
| `fix/u10-deterministic-runner-config` | `origin/fix/u10-deterministic-runner-config` at `b039a869c8047258c1f984b649d383888b6b8236` | `bb576ac0830308091623018aa1546559ac4fa1a9` (#38) | Landing remains an ancestor of checked `origin/main`. `git diff --stat bb576ac b039a86` is empty (also `--quiet` exit 0): identical trees, fully reconciled; no recovery. |

At capture, the eight inclusion assertions were checked with
`git merge-base --is-ancestor <sha> 26e5c61` (exit 0 for all eight distinct
commits). `git show` established the merge parent relationships;
`git diff-tree` and `git diff` established the landed files and later evolution.
Commit subjects alone were not used as equivalence proof.

At review refresh, `git merge-base --is-ancestor <sha> origin/main` returned
exit 0 for all eight cited commits: `fe7f462`, `d424876`, `f536436`, `f48ed16`,
`a6e713c`, `7ea40ea`, `737ecb5` and `bb576ac`, against
`cffe049c51bc7197a8354c783af3d1843285479d`. The three source/landing tree
comparisons above are empty, resolving their squash-equivalence questions.

`git show --stat d9ebbf9` identifies `WIP: PreCompact auto-save`;
`git diff-tree --no-commit-id --name-only -r d9ebbf9` lists only
`.codex/hooks.json`, `.planning/HANDOFF.json`, `.planning/STATE.md`,
`.planning/phases/03-consolidated-system-status-chip/.continue-here.md` and
`AGENTS.md`. This is planning/agent auto-save state, with no application changes.
Its ancestry check against the same `origin/main` returned exit 1; it is not
included, but does not establish behavior recovery work.

### Current implementation examined

| Area | Current source evidence and preserved intent |
| --- | --- |
| Backend drain | `.github/workflows/tests.yml` runs on pull requests and pushes to `main`, using Python 3.13, uv 0.9.22, frozen dev dependencies and spaCy model 3.8.0. `backend/tests/test_cf_access.py` expires JWKS relative to the monotonic clock; `backend/tests/test_ontology_ingestion.py` supplies deterministic DNS. No withdrawn quarantine marker was restored. |
| Identity and interchange | `backend/app/services/proposition/source.py` stamps content IRIs on read without rewriting stored jobs; legacy IDs remain. `backend/app/services/export/propositions_exporter.py` emits the shared record and flat proposition NDJSON lines. `backend/pyproject.toml` and `backend/uv.lock` retain folio-propositions v0.4.0 at `bb62e5b6defdccd8d552b794e16bdc2267720628`. |
| Insights and post-job flow | `backend/app/services/insights_client.py` handles HTTP/protocol failures. `backend/app/services/post_job/flow.py` retains independent review/push choices, access gating, revision-aware overrides and interrupted-push recovery. `frontend/index.html` patches corpus status around dirty review edits. |
| Scoped access | `backend/app/api/auth.py` separates annotation access from admin access and checks same-origin cookie/Access writes. `backend/app/api/routes/gold.py` gates gold mutations. Current code incorporates the later Access and bridge changes. |
| Review workspace | `frontend/index.html` retains the context pane, single active candidate, source ordering, persisted review filter, navigation and dirty-edit guard. Later fast-gold queue, undo and gesture behavior remains in place. |
| U10 runner | `backend/eval/synthetic_runner.py` pins both feature flags and numeric scoring settings, records configuration, and restores settings in `finally`. The existing runner suite verifies successful-run restoration; execution-failure restoration is not directly tested there. |

## U2: fresh verification

All runs used the application/test tree at `00090d0` (identical to `26e5c61`
outside the plan), with no production or test edits. Python 3.13.11 and uv
0.9.22 were used. `uv sync --frozen --extra dev --python 3.13` and installation
of the workflow's exact spaCy 3.8.0 wheel succeeded. The initial `--offline`
sync exited 1 because the Python 3.13 pyarrow wheel was not cached; downloading
the locked dependencies resolved setup without changing either dependency file.

Tests ran with a clean environment, bytecode writes disabled, and separate
temporary job/feedback directories. Gold tests use isolated fixture copies;
automated gold validation does not constitute Damien's human U6 validation.
No live insights ingest or paid-provider evaluation was performed.

| Check | Exit | Result |
| --- | ---: | --- |
| Exact CI backend command | 0 | **1,230 passed, 0 failed, 10 skipped**, 6 warnings, 20.22 s. The ten skips were browser tests without a discoverable launchable Playwright package. |
| Default collection | 0 | **1,240 selected of 1,283; 43 deselected** by existing marker defaults. |
| Plan-focused suite | 0 | **240 passed, 0 failed, 10 skipped, 2 deselected**, 2 warnings, 14.43 s. Serial focused verification, not a substitute for the parallel CI run above. |
| Browser follow-up | 0 | **10 passed, 0 failed, 0 skipped**, 25.92 s, using Playwright 1.64.1 with cached Chromium headless shell revision 1248 (156.0.8078.4). This separately resolves every browser skip above. |
| Workflow structure | 0 | YAML parsed and PR/main triggers, working directory, Python/uv versions, frozen sync, model pin and exact pytest command checked. `actionlint` was unavailable; this is not an actionlint result. |

The warnings came from a deliberately short HMAC key in the rejected-token test,
FAISS SWIG types, and citeurl's escape sequence. They did not fail the checks.
Default exclusions remain `not slow and not demo_regen and not eval`; no marker,
assertion, timeout or test selection was weakened to obtain a pass.

### Focused test accounting

Paths below are relative to `backend/tests/`. Counts come from the fresh focused
run's JUnit results, not historical receipts.

| Files | Passed | Skipped |
| --- | ---: | ---: |
| `test_ontology_ingestion.py`, `test_cf_access.py` | 9 + 38 | 0 |
| `test_proposition_content_identity.py`, `test_propositions_export.py`, `test_proposition_byte_neutral.py` | 17 + 8 + 3 | 0 |
| `test_insights_client.py`, `test_insights_route.py` | 29 + 13 | 0 |
| `test_post_job_flow.py`, `test_post_job_access_and_recovery.py` | 28 + 18 | 0 |
| `test_admin_auth.py`, `test_gold_store.py`, `test_gold_validity.py`, `test_gold_validation.py` | 10 + 33 + 9 + 16 | 0 |
| `test_insights_frontend.py`, `test_post_job_frontend.py`, `test_frontend_assets.py` | 1 + 1 + 1 | 0 |
| `test_insights_browser.py`, `test_post_job_browser.py`, `test_fast_gold_browser.py` | 0 | 1 + 1 + 8 |
| `test_synthetic_runner.py` | 6 | 0 |

This includes the clock-relative JWKS expiry and deterministic DNS checks,
legacy-ID/content-IRI lookup, flat NDJSON parse rule, byte-neutral exports,
production parallel-path override preservation, retry/recovery, and successful
deterministic-runner settings restoration. Static frontend checks alone do not
prove rendered browser behavior.

The browser follow-up exercised the actual frontend with synthetic/intercepted
APIs: corpus connected/error/disconnected states, dirty edits surviving status
arrival and refresh, post-job preferences/access/retry/resubmission, and all eight
fast-gold queue/edit/keyboard/touch/undo scenarios at desktop and phone widths.
The original context-pane/one-item-lens interaction has no dedicated test; source
inspection and these evolved-workspace checks do not claim exhaustive coverage.

Playwright was installed only into temporary tooling, then passed through the
existing `FOLIO_ENRICH_PLAYWRIGHT_MODULE` hook. An initial 1.58.2 probe could not
find its matching browser; its browser installer also lacked support for the
host platform. Version 1.64.1 used an already cached matching browser and
launched successfully. No repository dependency or test runner was modified.

### Reproduction commands

From `backend`, after the locked install and pinned model installation:

```sh
audit_dir=$(mktemp -d)
export PYTHONDONTWRITEBYTECODE=1
export FOLIO_ENRICH_JOBS_DIR="$audit_dir/jobs"
export FOLIO_ENRICH_FEEDBACK_DIR="$audit_dir/feedback"

uv run --no-sync python -m pytest tests/ -q -n 2 -ra -p no:cacheprovider
uv run --no-sync python -m pytest tests/ --collect-only -q -p no:cacheprovider

uv run --no-sync python -m pytest \
  tests/test_ontology_ingestion.py tests/test_cf_access.py \
  tests/test_proposition_content_identity.py tests/test_propositions_export.py \
  tests/test_proposition_byte_neutral.py tests/test_insights_client.py \
  tests/test_insights_route.py tests/test_post_job_flow.py \
  tests/test_post_job_access_and_recovery.py tests/test_admin_auth.py \
  tests/test_gold_store.py tests/test_gold_validity.py tests/test_gold_validation.py \
  tests/test_insights_browser.py tests/test_post_job_browser.py \
  tests/test_fast_gold_browser.py tests/test_insights_frontend.py \
  tests/test_post_job_frontend.py tests/test_frontend_assets.py \
  tests/test_synthetic_runner.py -q -ra -p no:cacheprovider

# Select a Playwright 1.64.1 package with its matching browser installed.
FOLIO_ENRICH_PLAYWRIGHT_MODULE="$playwright_module" \
  uv run --no-sync python -m pytest tests/test_insights_browser.py \
  tests/test_post_job_browser.py tests/test_fast_gold_browser.py \
  -q -ra -p no:cacheprovider
```

The actual full/focused runs also used `env -i PATH="$PATH"` with the displayed
test-state variables, and outer bounds of 240/180 seconds respectively. Both
finished normally before those bounds. Temporary logs and tooling are not
durable deliverables; this sanitized receipt records their outcomes.
The browser follow-up used the same clean-environment isolation and a 240-second
outer bound, completing normally. It did not rerun the entire suite with browser
tooling enabled; its result is reported separately from the CI command.

## U3: controller handoff and residuals

No behavior recovery unit is warranted by the available sources and checks.
Publish this receipt with the committed plan; do not open duplicate recovery
PRs for the represented landings. If a later source comparison demonstrates a
missing change, identify its exact source SHA, minimal patch and preserving
regression test, then assign one source branch per recovery PR.

The controller still needs to:

1. Confirm the intended publication target and repeat any affected behavior checks
   on the newer base. Ancestry was refreshed against `origin/main` at
   `cffe049c51bc7197a8354c783af3d1843285479d`; U2 remains historical evidence
   from `26e5c61`.
2. Supply the current scoped access release tip and a complete enumeration of
   both wildcard families. The three named squash sources are fully reconciled;
   their exact tips and equivalence are no longer pending. An authoritative
   deleted/unavailable disposition may close remaining inventory with a stated
   limitation; it cannot establish squash equivalence.
3. Supply the chief plan's Goal Capsule and campaign R11, R15, R16, R17, R19 and
   R20 excerpts. That repository is not mounted here, so agreement with its
   unseen contents remains unverified. The supplied standing lane rules were
   followed.

The origin-context handoff is located at
`docs/handoffs/2026-10-26-unified-proposition-engine-brainstorm.md` on
`origin/feat/unified-proposition-engine` (`7b71926`), with path-history commits
`56b01db`, `d179029`, `7f481a2` and `7b71926`. `git ls-tree` confirms it is
present on that branch and absent on checked `origin/main`. It is no longer a
missing-file controller input; this location evidence does not infer Phase B scope.

These are controller inputs, not Damien-only decisions. Palsgraf gold review,
human U6 validation and deferred proposition fields remain outside this item.
Cross-repository ingest/status acceptance remains outside this enrich-only
audit, as recorded in `docs/bridge-retirement-2026-10-09.md`.

No new test was added for this documentation-only audit; existing behavior was
verified unchanged. No frontend change was made, so the campaign's changed-page
screenshot requirement does not apply. No migration, data rewrite, release,
new outside service, branch deletion, push, PR or deployment was performed.
