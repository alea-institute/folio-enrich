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

    def test_demos_are_fresh(self) -> None:
        stale, reason = get_staleness_info()
        assert not stale, (
            f"Demos are stale: {reason}\n"
            "Regenerate with: cd backend && .venv/bin/python scripts/generate_demos.py"
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


OVERLAP_SLUGS = [
    "lm_encyclopedia_theft", "lm_aquinas_robbery", "lm_aquinas_just_price",
    "lm_exodus_restitution", "lm_catechism_seventh_eighth",
]
BREADTH_SLUGS = [
    "canon_liturgical_year", "canon_diocesan_governance",
    "canon_saints_and_orders", "canon_ce_abbot_1907",
]


def test_load_both_documents():
    from scripts.demo_documents import load_demo_documents

    docs = load_demo_documents("both")
    assert list(docs) == OVERLAP_SLUGS
    assert docs["lm_aquinas_robbery"]["text"].startswith("WHETHER")
    for doc in docs.values():
        assert doc["title"] and doc["description"] and doc["group"]


def test_load_canon_breadth_documents():
    from scripts.demo_documents import load_demo_documents

    docs = load_demo_documents("canon")
    assert list(docs) == ["nativity", "sacraments", "trent_eucharist", "rerum_novarum", *BREADTH_SLUGS]
    for slug in BREADTH_SLUGS[:3]:
        assert docs[slug]["description"].startswith("Synthetic —")


def test_both_sidecars(tmp_path, monkeypatch):
    import hashlib
    from scripts import generate_demos
    from app.services.folio import owl_cache
    from app.services.ontology.spec import CANON_SPEC

    monkeypatch.setattr(generate_demos, "DEMOS_DIR", tmp_path)
    monkeypatch.setattr(owl_cache, "get_owl_content_hash", lambda: "folio-content-hash")
    generate_demos._write_sidecars("both")
    assert json.loads((tmp_path / "both/.owl-version").read_text()) == {
        "folio": "folio-content-hash", "canon": CANON_SPEC.coords.owl_sha256,
    }
    from scripts.overlap_exemplars import OVERLAP_SAMPLES_JS
    assert (tmp_path / "both/.samples-version").read_text() == hashlib.sha256(
        OVERLAP_SAMPLES_JS.read_bytes()
    ).hexdigest()[:16]


async def test_seed_both_namespace(tmp_path, monkeypatch):
    from app.services import demo_seed
    from app.models.document import DocumentInput
    from app.models.job import Job, JobStatus
    from app.storage.job_store import JobStore, PROTECTED_JOB_IDS

    demos = tmp_path / "demos"
    (demos / "both").mkdir(parents=True)
    job = Job(input=DocumentInput(content="Theft and restitution", ontology="both"), status=JobStatus.COMPLETED)
    (demos / "both/example.json").write_text(json.dumps({"cache": {"job": job.model_dump(mode="json")}}))
    monkeypatch.setattr(demo_seed, "DEMOS_DIR", demos)
    store = JobStore(base_dir=tmp_path / "jobs")
    try:
        assert await demo_seed.seed_demo_jobs(store) == 1
        loaded = await store.load(job.id)
        assert loaded is not None and loaded.input.ontology == "both"
        assert loaded.status == JobStatus.COMPLETED
    finally:
        PROTECTED_JOB_IDS.discard(str(job.id))


def test_slim_nested_demo(tmp_path, monkeypatch):
    from scripts import slim_demos

    (tmp_path / "both").mkdir()
    path = tmp_path / "both/example.json"
    path.write_text(json.dumps({"cache": {"job": {"result": {"metadata": {"reconciled_concepts": [1]}}}}}))
    monkeypatch.setattr(slim_demos, "DEMOS_DIR", tmp_path)
    assert slim_demos.main([]) == 0
    assert "reconciled_concepts" not in json.loads(path.read_text())["cache"]["job"]["result"]["metadata"]
