"""Acceptance checks for baked breadth and overlap demos; no generation here."""

import json

import pytest

from scripts.generate_demos import DEMOS_DIR

BREADTH_SLUGS = [
    "canon_liturgical_year", "canon_diocesan_governance",
    "canon_saints_and_orders", "canon_ce_abbot_1907",
]
OVERLAP_SLUGS = [
    "lm_encyclopedia_theft", "lm_aquinas_robbery", "lm_aquinas_just_price",
    "lm_exodus_restitution", "lm_catechism_seventh_eighth",
]
pytestmark = pytest.mark.demo_regen


def _read_demo(ontology, slug):
    path = DEMOS_DIR / ontology / f"{slug}.json"
    if not path.exists():
        pytest.skip(f"{ontology}/{slug}.json absent; full LLM bake pending")
    return json.loads(path.read_text())["cache"]


@pytest.mark.parametrize("slug", BREADTH_SLUGS)
def test_canon_breadth_density(slug):
    cache = _read_demo("canon", slug)
    words = len(cache["normalizedText"].split())
    assert words > 0
    density = len(cache["job"]["result"]["annotations"]) / words * 100
    assert density >= 35, f"{slug}: {density:.2f} concept tags per 100 words"


@pytest.mark.parametrize("slug", OVERLAP_SLUGS)
def test_overlap_shared_share_and_bridges(slug):
    result = _read_demo("both", slug)["job"]["result"]
    concepts = [
        c for a in result["annotations"] for c in a["concepts"]
        if c.get("state") not in {"backup", "rejected"}
    ]
    assert concepts, f"{slug}: no active concepts"
    shared_share = sum(c.get("region") == "shared" for c in concepts) / len(concepts)
    assert shared_share > 0, f"{slug}: no shared concepts"
    assert result["bridges"], f"{slug}: no bridges"
