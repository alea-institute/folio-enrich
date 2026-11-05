"""Execution slots are shared across orchestrators, independently of admission."""
import asyncio

import pytest

from app.config import Settings, settings
from app.models.job import Job, JobStatus
from app.pipeline.orchestrator import PipelineConfig, PipelineOrchestrator
from app.storage.job_store import JobStore

QUEUE_MESSAGE = "Queued: waiting for a free pipeline slot"


def queue_entries(job):
    return [entry for entry in job.result.metadata.get("activity_log", [])
            if entry["stage"] == "queue"]


@pytest.fixture
def store(tmp_path):
    return JobStore(base_dir=tmp_path)


@pytest.fixture
def cap_one(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_pipelines", 1, raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("parallel", [False, True])
async def test_serial_runs_queue_pending_and_persist(monkeypatch, store, cap_one, parallel):
    first_entered, release_first, queued = asyncio.Event(), asyncio.Event(), asyncio.Event()
    first, second = Job(), Job()
    order = []
    original_save = store.save

    async def save(job):
        await original_save(job)
        if queue_entries(job):
            queued.set()

    async def execute(self, job):
        order.append((job.id, "start"))
        job.status = JobStatus.ENRICHING
        if job is first:
            first_entered.set()
            await release_first.wait()
        order.append((job.id, "end"))
        return job

    monkeypatch.setattr(store, "save", save)
    monkeypatch.setattr(PipelineOrchestrator, "_run_parallel" if parallel else "_run_flat", execute)
    pipelines = [PipelineOrchestrator(store, stages=[]) for _ in range(2)]
    if parallel:
        for pipeline in pipelines:
            pipeline._config = PipelineConfig()
    tasks = []
    try:
        tasks.append(asyncio.create_task(pipelines[0].run(first)))
        await asyncio.wait_for(first_entered.wait(), 1)
        tasks.append(asyncio.create_task(pipelines[1].run(second)))
        await asyncio.wait_for(queued.wait(), 1)
        assert second.status == JobStatus.PENDING
        saved = await store.load(second.id)
        assert saved.status == JobStatus.PENDING
        assert len(queue_entries(saved)) == 1
        assert queue_entries(saved)[0]["msg"] == QUEUE_MESSAGE
        assert not queue_entries(first)
        assert order == [(first.id, "start")]
        release_first.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 1)
        assert order == [(first.id, "start"), (first.id, "end"),
                         (second.id, "start"), (second.id, "end")]
        assert len(queue_entries(second)) == 1
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_failure_or_cancellation_releases_slot(monkeypatch, store, cap_one, cancel):
    entered, release = asyncio.Event(), asyncio.Event()
    first, second = Job(), Job()

    async def execute(self, job):
        if job is first:
            entered.set()
            await release.wait()
            raise RuntimeError("pipeline failed")
        return job

    monkeypatch.setattr(PipelineOrchestrator, "_run_flat", execute)
    first_task = asyncio.create_task(PipelineOrchestrator(store, stages=[]).run(first))
    second_task = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second_task = asyncio.create_task(PipelineOrchestrator(store, stages=[]).run(second))
        await asyncio.sleep(0)
        assert not second_task.done()
        if cancel:
            first_task.cancel()
        else:
            release.set()
        with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
            await first_task
        assert await asyncio.wait_for(second_task, 1) is second
    finally:
        first_task.cancel()
        if second_task is not None:
            second_task.cancel()
        await asyncio.gather(first_task, *([second_task] if second_task else []), return_exceptions=True)


@pytest.mark.asyncio
async def test_cap_two_allows_two_simultaneous_runs(monkeypatch, store):
    monkeypatch.setattr(settings, "max_parallel_pipelines", 2, raising=False)
    both_entered, release = asyncio.Event(), asyncio.Event()
    active = 0

    async def execute(self, job):
        nonlocal active
        active += 1
        if active == 2:
            both_entered.set()
        await release.wait()
        active -= 1
        return job

    monkeypatch.setattr(PipelineOrchestrator, "_run_flat", execute)
    jobs = [Job(), Job()]
    tasks = [asyncio.create_task(PipelineOrchestrator(store, stages=[]).run(job)) for job in jobs]
    try:
        await asyncio.wait_for(both_entered.wait(), 1)
        assert active == 2
        assert all(not queue_entries(job) for job in jobs)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 1)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("value, expected", [(0, 1), (-3, 1), (1, 1), (2, 2)])
def test_setting_from_environment_clamps_to_one(monkeypatch, value, expected):
    monkeypatch.setenv("FOLIO_ENRICH_MAX_PARALLEL_PIPELINES", str(value))
    assert Settings().max_parallel_pipelines == expected


def test_contended_gate_works_with_fresh_event_loops(monkeypatch, store, cap_one):
    async def exercise():
        release = asyncio.Event()

        async def execute(self, job):
            await release.wait()
            return job

        monkeypatch.setattr(PipelineOrchestrator, "_run_flat", execute)
        jobs = [Job(), Job()]
        tasks = [asyncio.create_task(PipelineOrchestrator(store, stages=[]).run(job)) for job in jobs]
        try:
            await asyncio.sleep(0)
            assert len(queue_entries(jobs[1])) == 1
            release.set()
            await asyncio.wait_for(asyncio.gather(*tasks), 1)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(exercise())
    asyncio.run(exercise())
