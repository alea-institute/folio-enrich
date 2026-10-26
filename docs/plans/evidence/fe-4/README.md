# fe-4 annotation UI evidence

Implementation and review fixes are committed locally on `drawdown/fe-4`. The implementation was verified at `3d99e72`; this receipt and the screenshots are the only subsequent changes.

Plan: `docs/plans/2026-10-26-1227-feat-annotation-ui-polish-plan.md`.

## Results

| Check | Result |
|---|---|
| Backend suite, existing marker policy | 1,252 passed; no failures or skips; 4 existing dependency/test warnings |
| Synthetic annotation browser scenarios | 20 passed, each at 1280 × 950 and 390 × 950; 40 scenario/viewport runs |
| Browser runtime errors | None in the annotation scenarios |
| Screenshot evidence | 36 captures: nine states, both viewports, light and dark themes |
| Existing tests | All eight original annotation scenarios retained; hand-added assertions strengthened |
| Review | Focused correctness review and a separate adversarial review; both findings fixed and regression-tested |
| Diff whitespace | `git diff --check` passed |

Commands run from `backend/`:

```sh
uv sync --frozen --extra dev
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
uv run --no-sync python -m pytest tests/ -q -n 2 -ra -p no:cacheprovider
FAST_ANNOTATION_SCREENSHOTS=../docs/plans/evidence/fe-4 uv run --no-sync python -m pytest tests/test_fast_gold_browser.py -q -ra -p no:cacheprovider
```

The first eight-scenario browser baseline passed. The first backend run lacked the spaCy model already required by CI and produced 87 failures. Installing that exact model resolved the dependency gap; the final suite passed. Shell startup printed the sandbox's expected stream-file-descriptor warnings, but Chromium launched and every browser scenario executed. No launch failure or skip is counted as acceptance.

The page is the real `frontend/index.html`, with synthetic jobs and route-intercepted API responses at `/?job=<synthetic-id>&tab=propositions`, including pinned-session links. No running backend or external annotation service is needed. The screenshot option is opt-in; ordinary browser tests write no repository screenshots.

## Behavioral coverage

| Plan coverage | Evidence |
|---|---|
| U1 / R1, R5 / AE1–AE2 | Repeated keyboard navigation, boundary focus, dirty source activation, shortcut targeting, composition and modal guards, filter/help focus, background save/corpus updates, text selections and drafts |
| U2 / R2–R3 / AE3 | Review labels independent of legal disposition; draft and hand-added states; no document, processing, failed document, no session, no candidates, read-only filter recovery, and finished-queue browsing |
| U3 / R4 / AE4–AE5 | Persistent session and completeness errors; lookup-only retries; pinned-session recovery; completeness retry without repeated writes; field-associated validation; escaped failure details and stale-result rejection |
| R6 | Existing undo, failed-save retry, same-type approval, held-key, multitouch, swipe, gold validity, access and byte-neutrality tests pass |
| R7–R8 | Executed browser checks and committed evidence; local publication boundary preserved |

New tests failed before the corresponding fixes: navigation dropped focus, source-mark shortcuts acted on another card, labels and empty states lacked context, read failures lacked recovery, and validation lacked inline errors. The additional review regressions reproduced an older lookup overwriting a saved classification and pinned-session failure bypassing recovery. Both now pass. The lookup regression covers writes pending when a read starts and writes started afterward.

Simplification preserved the proof tests and replaced nested completeness-message conditionals with ordered returns. Review found no remaining actionable issues after the fixes. Additional learning documentation was unnecessary because the plan and regression tests carry the reasoning.

## Screenshots

Representative captures were inspected across all nine states, both widths, and both themes. Inspection confirmed visible focus, contextual recovery controls, inline validation, and readable source highlights in dark mode. These are synthetic UI states, not human validation or live gold records.

| State | Desktop light | Desktop dark | Phone light | Phone dark |
|---|---|---|---|---|
| Focused review | [1280 light](focus-review-1280-light.png) | [1280 dark](focus-review-1280-dark.png) | [390 light](focus-review-390-light.png) | [390 dark](focus-review-390-dark.png) |
| Save failure | [1280 light](states-save-error-1280-light.png) | [1280 dark](states-save-error-1280-dark.png) | [390 light](states-save-error-390-light.png) | [390 dark](states-save-error-390-dark.png) |
| Empty reviewed filter | [1280 light](empty-reviewed-1280-light.png) | [1280 dark](empty-reviewed-1280-dark.png) | [390 light](empty-reviewed-390-light.png) | [390 dark](empty-reviewed-390-dark.png) |
| No candidates | [1280 light](empty-no-candidates-1280-light.png) | [1280 dark](empty-no-candidates-1280-dark.png) | [390 light](empty-no-candidates-390-light.png) | [390 dark](empty-no-candidates-390-dark.png) |
| Session lookup failure | [1280 light](lookup-error-1280-light.png) | [1280 dark](lookup-error-1280-dark.png) | [390 light](lookup-error-390-light.png) | [390 dark](lookup-error-390-dark.png) |
| Lookup recovered without a session | [1280 light](lookup-recovered-1280-light.png) | [1280 dark](lookup-recovered-1280-dark.png) | [390 light](lookup-recovered-390-light.png) | [390 dark](lookup-recovered-390-dark.png) |
| Completeness failure after save | [1280 light](completeness-error-1280-light.png) | [1280 dark](completeness-error-1280-dark.png) | [390 light](completeness-error-390-light.png) | [390 dark](completeness-error-390-dark.png) |
| Completeness recovered with edits retained | [1280 light](completeness-recovered-1280-light.png) | [1280 dark](completeness-recovered-1280-dark.png) | [390 light](completeness-recovered-390-light.png) | [390 dark](completeness-recovered-390-dark.png) |
| Inline validation | [1280 light](validation-error-1280-light.png) | [1280 dark](validation-error-1280-dark.png) | [390 light](validation-error-390-light.png) | [390 dark](validation-error-390-dark.png) |

## Controller acceptance boundary

This clone has no remote; no push, PR, merge, or deployment was attempted. The controller owns publication and the campaign merge gate. The campaign plan/common mandate and the named unified-proposition brainstorm were unavailable in this clone. The controller must reconcile those sources before campaign acceptance, as the implementation plan records; the build used the supplied standing rules.

No schema migration, data rewrite, package release, outside service, gold-record edit, or human U6 validation is included. No human decision or held change was needed for this implementation.
