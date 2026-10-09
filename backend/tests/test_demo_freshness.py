"""Tests for demo file freshness and auto-regeneration.

Run explicitly:  pytest -m demo_regen -v
"""

from __future__ import annotations

import json

import pytest
from scripts.demo_documents import DEMO_DOCUMENTS
from scripts.generate_demos import DEMOS_DIR, get_staleness_info

EXPECTED_SLUGS = list(DEMO_DOCUMENTS.keys())


@pytest.mark.demo_regen
class TestDemoFreshness:
    """Verify demo JSON files are present, well-formed, and up-to-date."""

    def test_all_demo_files_exist(self) -> None:
        missing = [s for s in EXPECTED_SLUGS if not (DEMOS_DIR / f"{s}.json").exists()]
        assert not missing, f"Missing demo files: {missing}"

    def test_demo_json_structure(self) -> None:
        for slug in EXPECTED_SLUGS:
            path = DEMOS_DIR / f"{slug}.json"
            if not path.exists():
                pytest.skip(f"{slug}.json missing — run generate_demos.py first")

            data = json.loads(path.read_text())
            assert "demo" in data, f"{slug}.json missing 'demo' key"
            assert "cache" in data, f"{slug}.json missing 'cache' key"
            demo = data["demo"]
            assert "generated_at" in demo, f"{slug}.json missing 'generated_at'"
            assert "name" in demo, f"{slug}.json missing 'name'"
            assert demo["name"] == slug, f"{slug}.json name mismatch: {demo['name']}"

    @pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=(
            "Known main failure (2026-10-09): baked demos target FOLIO OWL "
            "9a9d3cb5d2823f2a and older pipeline sources; rebake demos and "
            "their version sidecars before removing this marker. See "
            "docs/plans/2026-10-09-backend-ci-lane-plan.md."
        ),
    )
    def test_demos_are_fresh(self) -> None:
        stale, reason = get_staleness_info()
        assert not stale, (
            f"Demos are stale: {reason}\n"
            "Regenerate with: cd backend && .venv/bin/python scripts/generate_demos.py"
        )

    @pytest.mark.skip(
        reason=(
            "Known main failure (2026-10-09): stale baked demo regeneration "
            "requires live ontology/models and may use a paid LLM provider; "
            "run scripts/generate_demos.py in an authorized regeneration run, "
            "refresh version sidecars, then restore this test. See "
            "docs/plans/2026-10-09-backend-ci-lane-plan.md."
        ),
    )
    @pytest.mark.timeout(600)
    async def test_regenerate_if_stale(self) -> None:
        stale, reason = get_staleness_info()
        if not stale:
            pytest.skip(f"Demos are fresh — {reason}")

        from scripts.generate_demos import main

        await main()

        stale_after, reason_after = get_staleness_info()
        assert not stale_after, f"Demos still stale after regeneration: {reason_after}"
