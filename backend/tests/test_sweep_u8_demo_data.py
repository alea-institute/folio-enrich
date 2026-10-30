"""U8 sweep: demo jobs must stay completed across startup, and demo data must be
internally consistent (no dangling individual class_link annotation ids)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.document import DocumentFormat, DocumentInput
from app.models.job import Job, JobStatus
from app.services import demo_seed
from app.storage.job_store import PROTECTED_JOB_IDS, JobStore


def _demo_files() -> list[Path]:
    if not demo_seed.DEMOS_DIR.is_dir():
        return []
    return sorted(demo_seed.DEMOS_DIR.rglob("*.json"))


async def test_seed_forces_completed_then_survives_orphan_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A demo baked mid-pipeline must still seed as completed, so the startup
    orphan reconciliation (run right after seeding) leaves it alone."""
    demos = tmp_path / "demos"
    demos.mkdir()
    job = Job(input=DocumentInput(content="hello", format=DocumentFormat.PLAIN_TEXT))
    job.status = JobStatus.MATCHING  # what 20 FOLIO demos were baked with
    (demos / "baked.json").write_text(
        json.dumps({"cache": {"job": json.loads(job.model_dump_json())}})
    )
    monkeypatch.setattr(demo_seed, "DEMOS_DIR", demos)

    store = JobStore(base_dir=tmp_path / "jobs")
    try:
        assert await demo_seed.seed_demo_jobs(store) == 1
        # Same order as app startup (main.py lifespan): seed, then reconcile.
        assert await store.fail_orphaned_jobs() == 0
        loaded = await store.load(job.id)
        assert loaded is not None
        assert loaded.status == JobStatus.COMPLETED
    finally:
        PROTECTED_JOB_IDS.discard(str(job.id))


async def test_real_demos_stay_completed_after_startup_sequence(tmp_path: Path) -> None:
    if not _demo_files():
        pytest.skip("no demo files")
    store = JobStore(base_dir=tmp_path)
    protected_before = set(PROTECTED_JOB_IDS)
    try:
        seeded = await demo_seed.seed_demo_jobs(store)
    finally:
        # Seeding registers ids in a process-global set; don't leak them into
        # other tests that count it.
        PROTECTED_JOB_IDS.intersection_update(protected_before)
    assert seeded > 0
    assert await store.fail_orphaned_jobs() == 0
    for p in tmp_path.glob("*.json"):
        assert json.loads(p.read_text())["status"] == "completed", p.name


@pytest.mark.parametrize("path", _demo_files(), ids=lambda p: p.relative_to(p.parents[1]).as_posix())
def test_demo_json_is_completed_and_class_links_resolve(path: Path) -> None:
    job = json.loads(path.read_text())["cache"]["job"]
    assert job["status"] == "completed"
    result = job["result"]
    ann_ids = {a["id"] for a in result.get("annotations", [])}
    dangling = [
        cl["annotation_id"]
        for ind in result.get("individuals", [])
        for cl in ind.get("class_links", [])
        if cl.get("annotation_id") is not None and cl["annotation_id"] not in ann_ids
    ]
    assert not dangling, f"{len(dangling)} class_link annotation_id(s) point at missing annotations"
