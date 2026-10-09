"""JS-executing browser test for the post-job review/push card.

Runs ``tests/browser/post_job_panel.cjs`` under Node + Playwright against the
real ``frontend/index.html`` (served and API-stubbed via ``page.route``; no
backend process or port). Covers: localStorage preferences prefill the
submission toggles, the push toggle is disabled without push access, chips and
actions for awaiting / pushed / failed jobs (Retry on failed), and a resubmit
after a completed job showing the new job's running state.

Skips cleanly when Node, Playwright or a launchable Chromium is unavailable
(``FOLIO_ENRICH_PLAYWRIGHT_MODULE`` picks a package explicitly).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from app.services.post_job import flow

from tests.browser_support import playwright_module
from tests.helpers import make_job

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
SCRIPT = Path(__file__).parent / "browser" / "post_job_panel.cjs"


def _state(**fields) -> dict:
    state = flow.initial_state(False, True)
    for key, value in fields.items():
        setattr(state, key, value)
    return state.model_dump(mode="json")


def _fixture() -> dict:
    jobs = {name: json.loads(make_job(text="We hold that the rule applies.").model_dump_json())
            for name in ("awaiting", "pushed", "failed")}
    return {
        "jobs": jobs,
        "runningJobId": str(uuid.uuid4()),
        "postJob": {
            "awaiting": _state(review="required", review_status="awaiting_review", push_status="waiting_for_review"),
            "pushed": _state(review_status="not_required", push_status="pushed", push_attempts=1,
                             last_push_report={"created": 3, "existing": 1, "skipped": 0, "refused": 0}),
            "failed": _state(review_status="not_required", push_status="failed", push_attempts=1,
                             last_push_error="folio-insights returned a server error (503)."),
        },
    }


@pytest.mark.timeout(150)
def test_post_job_panel_in_browser(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = playwright_module(node)
    if module is None:
        pytest.skip("No Playwright package with a launchable Chromium (set FOLIO_ENRICH_PLAYWRIGHT_MODULE)")
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(_fixture()))

    run = subprocess.run(
        [node, str(SCRIPT), module, str(FRONTEND), str(fixture_path)],
        capture_output=True, text=True, timeout=140, check=False,
    )
    if run.returncode == 3:
        pytest.skip(f"Playwright browser unavailable: {run.stderr.strip()[:200]}")
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])

    assert out["prefill"] == {"review": True, "push": True, "heading": "Next job"}

    assert out["noAccess"]["pushChecked"] is False
    assert "annotation access" in out["noAccess"]["note"]

    assert out["awaiting"]["chips"] == "Review: awaitingInsights: waiting for review"
    assert out["awaiting"]["completeVisible"] is True
    assert out["awaiting"]["barCompleteVisible"] is True
    assert out["awaiting"]["retryVisible"] is False

    assert out["pushed"]["chips"] == "Review: skippedInsights: pushed (3 new, 1 existing)"
    assert out["pushed"]["retryVisible"] is False
    assert out["pushed"]["completeVisible"] is False
    assert out["pushed"]["heading"] == "This job"

    assert out["failed"]["chips"] == "Review: skippedInsights: failed"
    assert out["failed"]["retryVisible"] is True
    assert out["failed"]["title"] == "folio-insights returned a server error (503)."
    assert out["failed"]["afterRetry"] == "Review: skippedInsights: pushed (3 new, 1 existing)"
    assert out["failed"]["retryVisibleAfter"] is False

    resubmit = out["resubmit"]
    assert resubmit["heading"] == "This job"
    assert resubmit["chips"] == "Review: after the runInsights: after the run"
    assert resubmit["togglesDisabled"] is True
    assert resubmit["submitted"] == {"review": False, "push": True}

    assert out["errors"] == []
