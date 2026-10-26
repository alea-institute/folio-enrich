---
title: Fe-3 Enrich-Insights Bridge Reconciliation - Plan
type: fix
date: 2026-10-26
artifact_contract: ce-unified-plan/v1
product_contract_source: drawdown-mandate
origin: docs/plans/2026-10-09-0645-feat-insights-bridge-plan.md
execution: code
item_id: fe-3
item_kind: planned
---

# Fe-3 Enrich-Insights Bridge Reconciliation - Plan

## Goal Capsule

- **Objective:** Users can push a document's propositions to folio-insights and see the resulting corpus status in the Propositions tab without manually refreshing or losing review edits.
- **Means:** Preserve the landed bridge, connect successful push observations to its existing status refresh path, and close the enrich-side verification gaps (KTD1-KTD4).
- **Authority:** The fe-3 mandate and supplied campaign standing rules; chief repository `docs/plans/2026-10-26-0705-feat-codex-drawdown-campaign-plan.md`, Goal Capsule and R11, R15, R16, R17, R19, R20; the origin bridge plan; Phase A and the Palsgraf reconciliation cited below. The chief document itself was unavailable; the source limitation below is a build prerequisite.
- **Scope:** Only fe-3 on `drawdown/fe-3`. This document plans the remaining enrich work; it does not supersede the origin plan's requirements for other repositories.
- **Delivery:** This stage commits this plan only. The build stage implements and verifies locally; the controller publishes the branch and PR, and the campaign merge gate owns merging. No remote, login, credential discovery, or deployment belongs in this clone.

---

## Product Contract

### Summary

Refresh the corpus view once when the browser learns that a push succeeded, using the existing status API and preserving the active review form. Verify the already-landed identity, export, ingest-client, and review/push contracts, then record actual browser and backend results separately from cross-repository evidence.

### Problem Frame

The mandate describes a stranded bridge, but the supplied checkout already contains its merge. Commit `d42487630c67b2ce7b4723348b105b2ab521f0ed` landed identity stamping, exports, the status panel, and post-job review/push in PR #44. The clean planning base is `26e5c61b44e3165d3f2bfad5214516a6d6dcede3`, which also contains backend CI and fast annotation changes. There is no local `main`, original bridge branch, or remote ref to establish anything newer than that supplied snapshot.

One remaining integration defect is visible in the source: `ensureInsightsStatus` retains each job's status result, while `applyPostJobPayload` updates push chips without invalidating that result. A successful push can therefore coexist with a stale “Not in corpus” row. Calling the existing forced-refresh path alone would miss the case where a pre-push status request is still loading.

The historical receipt `docs/bridge-retirement-2026-10-09.md` also leaves full-suite, browser, and real cross-repository verification open. Neither that receipt nor the existence of tests establishes a pass at this base. No tests or application probes were run during this planning stage.

### Starting-state evidence and requirement trace

`Bridge R...`, `Bridge F...`, and `Bridge AE...` refer to the origin plan. `Campaign R...` refers to the chief campaign; its cited rules were supplied in the mandate. Unqualified IDs belong to this plan.

| Origin scope | Observed state at the supplied base | Fe-3 disposition |
| --- | --- | --- |
| Bridge R1-R6, AE1-AE2: shared library identity/lifecycle | `backend/pyproject.toml` and `backend/uv.lock` pin `folio-propositions` v0.4.0 | Consume the existing pin; no library release or migration |
| Bridge R7-R10, F1, AE3: identities and exports | `backend/app/services/proposition/source.py`, `identity.py`, `backend/app/services/export/propositions_exporter.py`; existing identity/export tests | Preserve and verify in U3 |
| Bridge R11-R16, F1, AE4: receiver ingestion, parity, corpus queries | Enrich has `backend/app/services/insights_client.py` and `backend/scripts/export_insights_fixture.py`; the Insights receiver is not in this clone | Verify the local sender; retain the receiver gate described in U3 |
| Bridge R17-R19, F2, AE5: corpus status during review | `backend/app/api/routes/insights.py` and the corpus functions in `frontend/index.html` exist | Correct freshness in U1-U2; verify in U3 |
| Bridge R20-R22: sibling bridge retirement | `docs/bridge-retirement-2026-10-09.md` records the enrich boundary | Other repositories retain ownership; no retirement work here |
| Bridge R23-R28, F3: independent review and push choices | `backend/app/services/post_job/flow.py`, routes, storage revisions, controls, and regression tests exist | Preserve the lifecycle and cover its status-panel handoff |

### Key Decisions

- **Keep the document/corpus bridge.** (session-settled: user-directed — chosen over merging or porting Insights into Enrich: document work and corpus work retain separate ownership.) Governs R1, R5, R7; see the origin's bridge decision.
- **Retain independent review and push choices.** (session-settled: user-directed — chosen over pull-only, per-job opt-in only, and push-everything: users retain saved defaults and per-job overrides.) Governs R1, R5; see Bridge R23-R28.
- **Finish evidenced work, then durable hygiene.** (session-settled: user-directed — chosen over speculative features when worthwhile work runs out: the campaign has no user time through 2026-10-30.) Governs R6-R8. No human annotation or taste decision is a prerequisite for this fix.

### Requirements

**Status freshness and review continuity**

- R1. Each newly observed successful push attempt invalidates that job's prior corpus status and causes one fresh read when the completed job is current; only the returned status determines corpus membership.
- R2. Repeated observations of the same success do not fetch again, while a later successful attempt can refresh independently.
- R3. Success arriving during an existing status request leaves one pending refresh after that request settles; an obsolete response cannot clear the invalidation or become the final displayed result.
- R4. Refresh preserves unsaved fields, drafts, selection/gesture state, focus, and save-state protections, and never repaints another job with an old response.
- R5. Existing manual refresh, disconnected/error presentation, review/push preferences, retries, authorization, identity stamping, exports, and disabled-feature behavior continue to work; the correction adds no automatic retry or periodic sync.

**Evidence and delivery**

- R6. Add behavioral browser regressions for the changed handoff, retain every existing test and assertion, and commit a Playwright screenshot under `docs/plans/evidence/` for the frontend change (Campaign R15-R16).
- R7. Report local sender contracts, browser behavior, the configured default backend suite, and actual receiver integration as separate evidence levels; skipped or unavailable checks remain open.
- R8. Keep this one planned item on `drawdown/fe-3`, with no new schema fields, migration, stored-data rewrite, package release, outside service, spend, credential/security-setting change, real-person send, or unbacked deletion (Campaign R11, R15-R17, R19-R20).

### Acceptance Examples

- AE1. Covers R1-R4. With an absent corpus row cached and a dirty disposition field, completing the existing review/push flow leads to one fresh status read. A returned present row and the successful push chip appear while the edited value and original review-card node survive.
- AE2. Covers R2-R3. A pre-push status request is held open when success arrives. Releasing it causes exactly one follow-up request; repeating that success causes none, and a later successful attempt causes one more.
- AE3. Covers R4-R5. Navigating away while a status request is held does not repaint the new job. Returning to an invalidated old job obtains fresh facts. A failed push triggers no success refresh; a failed status read uses the existing unavailable state and manual retry path.

### Scope Boundaries

- Application changes are confined to the corpus cache and post-job UI handoff in `frontend/index.html`; tests and public-safe evidence support that change.
- Preserve Palsgraf gold, U6 human validation, and the deferred polarity/per-opinion-stance fields from `docs/plans/2026-09-30-palsgraf-cycle-1-reconciliation.md`. Phase A's human cycle and adoption decisions remain outside this item.
- Completing review currently releases a gate before exporting `job.result.propositions`; it does not promote gold-session edits or certify human validation. This item preserves that behavior.
- Considered and not built: a new background sync loop, eventual-consistency retries, or optimistic “present” rows. A single status read plus the existing manual control resolves this defect without inventing corpus facts; evidence of a separate receiver consistency contract would require separate planning.
- Considered and not built: a new API, persistent bookkeeping, frontend framework, or browser-discovery overhaul. Existing attempt fields, in-memory cache, and browser harnesses cover the change.

#### Deferred to Follow-Up Work

The controller retains cross-repository ingestion/parity reconciliation under the origin plan. Branch triage (fe-1), CI promotion (fe-2), annotation polish (fe-4), and NER/dependency hygiene (fe-5) remain separate mandates. No implementation of those items is included here.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Reconcile from the landed implementation.** U1-U3 address R1-R7 against the supplied base. Reapplying the former bridge branch would duplicate already-merged behavior and risk later annotation fixes.
- KTD2. **Identify success by job and existing `push_attempts`.** Keep the last observed successful attempt in browser memory for the same lifetime as the job's corpus cache. Evaluate it only after `applyPostJobPayload` accepts the job and response sequence. A newly observed historical success counts once; first load without cached facts needs only its first current read. This implements R1-R2 without new server fields.
- KTD3. **Coalesce invalidation with the existing request lifecycle.** Retain a pending invalidation when status is loading, and consume it with one subsequent read after the current request settles. Do not delete a loading cache entry to launch an overlapping request. If the user changes jobs, leave the old job stale until its next normal load. A still-current completed job refreshes once even if its Propositions tab is hidden. This implements R3-R4.
- KTD4. **Reuse the safe rendering path and real-page tests.** Status results continue through `applyInsightsStatusUpdate` and `patchActivePropositionCorpusRow`; push completion must not directly rebuild the tab. Extend the existing route-stubbed Playwright harness, which already holds responses and checks dirty-card identity. This implements R4-R6.
- KTD5. **Keep execution evidence bounded and truthful.** Use the locked backend setup and existing default test selection; preserve intentional `slow`, `demo_regen`, and `eval` exclusions. Browser skips do not satisfy R6, and HTTP mocks do not satisfy receiver integration in R7.

### High-Level Technical Design

```mermaid
sequenceDiagram
    participant P as Existing post-job response handler
    participant C as Per-job corpus cache
    participant E as Enrich status API
    participant V as Corpus banner and active card
    P->>P: Accept current job and response sequence
    P->>C: Observe new successful attempt
    alt Status read already in flight
        C->>C: Retain one pending invalidation
        E-->>C: Earlier read settles
        C->>C: Keep invalidation; discard obsolete settlement
    end
    alt Job still current
        C->>E: Read status once for latest invalidation
        E-->>C: Current facts or unavailable state
        C->>V: Apply existing safe status update
    else User changed jobs
        C->>C: Retain stale marker until next normal load
    end
```

Only browser bookkeeping changes. Enrich still owns payload creation and presentation; folio-propositions owns shared identity/schema, and Insights owns corpus writes and reported corpus facts.

### Assumptions and Source Limitations

- **Supplied-base assumption:** `26e5c61` is the controller's main snapshot for this lane. Its contents and bridge ancestry were inspected; remote freshness was not verified and must not be claimed.
- **Unavailable authority:** The chief campaign plan, `ops/drawdown/mandates/_common.md`, and `docs/handoffs/2026-10-26-unified-proposition-engine-brainstorm.md` are absent from the available checkout/workspace. The handoff is also absent from the other available branch. The supplied campaign rules constrain this draft, but its chief Goal Capsule was not read. Before build dispatch, the controller must supply or check the Goal Capsule, the cited campaign R-IDs, and relevant handoff constraints against this plan. No credential or remote search is an authorized recovery path.
- **Repo instructions:** No `AGENTS.md` or `CLAUDE.md` exists at the planning HEAD. The other available branch's `AGENTS.md` confirms Python/FastAPI, the backend pytest suite, and the single-file vanilla frontend; it does not authorize importing that branch's work.
- **Execution environment:** Node, a launchable Playwright Chromium, locked Python dependencies, and the pinned spaCy model are build-time prerequisites. The sandbox denies Unix sockets, so browser launch may require the controller's permitted runner. No runtime availability is asserted here.
- **Receiver evidence:** No folio-insights checkout or running receiver was supplied. Actual ingest/idempotence/query parity remains a controller integration prerequisite, separate from the local fix. This is an infrastructure/source handoff, not a request for human review or new credentials.

### Sequencing and Risks

U1 establishes the missing regression, U2 fixes its cause, and U3 verifies compatibility and records evidence. The first two units require the authority check above; local work can then proceed independently of receiver availability.

The main implementation risks are losing a refresh behind an in-flight request, re-fetching on every render, and wiping unsaved annotation work. KTD2-KTD4 and U1's controlled-response scenarios target those exact paths. A failed refresh leaves existing error presentation; it does not retry or change the successful push result.

---

## Implementation Units

### U1. Add browser regressions for the push/status handoff

- **Goal:** Reproduce the stale corpus view and cover the request races that a direct forced-refresh call misses.
- **Requirements:** R1-R6; AE1-AE3; Bridge R18-R19, R27-R28.
- **Dependencies:** Controller authority check; current browser harness and toolchain.
- **Files:** `backend/tests/browser/insights_panel.cjs`, `backend/tests/test_insights_browser.py`; extend fixtures in `backend/tests/browser/post_job_panel.cjs` and assertions in `backend/tests/test_post_job_browser.py` only where the new status request affects their existing cases.
- **Approach:** Extend the existing synthetic job fixtures with post-job responses, successful attempt counters, sequenced corpus results, and explicit held-response controls. Drive completion/retry through existing UI actions where relevant; retain all original assertions. Use response barriers and conditions instead of timing sleeps.
- **Patterns:** The current insights harness routes the real `frontend/index.html`, records page errors and request counts, and checks the original dirty-card DOM node.
- **Execution note:** Establish the stale-cache regression before changing production code.
- **Test scenarios:**
  1. Covers AE1. Cached absent facts become the returned present facts after success, with one new request and unchanged dirty field/card identity.
  2. Covers AE2. Hold a pre-push response; success queues one follow-up. The old response cannot finish as authoritative status.
  3. Repeat the same success through poll, render, and revisit: no additional read. Observe a higher successful `push_attempts` without its intermediate pending state: one new read.
  4. First observe an already-pushed job with no status cache: one initial read. Success while the tab is hidden refreshes once, and opening it reuses that result.
  5. Covers AE3. Reject stale post-job responses; switch jobs with a held status response and pending invalidation; return and refresh the correct job without repainting another.
  6. Failed or unconfigured push adds no automatic read. A post-success status error shows existing unavailable feedback without a loop; manual Refresh still works.
  7. A successful report with skipped/refused records displays actual returned absence rather than assuming every proposition entered the corpus.
  8. Preserve the existing unsaved-field regression and add a focused hand-added-draft/focus check for the automatic refresh path; assert zero browser page errors.
- **Verification:** The new core regression fails on the planning base for the stale-cache behavior. Existing cases remain intact; unavailable browser execution is recorded rather than treated as a pass.

### U2. Refresh corpus facts after each newly observed successful push

- **Goal:** Make the post-job chip and corpus view reflect the same completed push without disrupting review.
- **Requirements:** R1-R5; KTD1-KTD4; AE1-AE3.
- **Dependencies:** U1.
- **Files:** `frontend/index.html`; U1 test files for final regression assertions.
- **Approach:** Connect accepted post-job payloads to success-attempt bookkeeping (KTD2), carry invalidation through status-request completion (KTD3), and apply results through the existing safe rendering path (KTD4). Keep existing current-job and response-sequence guards before any new side effect.
- **Patterns:** `applyPostJobPayload`, `ensureInsightsStatus`, `propositionReviewBusy`, `applyInsightsStatusUpdate`, and `patchActivePropositionCorpusRow`.
- **Test scenarios:** All eight U1 cases must pass, including exact request counts and a late response after navigation. Existing manual-refresh and post-job action cases continue passing.
- **Verification:** No new route, dependency, persistent field, polling timer, or gold-data change appears in the diff. The UI uses server-returned corpus facts and preserves review input.

### U3. Verify the landed contracts and record completion evidence

- **Goal:** Give the controller current-revision evidence for the enrich bridge and clearly identify remaining receiver gates.
- **Requirements:** R5-R8; Bridge R7-R19 and R23-R28; Bridge AE3-AE5.
- **Dependencies:** U2; build runner with required dependencies and browser capability. Receiver certification additionally requires the controller's existing Insights environment.
- **Files:** `docs/plans/evidence/fe-3-insights-bridge-verification.md`, `docs/plans/evidence/fe-3-insights-after-push.png`; existing bridge tests listed in the Verification Contract; U1 browser harness may accept an optional screenshot destination without changing its normal results.
- **Approach:** Run the focused contracts and configured default suite, execute the real-page browser scenarios, and capture the changed Propositions page. Record the tested revision, commands, counts, skips, environment limits, screenshot path, and local-versus-receiver evidence. Leave historical receipts intact and link them as history.
- **Test scenarios:**
  1. Bridge AE3: identical source/span across two jobs keeps different legacy IDs and matching content IRIs; legacy records stamp on read without rewriting stored files.
  2. JSON validates against the pinned shared model; NDJSON keeps its flat proposition lines; existing exports and feature-off behavior retain their regression guards.
  3. Status deduplication/chunking, zero-IRI health, sanitized failures, and the four review/push combinations retain their existing outcomes and authorization checks.
  4. Bridge AE5 and AE1-AE3 above execute in Chromium, preserving review saves while disconnected and showing the updated corpus state after success.
- **Receiver gate:** The controller uses an existing temporary Insights corpus and synthetic/public-safe exported document to check identity parity, ingest acceptance, repeat-ingest idempotence, expected hypothesis IRIs via corpus query, and returned status. Record both repository revisions and actual results. Enrich mocks and copied parsing rules cannot close Bridge AE1/AE4. No sibling code changes, receiver installation/service signup, or production data is part of this unit.
- **Verification:** The receipt reports what actually ran. If the sandbox cannot launch Chromium or reach the supplied receiver, record the exact blocked check and required controller runner; do not disable tests or claim bridge-wide completion. No new tests are needed for the receipt itself.

---

## Verification Contract

Build-stage commands run from `backend/` in the existing locked environment. Dependency preparation follows `.github/workflows/tests.yml`; preserve `backend/pyproject.toml` and `backend/uv.lock`.

| Gate | Check | Done signal |
| --- | --- | --- |
| Identity/export | `uv run --no-sync python -m pytest tests/test_proposition_content_identity.py tests/test_propositions_export.py tests/test_proposition_byte_neutral.py -q -ra -p no:cacheprovider` | Existing identity, interchange, and byte-neutral assertions pass |
| Status and post-job contracts | `uv run --no-sync python -m pytest tests/test_insights_client.py tests/test_insights_route.py tests/test_insights_frontend.py tests/test_post_job_flow.py tests/test_post_job_access_and_recovery.py tests/test_post_job_frontend.py -q -ra -p no:cacheprovider` | No failed contract/access/recovery checks; any infrastructure limit recorded |
| Browser behavior | `uv run --no-sync python -m pytest tests/test_insights_browser.py tests/test_post_job_browser.py -q -ra -p no:cacheprovider` | Actual Chromium execution, U1 assertions satisfied, zero page errors; a skip leaves this gate open |
| Default backend suite | `uv run --no-sync python -m pytest tests/ -q -n 2 -ra -p no:cacheprovider` | Pass with the existing configured marker selection, all counts and skips recorded; not described as all optional evaluations |
| Screenshot | Capture the post-push Propositions tab with the updated corpus row and preserved edit, using the synthetic fixture | Commit `docs/plans/evidence/fe-3-insights-after-push.png` and inspect its visible state; final build handoff names it as `SCREENSHOT: <path>` |
| Receiver contract | U3's real Insights ingest, repeat-ingest, query, and status checks | Separate receipt with both revisions, or explicitly unresolved controller gate |

Existing test exclusions are not permission to add new exclusions. Reproduce unexpected failures against the supplied base before attributing them to this change; fix only fe-3 regressions and record unrelated failures. Do not weaken tests, delete evidence, access real credentials, or change security settings to obtain a green result.

---

## Definition of Done

- The controller has reconciled the unavailable authority sources before implementation starts.
- U1-U2 deliver R1-R5 with new browser regressions and every pre-existing assertion preserved.
- The focused checks, configured default backend suite, and actual browser scenarios have current-revision results; U3's screenshot and public-safe receipt are committed.
- Receiver evidence is either verified by the controller or explicitly open; local completion is never presented as completion of the origin's entire cross-repository plan.
- The diff stays within fe-3, contains no abandoned-attempt code or generated scratch, and preserves Palsgraf/U6 and deferred schema decisions.
- The local branch is ready for the controller's publication process. No worker push, PR, remote addition, credential search, or deployment occurs.

---

## Sources

- `docs/plans/2026-10-09-0645-feat-insights-bridge-plan.md`: original product contract and cross-repository ownership.
- `docs/plans/2026-10-09-bridge-lane-completion-plan.md` and `docs/bridge-retirement-2026-10-09.md`: historical implementation and unresolved verification gates.
- `docs/plans/2026-08-16-2234-feat-proposition-system-phase-a-plan.md`: annotation/gold scope and byte-neutral boundaries; U6 is excluded here.
- `docs/plans/2026-09-30-palsgraf-cycle-1-reconciliation.md`: preserves human-validation and deferred-field decisions.
- `frontend/index.html`: corpus cache, safe review rendering, and accepted post-job payload path.
- `backend/tests/browser/insights_panel.cjs`, `backend/tests/browser/post_job_panel.cjs`, and their Python wrappers: existing browser assertion patterns and explicit skip behavior.
- `.github/workflows/tests.yml`, `backend/pyproject.toml`, and `backend/uv.lock`: existing verification configuration and shared-schema pin.
