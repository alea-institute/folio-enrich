"""Post-job flow: optional review step, then optional push to folio-insights.

Two independent per-job choices, recorded on ``Job.post_job``:

* ``review``: ``required`` (the job waits in ``awaiting_review`` after the
  pipeline finishes until someone completes or skips review) or ``skipped``.
* ``push``: ``requested`` (send the job's shared-schema ``propositions`` record
  to the insights ingest route) or ``not_requested``.

When both are on, the push waits for the review. The choices come from the
/enrich request; a field the caller omits falls back to the server defaults
``settings.post_job_review_default`` / ``settings.post_job_push_default``
(the push default only for callers allowed to push). Either can be changed
later with :func:`apply_override`. A failed pipeline job gets neither.

Consistency:

* Every flow change bumps ``PostJobState.revision`` and saves under a per-job
  lock. ``JobStore.save`` keeps the highest revision it has seen, so another
  writer holding a stale in-memory job (the orchestrator's post-completion
  saves, annotation edits) can never roll the post-job state back.
* A per-process in-flight set keeps two triggers from pushing the same job at
  once. A stored ``pending`` with nothing in flight (a restart, a lost final
  save) is reported as an interrupted, retryable failure.

Re-pushing is safe anyway: insights ingest is idempotent per shard IRI
(content-addressed), so already-ingested propositions come back ``existing``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.config import settings
from app.models.job import Job, JobStatus, PostJobState
from app.services import insights_client

logger = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "Push was interrupted; retry."
RETRYABLE_PUSH_STATUSES = ("failed", "not_configured")
PUSH_ACCESS_MESSAGE = (
    "Pushing to folio-insights requires annotation access "
    "(Cloudflare Access login, X-Annotation-Token or X-Admin-Token)."
)

# Tests inject an httpx.MockTransport here; production uses the real network.
push_transport: httpx.AsyncBaseTransport | None = None

_locks: dict[str, asyncio.Lock] = {}
_in_flight: set[str] = set()
# Scheduled but not yet started: the push is already recorded as "pending" in
# the same save that decided it, so no later trigger schedules a second one.
_queued: set[str] = set()
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


def initial_state(
    review_before_continuing: bool | None,
    push_to_insights: bool | None,
    *,
    push_allowed: bool = True,
) -> PostJobState:
    """State for a newly submitted job; ``None`` means "use the server default".

    The server push default never applies to a caller who may not push.
    """
    review = settings.post_job_review_default if review_before_continuing is None else review_before_continuing
    if push_to_insights is None:
        push = settings.post_job_push_default and push_allowed
    else:
        push = push_to_insights
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
    key = str(job_id)
    return key in _in_flight or key in _queued


def _queue(state: PostJobState, job_id: UUID | str) -> None:
    """Record a decided push as pending in the save that decides it.

    :func:`schedule_push` (called right after the lock is released, with no
    await in between) marks it queued, so it never reads as interrupted.
    """
    state.push_status = "pending"


def _heal_interrupted(state: PostJobState, job_id: UUID | str) -> bool:
    """A stored ``pending`` with nothing in flight becomes a retryable failure."""
    if state.push_status == "pending" and not is_push_in_flight(job_id):
        state.push_status = "failed"
        state.last_push_error = INTERRUPTED_MESSAGE
        return True
    return False


def _settle_failed_job(state: PostJobState) -> bool:
    """Failed pipeline jobs get no review and no push."""
    changed = False
    if state.review_status in ("pending_job", "awaiting_review"):
        state.review_status = "not_required"
        changed = True
    if state.push_status in ("waiting_for_job", "waiting_for_review"):
        state.push_status = "not_requested"
        changed = True
    return changed


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
    # pushed / pending / failed / not_configured never re-push automatically;
    # POST /enrich/{id}/insights-push retries a failure.
    return state.push_status in ("not_requested", "waiting_for_job", "waiting_for_review")


async def _load(store, job_id: UUID) -> Job:
    job = await store.load(job_id)
    if job is None:
        raise PostJobError("Job not found", 404)
    return job


async def _commit(store, job: Job, state: PostJobState) -> None:
    """Save ``state`` as the next post-job revision (caller holds the lock)."""
    state.revision = max(state.revision, effective_state(job).revision) + 1
    job.post_job = state
    await store.save(job)


def schedule_push(store, job_id: UUID) -> None:
    """Run :func:`run_push` in the background (does not block the caller)."""
    _queued.add(str(job_id))
    task = asyncio.create_task(_run_push_logged(store, job_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _run_push_logged(store, job_id: UUID) -> None:
    try:
        await run_push(store, job_id, queued=True)
    except PostJobError as exc:
        logger.info("Automatic insights push for job %s skipped: %s", job_id, exc.message)
    except Exception:
        logger.exception("Automatic insights push for job %s failed unexpectedly", job_id)
    finally:
        _queued.discard(str(job_id))


async def drain() -> None:
    """Wait for every scheduled background push (used by tests and shutdown)."""
    while _background:
        await asyncio.gather(*list(_background), return_exceptions=True)


async def read_state(store, job_id: UUID) -> Job:
    """Load the job, turning an interrupted ``pending`` push into a failure."""
    async with _lock(job_id):
        job = await _load(store, job_id)
        if job.post_job is not None:
            state = job.post_job.model_copy(deep=True)
            if _heal_interrupted(state, job_id):
                await _commit(store, job, state)
        return job


async def on_job_completed(store, job: Job) -> None:
    """Pipeline hook: the job just finished successfully."""
    if job.post_job is None:
        return  # caller chose no post-job flow (legacy/internal job)
    async with _lock(job.id):
        stored = await store.load(job.id) or job
        if stored.post_job is None:
            return
        state = stored.post_job.model_copy(deep=True)
        push_due = _reconcile(state, job_done=True)
        if push_due:
            _queue(state, job.id)
        await _commit(store, stored, state)
        job.post_job = stored.post_job
    if push_due:
        schedule_push(store, job.id)


async def on_job_failed(store, job: Job) -> None:
    """Pipeline hook: the job failed, so nothing waits for review or push."""
    if job.post_job is None:
        return
    async with _lock(job.id):
        stored = await store.load(job.id) or job
        if stored.post_job is None:
            return
        state = stored.post_job.model_copy(deep=True)
        if _settle_failed_job(state):
            await _commit(store, stored, state)
        job.post_job = stored.post_job


async def apply_override(
    store,
    job_id: UUID,
    review: bool | None,
    push: bool | None,
    *,
    push_allowed: bool = True,
) -> Job:
    """Change this job's review and/or push choice.

    Turning push on needs ``push_allowed`` (annotation access). Turning it off
    while a push is in flight records the choice and keeps the truthful final
    ``push_status`` that push writes.
    """
    async with _lock(job_id):
        job = await _load(store, job_id)
        if job.status == JobStatus.FAILED:
            raise PostJobError("The job failed; there is nothing to review or push.")
        state = effective_state(job).model_copy(deep=True)
        _heal_interrupted(state, job_id)
        if review is not None:
            state.review = "required" if review else "skipped"
        if push is not None:
            turned_on = push and state.push != "requested"
            if turned_on and not push_allowed:
                raise PostJobError(PUSH_ACCESS_MESSAGE, 403)
            state.push = "requested" if push else "not_requested"
            if turned_on and state.push_status in RETRYABLE_PUSH_STATUSES:
                state.push_status = "not_requested"  # a fresh opt-in tries again
        push_due = _reconcile(state, job_done=job.status == JobStatus.COMPLETED)
        if push_due:
            _queue(state, job_id)
        await _commit(store, job, state)
    if push_due:
        schedule_push(store, job_id)
    return job


async def complete_review(store, job_id: UUID) -> Job:
    """Mark the review done; a push that was waiting for it starts.

    That push was authorized when it was requested.
    """
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
        if push_due:
            _queue(state, job_id)
        await _commit(store, job, state)
    if push_due:
        schedule_push(store, job_id)
    return job


async def retry_push(store, job_id: UUID) -> Job:
    """Retry a failed, not-configured or interrupted push.

    Requesting a first push goes through :func:`apply_override` (PATCH).
    """
    async with _lock(job_id):
        job = await _load(store, job_id)
        state = effective_state(job).model_copy(deep=True)
        if job.status != JobStatus.COMPLETED or state.review_status == "pending_job":
            raise PostJobError("The job has not finished yet.")
        if is_push_in_flight(job_id):
            raise PostJobError("A push for this job is already in progress.")
        _heal_interrupted(state, job_id)
        if state.push_status not in RETRYABLE_PUSH_STATUSES:
            raise PostJobError(
                "Nothing to retry: this route only retries a failed or interrupted push. "
                "Use PATCH /enrich/{job_id}/post-job with push_to_insights=true to request a push."
            )
        if state.review_status == "awaiting_review":
            raise PostJobError("Complete or skip the review before pushing.")
        state.push = "requested"
        await _commit(store, job, state)
    return await run_push(store, job_id)


async def run_push(store, job_id: UUID, *, queued: bool = False) -> Job:
    """Build the job's propositions record and send it to insights once.

    ``queued`` marks the scheduled run of a push recorded by :func:`_queue`.
    """
    key = str(job_id)
    async with _lock(job_id):
        if key in _in_flight or (key in _queued and not queued):
            raise PostJobError("A push for this job is already in progress.")
        _queued.discard(key)
        job = await _load(store, job_id)
        state = effective_state(job).model_copy(deep=True)
        if state.review_status == "awaiting_review":
            raise PostJobError("Complete or skip the review before pushing.")
        _in_flight.add(key)
        try:
            state.push_status = "pending"
            state.push_attempts += 1
            state.last_push_at = _now()
            await _commit(store, job, state)
        except BaseException:
            _in_flight.discard(key)
            raise

    try:
        from app.services.export.propositions_exporter import build_proposition_record

        try:
            record = build_proposition_record(job).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 — invalid records become push failures
            logger.warning("Could not build the propositions record for job %s: %s", job_id, type(exc).__name__)
            result = insights_client.PushResult(state="failed", message="The job's proposition record could not be built.")
        else:
            result = await insights_client.push_record(record, transport=push_transport)

        async with _lock(job_id):
            try:
                return await _record_result(store, job_id, result)
            except Exception as exc:
                logger.warning("Could not save the push result for job %s: %s", job_id, type(exc).__name__)
                failed = insights_client.PushResult(state="failed", message="The push result could not be saved; retry.")
                try:
                    await _record_result(store, job_id, failed)
                except Exception:
                    logger.exception("Could not record the failed push for job %s", job_id)
                raise PostJobError("The push result could not be saved; retry.", 500) from exc
    finally:
        _in_flight.discard(key)


async def _record_result(store, job_id: UUID, result: insights_client.PushResult) -> Job:
    job = await _load(store, job_id)
    state = effective_state(job).model_copy(deep=True)
    state.push_status = result.state
    state.last_push_at = _now()
    if result.state == "pushed":
        state.last_push_error = None
        state.last_push_report = result.report
    else:
        state.last_push_error = result.message
    await _commit(store, job, state)
    return job


async def recover_on_startup(store) -> dict[str, int]:
    """Sweep persisted jobs once at boot (after orphaned jobs were failed).

    * ``pending`` pushes from the previous process become retryable failures.
    * Completed jobs whose post-job hook never ran (``pending_job``) get it now.
    * Failed jobs stop waiting for review or push.
    """
    counts = {"interrupted": 0, "resumed": 0, "settled_failed": 0}
    for path in sorted(store.base_dir.glob("*.json")):
        try:
            text = path.read_text()
            if '"post_job"' not in text:
                continue
            data = json.loads(text)
            post_job = data.get("post_job") or {}
            if not (
                post_job.get("push_status") in ("pending", "waiting_for_job")
                or post_job.get("review_status") == "pending_job"
            ):
                continue
            job_id = UUID(data["id"])
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            logger.debug("Skipping an unreadable job during post-job recovery")
            continue
        try:
            resume = False
            async with _lock(job_id):
                job = await store.load(job_id)
                if job is None or job.post_job is None:
                    continue
                state = job.post_job.model_copy(deep=True)
                changed = False
                if _heal_interrupted(state, job_id):
                    counts["interrupted"] += 1
                    changed = True
                if job.status == JobStatus.FAILED and _settle_failed_job(state):
                    counts["settled_failed"] += 1
                    changed = True
                resume = job.status == JobStatus.COMPLETED and state.review_status == "pending_job"
                if changed:
                    await _commit(store, job, state)
            if resume:
                await on_job_completed(store, job)
                counts["resumed"] += 1
        except Exception:
            logger.exception("Post-job startup recovery failed for job %s", job_id)
    if any(counts.values()):
        logger.info("Post-job startup recovery: %s", counts)
    return counts
