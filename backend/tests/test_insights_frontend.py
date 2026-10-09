"""Smoke test: the served index.html carries the folio-insights panel hooks."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index_contains_corpus_status_panel_hooks():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    # Fetch path and per-job cache
    assert "/insights-status" in html
    assert "insightsStatusCache" in html
    # Tab-level banner + refresh control, including the not-connected copy (AE5)
    assert 'id="propositionCorpusBanner"' in html
    assert 'id="refreshCorpusStatusBtn"' in html
    assert "folio-insights not connected — corpus status unavailable" in html
    # Card row, disclosure, absent state, copy with execCommand fallback
    assert "renderPropositionCorpusRow" in html
    assert "Related (${related.length}) · Contesting (${contesting.length})" in html
    assert "Not in corpus" in html
    assert "execCommand('copy')" in html
