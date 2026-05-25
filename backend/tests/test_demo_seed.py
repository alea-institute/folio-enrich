"""Demo job seeding + cleanup-protection tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.document import DocumentFormat, DocumentInput
from app.models.job import Job, JobStatus
from app.storage.job_store import PROTECTED_JOB_IDS, JobStore


def _old_job() -> Job:
    job = Job(input=DocumentInput(content="hello", format=DocumentFormat.PLAIN_TEXT))
    job.status = JobStatus.COMPLETED
    job.updated_at = datetime.now(timezone.utc) - timedelta(days=999)
    return job


async def test_cleanup_skips_protected_jobs(tmp_path: Path) -> None:
    store = JobStore(base_dir=tmp_path)
    protected, normal = _old_job(), _old_job()
    await store.save(protected)
    await store.save(normal)

    PROTECTED_JOB_IDS.add(str(protected.id))
    try:
        deleted = await store.cleanup_expired(retention_days=0)
    finally:
        PROTECTED_JOB_IDS.discard(str(protected.id))

    assert await store.load(protected.id) is not None, "protected demo job was deleted"
    assert await store.load(normal.id) is None, "stale non-protected job should be deleted"
    assert deleted == 1


async def test_seed_demo_jobs_registers_and_loads(tmp_path: Path) -> None:
    """If demo files exist, seeding loads them and protects their ids."""
    from app.services.demo_seed import DEMOS_DIR, seed_demo_jobs

    if not DEMOS_DIR.is_dir() or not list(DEMOS_DIR.glob("*.json")):
        pytest.skip("no demo files generated yet")

    store = JobStore(base_dir=tmp_path)
    before = len(PROTECTED_JOB_IDS)
    seeded = await seed_demo_jobs(store)
    assert seeded > 0
    assert len(PROTECTED_JOB_IDS) >= before + seeded
    # every seeded file is a loadable completed job
    for p in tmp_path.glob("*.json"):
        job = await store.load(__import__("uuid").UUID(p.stem))
        assert job is not None and job.result is not None
