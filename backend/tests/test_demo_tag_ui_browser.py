"""Exercise opinion demo tag controls in the real frontend with stubbed APIs."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests.browser_support import playwright_module


@pytest.fixture(scope="module")
def demo_ui():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = playwright_module(node)
    if module is None:
        pytest.skip("No Playwright package with a launchable Chromium")
    backend = Path(__file__).resolve().parents[1]
    run = subprocess.run(
        [node, str(backend / "tests/browser/demo_tag_ui.cjs"), module,
         str(backend.parent / "frontend")],
        capture_output=True, text=True, timeout=140, check=False,
    )
    if run.returncode == 3:
        pytest.skip(f"Playwright unavailable: {run.stderr[:200]}")
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


@pytest.mark.timeout(150)
@pytest.mark.parametrize("scenario", ["uncertain", "confidence", "counts", "escape", "close", "remove", "bulk", "detail"])
def test_demo_tag_ui(demo_ui, scenario):
    assert demo_ui["results"][scenario] is None, demo_ui["results"][scenario]


def test_demo_tag_ui_no_page_errors(demo_ui):
    assert demo_ui["errors"] == []
