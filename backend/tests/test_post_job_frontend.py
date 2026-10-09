"""Smoke test: the served index.html carries the post-job review/push controls."""

from __future__ import annotations

import re

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_index_contains_post_job_controls():
    html = client.get("/").text
    # Submission + completion controls, status chips, review and retry actions
    for element_id in (
        "postJobPanel", "postJobReviewToggle", "postJobPushToggle", "postJobChips",
        "postJobCompleteReviewBtn", "postJobRetryBtn", "propositionPostJobBar",
        "propositionCompleteReviewBtn", "settingsPostJobReview", "settingsPostJobPush",
    ):
        assert f'id="{element_id}"' in html, element_id
    # Browser preferences (localStorage keys) and the request fields they feed
    assert "'postJobReview'" in html and "'postJobPush'" in html
    assert "body.review_before_continuing" in html and "body.push_to_insights" in html
    # Routes the UI calls
    for path in ("/post-job", "/review/complete", "/insights-push"):
        assert path in html
    # Status changes are announced
    assert re.search(r'id="postJobChips"[^>]*aria-live="polite"', html)
