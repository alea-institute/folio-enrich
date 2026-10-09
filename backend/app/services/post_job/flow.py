"""Post-job flow: optional review step, then optional push to folio-insights.

Two independent per-job choices, recorded on ``Job.post_job``:

* ``review``: ``required`` (the job waits in ``awaiting_review`` after the
  pipeline finishes until someone completes or skips review) or ``skipped``.
* ``push``: ``requested`` (send the job's shared-schema ``propositions`` record
  to the insights ingest route) or ``not_requested``.

When both are on, the push waits for the review. The choices come from the
/enrich request; a field the caller omits falls back to the server defaults
``settings.post_job_review_default`` / ``settings.post_job_push_default``.
Either can be changed later with :func:`apply_override`.

Every state change reloads the job from the store under a per-job lock and
saves it back, so it never overwrites concurrent edits with a stale copy. A
per-process in-flight set keeps two triggers from pushing the same job at
once. Re-pushing is safe anyway: insights ingest is idempotent per shard IRI
(content-addressed), so a second push reports the shards as ``existing``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.config import settings
from app.models.job import Job, JobStatus, PostJobState
from app.services import insights_client

logger = logging.getLogger(__name__)

# Tests inject an httpx.MockTransport here; production uses the real network.
push_transport: httpx.AsyncBaseTransport | None = None

_locks: dict[str, asyncio.Lock] = {}
_in_flight: set[str] = set()
_background: set[asyncio.Task] = set()


class PostJobError(Exception):
    """A requested post-job action does not fit the job's current state."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _lock(job_id: UUID | str) -> asyncio.Lock:
    key = str(job_id)
    lock = _locks.get(key)
    if lock is None:
        lock = _locks[key] = asyncio.Lock()
    return lock


def _now() -> datetime:
    return datetime.now(timezone.utc)


def initial_state(review_before_continuing: bool | None, push_to_insights: bool | None) -> PostJobState:
    """State for a newly submitted job; ``None`` means "use the server default"."""
    review = settings.post_job_review_default if review_before_continuing is None else review_before_continuing
    push = settings.post_job_push_default if push_to_insights is None else push_to_insights
    return PostJobState(
        review="required" if review else "skipped",
        push="requested" if push else "not_requested",
        review_status="pending_job",
        push_status="waiting_for_job" if push else "not_requested",
    )


def effective_state(job: Job) -> PostJobState:
    """The job's state, or the legacy default (no review, no push)."""
    return job.post_job if job.post_job is not None else PostJobState()


def is_push_in_flight(job_id: UUID | str) -> bool:
    return str(job_id) in _in_flight


def _reconcile(state: PostJobState, job_done: bool) -> bool:
    """Bring statuses in line with the choices; return True if a push is due."""
    if not job_done:
        state.review_status = "pending_job"
        if state.push == "requested":
            if state.push_status in ("not_requested", "waiting_for_review"):
                state.push_status = "waiting_for_job"
        elif state.push_status in ("waiting_for_job", "waiting_for_review"):
            state.push_status = "not_requested"
        return False

    if state.review_status == "pending_job":
        state.review_status = "awaiting_review" if state.review == "required" else "not_required"
    elif state.review == "required" and state.review_status == "not_required":
        state.review_status = "awaiting_review"
    elif state.review == "skipped" and state.review_status == "awaiting_review":
        state.review_status = "not_required"

    if state.push != "requested":
        if state.push_status in ("waiting_for_job", "waiting_for_review"):
            state.push_status = "not_requested"
        return False
    if state.review_status == "awaiting_review":
        if state.push_status in ("not_requested", "waiting_for_job", "waiting_for_review"):
            state.push_status = "waiting_for_review"
        return False
    # pushed / pending / failed / not_configured do not re-push automatically;
    # POST /enrich/{id}/insights-push retries.
    return state.push_status in ("not_requested", "waiting_for_job", "waiting_for_review")


async def _load(store, job_id: UUID) -> Job:
    job = await store.load(job_id)
    if job is None:
        raise PostJobError("Job not found", 404)
    return job


def schedule_push(store, job_id: UUID) -> None:
    """Run :func:`run_push` in the background (does not block the caller)."""
    task = asyncio.create_task(_run_push_logged(store, job_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _run_push_logged(store, job_id: UUID) -> None:
    try:
        await run_push(store, job_id)
    except PostJobError as exc:
        logger.info("Automatic insights push for job %s skipped: %s", job_id, exc.message)
    except Exception:  # noqa: BLE001 — a background push must never crash the loop
        logger.exception("Automatic insights push for job %s failed unexpectedly", job_id)


async def drain() -> None:
    """Wait for every scheduled background push (used by tests and shutdown)."""
    while _background:
        await asyncio.gather(*list(_background), return_exceptions=True)


async def on_job_completed(store, job: Job) -> None:
    """Pipeline hook: the job just finished successfully."""
    if job.post_job is None:
        return  # caller chose no post-job flow (legacy/internal job)
    async with _lock(job.id):
        stored = await store.load(job.id) or job
        if stored.post_job is None:
            return
        state = stored.post_job
        push_due = _reconcile(state, job_done=True)
        await store.save(stored)
        job.post_job = state
    if push_due:
        schedule_push(store, job.id)


async def apply_override(store, job_id: UUID, review: bool | None, push: bool | None) -> Job:
    """Change this job's review and/or push choice."""
    async with _lock(job_id):
        job = await _load(store, job_id)
        if job.status == JobStatus.FAILED:
            raise PostJobError("The job failed; there is nothing to review or push.")
        state = effective_state(job).model_copy(deep=True)
        if review is not None:
            state.review = "required" if review else "skipped"
        if push is not None:
            turned_on = push and state.push != "requested"
            state.push = "requested" if push else "not_requested"
            if turned_on and state.push_status in ("failed", "not_configured"):
                state.push_status = "not_requested"  # a fresh opt-in tries again
        push_due = _reconcile(state, job_done=job.status == JobStatus.COMPLETED)
        job.post_job = state
        await store.save(job)
    if push_due:
        schedule_push(store, job_id)
    return job


async def complete_review(store, job_id: UUID) -> Job:
    """Mark the review done; a push that was waiting for it starts."""
    async with _lock(job_id):
        job = await _load(store, job_id)
        state = effective_state(job).model_copy(deep=True)
        if job.status != JobStatus.COMPLETED or state.review_status == "pending_job":
            raise PostJobError("The job has not finished yet.")
        if state.review_status != "awaiting_review":
            return job  # already completed or review not required: idempotent
        state.review_status = "completed"
        state.review_completed_at = _now()
        push_due = _reconcile(state, job_done=True)
        job.post_job = state
        await store.save(job)
    if push_due:
        schedule_push(store, job_id)
    return job


async def manual_push(store, job_id: UUID) -> Job:
    """Push now (first push, retry after a failure, or a deliberate re-push)."""
    async with _lock(job_id):
        job = await _load(store, job_id)
        state = effective_state(job).model_copy(deep=True)
        if job.status != JobStatus.COMPLETED or state.review_status == "pending_job":
            raise PostJobError("The job has not finished yet.")
        if state.review_status == "awaiting_review":
            raise PostJobError("Complete or skip the review before pushing.")
        if state.push != "requested":
            state.push = "requested"
            job.post_job = state
            await store.save(job)
    return await run_push(store, job_id)


async def run_push(store, job_id: UUID) -> Job:
    """Build the job's propositions record and send it to insights once."""
    key = str(job_id)
    async with _lock(job_id):
        if key in _in_flight:
            raise PostJobError("A push for this job is already in progress.")
        job = await _load(store, job_id)
        state = effective_state(job).model_copy(deep=True)
        if state.review_status == "awaiting_review":
            raise PostJobError("Complete or skip the review before pushing.")
        _in_flight.add(key)
        state.push_status = "pending"
        state.push_attempts += 1
        state.last_push_at = _now()
        job.post_job = state
        await store.save(job)

    try:
        from app.services.export.propositions_exporter import build_proposition_record

        try:
            record = build_proposition_record(job).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 — an invalid record is a push failure, not a crash
            logger.warning("Could not build the propositions record for job %s: %s", job_id, type(exc).__name__)
            result = insights_client.PushResult(state="failed", message="The job's proposition record could not be built.")
        else:
            result = await insights_client.push_record(record, transport=push_transport)

        async with _lock(job_id):
            job = await _load(store, job_id)
            state = effective_state(job).model_copy(deep=True)
            state.push_status = result.state
            state.last_push_at = _now()
            if result.state == "pushed":
                state.last_push_error = None
                state.last_push_report = result.report
            else:
                state.last_push_error = result.message
            job.post_job = state
            await store.save(job)
            return job
    finally:
        _in_flight.discard(key)
