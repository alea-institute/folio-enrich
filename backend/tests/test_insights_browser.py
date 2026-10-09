"""JS-executing browser test for the folio-insights corpus panel.

Runs ``tests/browser/insights_panel.cjs`` under Node + Playwright against the
real ``frontend/index.html`` (served and API-stubbed via ``page.route``, so no
backend process or port is needed). It covers the banner for every bridge
state, a review save while insights is not configured, and the regression
where a status response landing on a dirty card re-rendered the tab.

Part of the default suite; it skips cleanly when Node, the Playwright package
or its Chromium build is unavailable. Point ``FOLIO_ENRICH_PLAYWRIGHT_MODULE``
at a Playwright package directory to choose one explicitly, e.g.::

    FOLIO_ENRICH_PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \\
        .venv/bin/python -m pytest tests/test_insights_browser.py -q
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from folio_propositions import ActorRef, Disposition, Proposition, content_iri

from tests.browser_support import playwright_module
from tests.helpers import make_job

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
SCRIPT = Path(__file__).parent / "browser" / "insights_panel.cjs"
TEXT = "We hold that the rule applies. The court finds that the fence stood for twenty years."
SOURCE = "urn:example:browser-test"


def _playwright_module(node: str) -> str | None:
    return playwright_module(node)


def _fixture() -> dict:
    job = make_job(text=TEXT)
    spans = [
        ("the rule applies", "Judicial Legal Conclusion"),
        ("the rule applies", "Legal Proposition"),  # same span → same content IRI
        ("the fence stood for twenty years", "Judicial Finding of Fact"),
    ]
    propositions = []
    for index, (span, kind) in enumerate(spans):
        start = TEXT.index(span)
        propositions.append(Proposition(
            id=f"prop-{index + 1}", start_char=start, end_char=start + len(span), text=span,
            proposition_type=kind, asserter=ActorRef(role="court"), validator=None,
            disposition=Disposition.ACCEPTED, content_iri=content_iri(SOURCE, span),
        ))
    job.result.propositions = propositions
    shared, other = propositions[0].content_iri, propositions[2].content_iri
    by_id = {p.id: p.content_iri for p in propositions}

    def result(iri: str, present: bool) -> dict:
        return {
            "iri": iri, "present": present, "shard_type": "hypothesis" if present else None,
            "epistemic_status": "hypothesis" if present else None, "contested": present,
            "supersedes": None, "superseded_by": None,
            "related": [{"iri": "urn:folio:shard/" + "1" * 32, "relation": "elaborates"}] if present else [],
            "contesting": [], "enrich_sources": [],
        }

    base = {"insights_version": "0.1.0", "propositions": by_id}
    return {
        "job": json.loads(job.model_dump_json()),
        "scenarios": {
            # Two propositions share the present IRI: 2 of 3 propositions, not 1 of 2 IRIs.
            "connected": {**base, "connected": True, "state": "connected", "message": None, "corpus": "default",
                          "results": {shared: result(shared, True), other: result(other, False)}},
            "not_configured": {**base, "connected": False, "state": "not_configured",
                               "message": "folio-insights is not connected.", "corpus": None, "results": {}},
            "unreachable": {**base, "connected": False, "state": "unreachable",
                            "message": "folio-insights could not be reached.", "corpus": None, "results": {}},
            "error": {**base, "connected": False, "state": "error",
                      "message": "folio-insights returned a server error (503).", "corpus": None, "results": {}},
        },
    }


@pytest.mark.timeout(120)
def test_insights_panel_in_browser(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = _playwright_module(node)
    if module is None:
        pytest.skip("Playwright package not found (set FOLIO_ENRICH_PLAYWRIGHT_MODULE)")
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(_fixture()))

    run = subprocess.run(
        [node, str(SCRIPT), module, str(FRONTEND), str(fixture_path)],
        capture_output=True, text=True, timeout=110, check=False,
    )
    if run.returncode == 3:
        pytest.skip(f"Playwright browser unavailable: {run.stderr.strip()[:200]}")
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])

    banners = out["banners"]
    assert banners["connected"] == "folio-insights connected · corpus default · 2 of 3 propositions in corpus"
    assert banners["not_configured"] == "folio-insights not connected — corpus status unavailable"
    assert banners["unreachable"] == "folio-insights unreachable — corpus status unavailable"
    assert banners["error"] == (
        "folio-insights error — corpus status unavailable · folio-insights returned a server error (503)."
    )
    assert out["connectedCorpusRows"] == 1
    assert "contested" in out["connectedBadges"]

    # Not configured: no corpus rows, and an outcome save still goes through.
    assert out["notConfiguredCorpusRows"] == 0
    assert out["notConfiguredPatches"] == [{"id": "prop-1", "outcome": "accepted"}]
    assert out["notConfiguredAfterSaveBanner"] == banners["not_configured"]

    # Regression: the status response (and a Refresh) landing on a dirty card
    # patches the corpus row in place instead of re-rendering the tab.
    assert out["dirtyBefore"] == "true"
    assert out["dirtyAfter"] == "true"
    assert out["dirtyDisposition"] == "rejected"
    assert out["dirtySameNode"] is True
    assert out["dirtyBanner"] == banners["connected"]
    assert out["dirtyCopyEnabled"] is True
    assert out["dirtyAfterRefresh"] == "true"
    assert out["dirtySameNodeAfterRefresh"] is True
    assert out["dirtyStatusCalls"] == 2

    assert out["errors"] == []
