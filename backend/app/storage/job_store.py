from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)

# Newest post-job state written in this process, per job id. The pipeline and
# the annotation routes save whole jobs from in-memory copies that may predate a
# user's review/push override; save() substitutes the newest revision so those
# writers never roll it back. (Single-process store, like the asyncio locks.)
_POST_JOB_LATEST: dict[str, object] = {}

# Job IDs that must never be auto-deleted by cleanup_expired (e.g. seeded demo jobs
# that back demo-mode exports). Populated at startup by app.services.demo_seed.
PROTECTED_JOB_IDS: set[str] = set()

# count_active() needs only each job's status and timestamps, which Job's
# serialization writes first (id, status, created_at, updated_at). Read a small
# file head instead of parsing whole multi-MB jobs, and cache the result per path
# keyed by (inode, mtime_ns, size) so unchanged files cost a stat only. Any writer
# (save's atomic rename, stale/orphan reconciliation, external tools) changes
# that stamp, so the cache cannot go stale.
_HEADER_BYTES = 1024
_HEADER_CACHE: dict[str, tuple[tuple[int, int, int], str, str | None]] = {}
_STATUS_RE = re.compile(r'"status"\s*:\s*"([^"]*)"')
_CREATED_RE = re.compile(r'"created_at"\s*:\s*"([^"]*)"')
_UPDATED_RE = re.compile(r'"updated_at"\s*:\s*"([^"]*)"')
_INPUT_RE = re.compile(r'"(input|result)"\s*:')


def _job_header(path: Path) -> tuple[str, str | None]:
    """Return (status, updated_at or created_at) for a job file, cheaply."""
    st = path.stat()
    key = str(path)
    stamp = (st.st_ino, st.st_mtime_ns, st.st_size)
    cached = _HEADER_CACHE.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1], cached[2]
    with open(path, "rb") as f:
        head = f.read(_HEADER_BYTES).decode("utf-8", errors="ignore")
    # Only trust the head when the top-level fields precede the nested payload
    # (whose own "status"-like keys could otherwise be mistaken for the job's).
    nested = _INPUT_RE.search(head)
    scope = head[: nested.start()] if nested else head
    status_m = _STATUS_RE.search(scope)
    if status_m is not None and (nested is not None or st.st_size <= _HEADER_BYTES):
        updated_m = _UPDATED_RE.search(scope) or _CREATED_RE.search(scope)
        status, updated = status_m.group(1), (updated_m.group(1) if updated_m else None)
    else:  # Unexpected layout: fall back to a full parse.
        data = json.loads(path.read_text())
        status = data.get("status", "")
        updated = data.get("updated_at") or data.get("created_at")
    _HEADER_CACHE[key] = (stamp, status, updated)
    return status, updated


class JobStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.jobs_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _job_path(self, job_id: UUID) -> Path:
        return self.base_dir / f"{job_id}.json"

    async def save(self, job: Job) -> None:
        self._merge_post_job(job)
        path = self._job_path(job.id)
        data = job.model_dump_json(indent=2)
        # Atomic write: write to temp file then rename
        fd, tmp_path = tempfile.mkstemp(dir=self.base_dir, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                f.write(data)
            Path(tmp_path).rename(path)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    @staticmethod
    def _merge_post_job(job: Job) -> None:
        key = str(job.id)
        latest = _POST_JOB_LATEST.get(key)
        current = job.post_job
        if latest is not None and (current is None or current.revision < latest.revision):
            job.post_job = latest.model_copy(deep=True)
        elif current is not None:
            _POST_JOB_LATEST[key] = current.model_copy(deep=True)

    async def load(self, job_id: UUID) -> Job | None:
        path = self._job_path(job_id)
        if not path.exists():
            return None
        data = path.read_text()
        return Job.model_validate_json(data)

    async def list_jobs(self) -> list[Job]:
        jobs = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                jobs.append(Job.model_validate_json(path.read_text()))
            except Exception:
                continue
        return jobs

    async def delete(self, job_id: UUID) -> bool:
        _POST_JOB_LATEST.pop(str(job_id), None)
        path = self._job_path(job_id)
        if path.exists():
            path.unlink()
            return True
        return False

    async def count_active(self) -> int:
        """Count jobs currently in progress, auto-failing stale ones.

        Runs on a worker thread and reads only each job file's header (cached
        by mtime/size), so a POST /enrich no longer parses every retained job.
        """
        return await asyncio.to_thread(self._count_active_sync)

    def _count_active_sync(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.stale_job_timeout_minutes
        )
        count = 0
        seen: set[str] = set()
        for path in self.base_dir.glob("*.json"):
            key = str(path)
            seen.add(key)
            try:
                status, updated = _job_header(path)
                if status in ("completed", "failed", "pending"):
                    continue
                # Check if this in-progress job is stale
                if updated:
                    ts = datetime.fromisoformat(updated)
                    if ts < cutoff:
                        data = json.loads(path.read_text())
                        if data.get("status", "") in ("completed", "failed", "pending"):
                            continue  # finished since the header read
                        data["status"] = "failed"
                        data["error"] = "Job timed out (stale)"
                        data["updated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        path.write_text(json.dumps(data, indent=2))
                        logger.info("Marked stale job %s as failed", path.stem)
                        continue
                count += 1
            except Exception:
                continue
        # Forget headers of deleted job files in this directory.
        base = str(self.base_dir)
        for key in [k for k in _HEADER_CACHE if k not in seen and str(Path(k).parent) == base]:
            _HEADER_CACHE.pop(key, None)
        return count

    async def fail_orphaned_jobs(self) -> int:
        """Mark every non-terminal job as failed. Called once at startup.

        A job's pipeline runs in an in-process asyncio task that does not
        survive a restart/redeploy. Any job still in a non-terminal state when
        the process boots is therefore orphaned — it will never progress, yet
        it keeps counting toward ``max_concurrent_jobs``. On platforms that
        redeploy often (Railway), these pile up until new jobs are blocked with
        "Too many concurrent jobs". Reconcile them to ``failed`` so the active
        count reflects reality. Returns the number reconciled.
        """
        terminal = ("completed", "failed")
        reconciled = 0
        for path in self.base_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("status", "") in terminal:
                    continue
                data["status"] = "failed"
                data["error"] = "Job interrupted by server restart"
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                path.write_text(json.dumps(data, indent=2))
                reconciled += 1
            except Exception:
                continue
        if reconciled:
            logger.info("Reconciled %d orphaned job(s) to failed at startup", reconciled)
        return reconciled

    async def cleanup_expired(self, retention_days: int | None = None) -> int:
        """Delete jobs older than retention period. Returns count of deleted jobs."""
        if retention_days is None:
            retention_days = settings.job_retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = 0
        unexported_job_ids: set[str] = set()

        for session_path in (self.base_dir / "gold_sessions").glob("*.json"):
            try:
                data = json.loads(session_path.read_text())
                job_id = data.get("job_id")
                if isinstance(job_id, str) and not data.get("exported_at"):
                    unexported_job_ids.add(job_id)
            except Exception:
                continue

        for path in list(self.base_dir.glob("*.json")):
            if path.stem in PROTECTED_JOB_IDS or path.stem in unexported_job_ids:
                continue
            try:
                data = json.loads(path.read_text())
                updated = data.get("updated_at") or data.get("created_at")
                if updated:
                    ts = datetime.fromisoformat(updated)
                    if ts < cutoff:
                        path.unlink()
                        _POST_JOB_LATEST.pop(path.stem, None)
                        deleted += 1
            except Exception:
                continue

        return deleted
