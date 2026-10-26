"""Fast gold acceptance through the real frontend and an isolated, synthetic API."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from folio_propositions import ActorRef, Disposition, Proposition

from tests.browser_support import playwright_module
from tests.helpers import make_job

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).parent / "browser" / "fast_gold_annotation.cjs"
SCENARIOS = ["queue", "failed-edit", "held-key", "same-type", "discarded", "multitouch", "mid-swipe", "hand-added"]


def _fixture() -> dict:
    sentences = [f"The court applies rule {i} to this claim." for i in range(8)]
    text = " ".join(sentences)
    job = make_job(text=text)
    job.result.propositions = [
        Proposition(id=f"prop-{i}", start_char=text.index(span), end_char=text.index(span) + len(span),
                    text=span, proposition_type="Legal Proposition", disposition=Disposition.ACCEPTED,
                    asserter=ActorRef(role="court") if i == 0 else None, validator=None)
        for i, span in enumerate(sentences)
    ]
    return {"job": json.loads(job.model_dump_json())}


@pytest.mark.timeout(120)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fast_gold_in_browser(tmp_path, scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = playwright_module(node)
    if module is None:
        pytest.skip("Playwright package not found (set FOLIO_ENRICH_PLAYWRIGHT_MODULE)")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(_fixture()))
    run = subprocess.run(
        [node, str(SCRIPT), module, "http://localhost", str(BACKEND.parent / "frontend"), str(fixture), scenario],
        capture_output=True, text=True, timeout=110, check=False,
    )
    if run.returncode == 3:
        pytest.skip(f"Playwright browser unavailable: {run.stderr.strip()[:200]}")
    assert run.returncode == 0, run.stderr[-4000:]
    assert json.loads(run.stdout.strip().splitlines()[-1]) == {"scenario": scenario, "widths": [1280, 390]}
