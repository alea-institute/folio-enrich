"""JS-executing browser test for the settings modal's public vs local posture.

Runs ``tests/browser/settings_posture.cjs`` under Node + Playwright against the
real ``frontend/index.html`` (API stubbed via ``page.route``). Public posture
(``require_user_api_key``): the provider/model/key choice stays in this
browser, no ``PUT /settings`` is sent, server-wide controls are disabled, and
the choice travels with ``/enrich``. Local posture: Save still writes server
defaults, and a 403 surfaces "Admin only on this server".

Skips cleanly when Node, Playwright or a launchable Chromium is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.browser_support import playwright_module

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
SCRIPT = Path(__file__).parent / "browser" / "settings_posture.cjs"


@pytest.mark.timeout(150)
def test_settings_modal_posture_in_browser():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = playwright_module(node)
    if module is None:
        pytest.skip("No Playwright package with a launchable Chromium (set FOLIO_ENRICH_PLAYWRIGHT_MODULE)")
    run = subprocess.run(
        [node, str(SCRIPT), module, str(FRONTEND)],
        capture_output=True, text=True, timeout=140, check=False,
    )
    if run.returncode == 3:
        pytest.skip(f"Playwright browser unavailable: {run.stderr.strip()[:200]}")
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])

    public = out["public"]
    assert public["translationDisabled"] is True
    assert public["putsAfterSave"] == 0
    assert json.loads(public["localChoice"]) == {"provider": "openai", "model": "gpt-b"}
    assert "Admin only" not in public["toast"]
    assert public["afterReload"] == {"provider": "openai", "model": "gpt-b", "key": "sk-user-key"}
    assert public["putsAfterSubmit"] == 0
    assert public["submitted"] == {"provider": "openai", "model": "gpt-b", "key": "sk-user-key"}

    local403 = out["local403"]
    assert local403["translationDisabled"] is False
    assert local403["puts"] == 1
    assert "Admin only on this server" in local403["toast"]

    local = out["local"]
    assert local["puts"] == 1
    assert local["body"]["llm_provider"] == "openai"
    assert local["body"]["llm_model"] == "gpt-b"
    assert local["body"]["openai_api_key"] == "sk-user-key"
    assert "Admin only" not in local["toast"]

    assert out["errors"] == []
