"""Seed pre-baked demo jobs into the job store so demo-mode exports work.

In demo mode the frontend hydrates from static JSON (``frontend/demos/<slug>.json``)
and sets ``currentJobId`` to the demo's job id. Export buttons call
``/enrich/{jobId}/export``, which requires the job to exist server-side. On startup we
load each demo file, reconstruct its ``Job``, stamp ``updated_at=now``, and save it —
and register its id in ``PROTECTED_JOB_IDS`` so periodic cleanup never deletes it.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.models.job import Job
from app.storage.job_store import PROTECTED_JOB_IDS, JobStore

logger = logging.getLogger(__name__)

DEMOS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "demos"


async def seed_demo_jobs(store: JobStore | None = None) -> int:
    """Load every demo JSON's embedded job into the job store. Returns count seeded."""
    if not DEMOS_DIR.is_dir():
        return 0

    store = store or JobStore()
    now = datetime.now(timezone.utc)
    seeded = 0

    for path in sorted(DEMOS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
            job_dict = (payload.get("cache") or {}).get("job")
            if not job_dict:
                continue
            job = Job.model_validate(job_dict)
            job.updated_at = now  # keep fresh so cleanup never targets it
            await store.save(job)
            PROTECTED_JOB_IDS.add(str(job.id))
            seeded += 1
        except Exception:
            logger.warning("Failed to seed demo job from %s", path.name, exc_info=True)

    if seeded:
        logger.info("Seeded %d demo job(s) for export support", seeded)
    return seeded
