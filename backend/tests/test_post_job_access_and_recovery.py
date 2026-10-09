"""Post-job flow: push authorization, override durability, and recovery.

* Every push trigger needs annotation access (open in local mode; refused in
  token mode without credentials, allowed with them), and the post-job server
  defaults need the admin token when one is configured.
* A user's review/push override survives the orchestrator's later saves of
  its stale in-memory job, on both the flat and the production parallel path.
* A stored ``pending`` push with nothing in flight is reported as interrupted,
  a failed final save records ``failed``, and a startup sweep settles jobs.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.config import settings
from app.models.job import JobStatus
from app.pipeline.orchestrator import PipelineOrchestrator
from app.pipeline.stages.base import PipelineStage
from app.services.post_job import flow
from tests.helpers import make_job
from tests.test_post_job_flow import (  # noqa: F401 — fixtures used by name
    BASE,
    SENTENCES,
    TEXT,
    TOKEN,
    FakePropositionStage,
    _proposition,
    defaults,
    insights,
    settle,
    store,
    submit,
)

ANNOTATION = "annot-secret-for-tests"
ADMIN = "admin-secret-for-tests"
AUTH = {"X-Annotation-Token": ANNOTATION}


@pytest.fixture
def token_mode(monkeypatch):
    monkeypatch.setattr(settings, "annotation_token", ANNOTATION)
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "cf_access_team_domain", "")


@pytest.fixture(autouse=True)
def open_mode_by_default(monkeypatch):
    monkeypatch.setattr(settings, "annotation_token", "")
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "cf_access_team_domain", "")


async def completed_job(store, *, review=False, push=False, push_status=None, status=JobStatus.COMPLETED):
    job = make_job(text=TEXT, status=status)
    job.result.propositions = [_proposition(s) for s in SENTENCES]
    job.post_job = flow.initial_state(review, push)
    if status == JobStatus.COMPLETED:
        flow._reconcile(job.post_job, job_done=True)
    if push_status is not None:
        job.post_job.push_status = push_status
    await store.save(job)
    return job


# ── Authorization of push triggers ───────────────────────────────────────


async def test_push_access_route(client, store, monkeypatch):
    body = (await client.get("/enrich/push-access")).json()
    assert body == {"push_allowed": True, "insights_configured": False}
    monkeypatch.setattr(settings, "annotation_token", ANNOTATION)
    assert (await client.get("/enrich/push-access")).json()["push_allowed"] is False
    assert (await client.get("/enrich/push-access", headers=AUTH)).json()["push_allowed"] is True
    cookie = {"Cookie": f"folio_annotation_access={ANNOTATION}", "Origin": "http://test"}
    assert (await client.get("/enrich/push-access", headers=cookie)).json()["push_allowed"] is True
    foreign = {"Cookie": f"folio_annotation_access={ANNOTATION}", "Origin": "https://evil.example"}
    assert (await client.get("/enrich/push-access", headers=foreign)).json()["push_allowed"] is False


async def test_access_cookie_reaches_enrich_routes(client, monkeypatch):
    monkeypatch.setattr(settings, "annotation_token", ANNOTATION)
    exchange = await client.post("/gold/access", json={"token": ANNOTATION})
    cookies = exchange.headers.get_list("set-cookie")
    assert any("Path=/gold" in c for c in cookies)
    assert any("Path=/enrich" in c and "HttpOnly" in c and "SameSite=strict" in c for c in cookies)


async def test_open_mode_allows_every_trigger(client, store, insights):
    job_id = await submit(client, push_to_insights=True)
    assert (await settle(store, job_id))["push_status"] == "pushed"
    other = await submit(client, push_to_insights=False)
    await settle(store, other)
    assert (await client.patch(f"/enrich/{other}/post-job", json={"push_to_insights": True})).status_code == 200


async def test_submission_push_needs_access(client, store, insights, token_mode):
    refused = await client.post("/enrich", json={"content": TEXT, "push_to_insights": True})
    assert refused.status_code == 403
    assert refused.json()["detail"] == flow.PUSH_ACCESS_MESSAGE
    allowed = await client.post("/enrich", json={"content": TEXT, "push_to_insights": True}, headers=AUTH)
    assert allowed.status_code == 202
    assert (await settle(store, allowed.json()["job_id"]))["push_status"] == "pushed"


async def test_push_default_never_applies_without_access(client, store, insights, token_mode, monkeypatch):
    monkeypatch.setattr(settings, "post_job_push_default", True)
    anonymous = await submit(client)
    state = await settle(store, anonymous)
    assert state["push"] == "not_requested"
    assert state["push_status"] == "not_requested"
    response = await client.post("/enrich", json={"content": TEXT}, headers=AUTH)
    assert (await settle(store, response.json()["job_id"]))["push_status"] == "pushed"
    assert len(insights.requests) == 1


async def test_patch_turning_push_on_needs_access(client, store, insights, token_mode):
    job = await completed_job(store)
    url = f"/enrich/{job.id}/post-job"
    refused = await client.patch(url, json={"push_to_insights": True})
    assert refused.status_code == 403
    assert (await client.get(url)).json()["post_job"]["push"] == "not_requested"
    # Review changes and turning push off need no push access.
    assert (await client.patch(url, json={"review_before_continuing": True})).status_code == 200
    assert (await client.patch(url, json={"push_to_insights": False})).status_code == 200
    assert (await client.patch(url, json={"review_before_continuing": False, "push_to_insights": True}, headers=AUTH)).status_code == 200
    await flow.drain()
    assert (await client.get(url)).json()["post_job"]["push_status"] == "pushed"


async def test_retry_needs_access(client, store, insights, token_mode):
    job = await completed_job(store, push=True, push_status="failed")
    url = f"/enrich/{job.id}/insights-push"
    assert (await client.post(url)).status_code == 403
    assert insights.requests == []
    retry = await client.post(url, headers=AUTH)
    assert retry.status_code == 200
    assert retry.json()["post_job"]["push_status"] == "pushed"
    assert retry.json()["push_allowed"] is True


async def test_post_job_defaults_need_admin_token_when_configured(client, monkeypatch):
    original = (settings.post_job_review_default, settings.post_job_push_default)
    try:
        monkeypatch.setattr(settings, "admin_token", ADMIN)
        refused = await client.put("/settings", json={"post_job_push_default": True, "llm_model": "x"})
        assert refused.status_code == 403
        assert settings.post_job_push_default is False
        assert settings.llm_model != "x"  # a refused request changes nothing
        # The rest of PUT /settings is unchanged (no admin token needed).
        assert (await client.put("/settings", json={"translation_matching_enabled": False})).status_code == 200
        ok = await client.put("/settings", json={"post_job_review_default": True, "post_job_push_default": True},
                              headers={"X-Admin-Token": ADMIN})
        assert ok.status_code == 200
        got = (await client.get("/settings")).json()
        assert got["post_job_review_default"] is True
        assert got["post_job_push_default"] is True
    finally:
        settings.post_job_review_default, settings.post_job_push_default = original


async def test_settings_round_trip_and_no_leak(client, monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", BASE)
    monkeypatch.setattr(settings, "insights_api_token", TOKEN)
    for review, push in ((True, False), (False, True), (False, False)):
        assert (await client.put("/settings", json={"post_job_review_default": review,
                                                    "post_job_push_default": push})).status_code == 200
        got = await client.get("/settings")
        body = got.json()
        assert (body["post_job_review_default"], body["post_job_push_default"]) == (review, push)
        assert body["insights_configured"] is True
        assert BASE not in got.text and TOKEN not in got.text
        assert "insights-private.internal" not in got.text
    monkeypatch.setattr(settings, "insights_api_url", "   ")
    assert (await client.get("/settings")).json()["insights_configured"] is False


# ── Overrides survive the orchestrator's stale saves ─────────────────────


class FakeAssessor:
    """Stands in for the post-completion area-of-law step and PATCHes mid-step."""

    store = None
    override: dict = {}

    def __init__(self, llm):
        pass

    async def assess(self, job):
        await flow.apply_override(FakeAssessor.store, job.id, **FakeAssessor.override)
        return [{"area": "Contracts"}]


@pytest.fixture
def patch_during_post_completion(monkeypatch, store):
    from app.services.concept import area_of_law_assessor

    FakeAssessor.store = store
    monkeypatch.setattr(area_of_law_assessor, "AreaOfLawAssessor", FakeAssessor)
    return FakeAssessor


async def _run(orchestrator, store, review, push):
    job = make_job(text=TEXT, status=JobStatus.PENDING)
    job.post_job = flow.initial_state(review, push)
    await store.save(job)
    await orchestrator.run(job)
    await flow.drain()
    return await store.load(job.id)


async def test_override_during_post_completion_survives_flat(store, insights, patch_during_post_completion):
    patch_during_post_completion.override = {"review": None, "push": True}
    orchestrator = PipelineOrchestrator(store, stages=[FakePropositionStage()], llm=object())
    stored = await _run(orchestrator, store, review=False, push=False)
    assert stored.result.metadata["areas_of_law"] == [{"area": "Contracts"}]  # the stale save happened
    assert stored.post_job.push == "requested"
    assert stored.post_job.push_status == "pushed"
    assert stored.post_job.push_attempts == 1
    assert len(insights.requests) == 1


async def test_review_override_during_post_completion_survives_flat(store, insights, patch_during_post_completion):
    patch_during_post_completion.override = {"review": True, "push": None}
    orchestrator = PipelineOrchestrator(store, stages=[FakePropositionStage()], llm=object())
    stored = await _run(orchestrator, store, review=False, push=True)
    assert stored.post_job.review == "required"
    assert stored.post_job.review_status == "awaiting_review"
    assert stored.post_job.push_status == "waiting_for_review"
    assert insights.requests == []


async def test_override_mid_pipeline_survives_stage_saves(store, insights):
    class OverrideStage(PipelineStage):
        name = "override"

        async def execute(self, job):
            await flow.apply_override(store, job.id, True, None)
            return job

    orchestrator = PipelineOrchestrator(store, stages=[FakePropositionStage(), OverrideStage(), FakePropositionStage()])
    stored = await _run(orchestrator, store, review=False, push=True)
    assert stored.post_job.review_status == "awaiting_review"
    assert stored.post_job.push_status == "waiting_for_review"
    assert insights.requests == []


@pytest.mark.timeout(120)
async def test_override_survives_production_parallel_path(store, insights, patch_during_post_completion):
    patch_during_post_completion.override = {"review": None, "push": True}
    orchestrator = PipelineOrchestrator(store, llm=None)
    assert orchestrator._config is not None  # the production three-phase path
    orchestrator._llm = object()  # enables only the post-completion area-of-law step
    stored = await _run(orchestrator, store, review=False, push=False)
    assert stored.status == JobStatus.COMPLETED
    assert stored.result.metadata.get("areas_of_law") == [{"area": "Contracts"}]
    assert stored.post_job.push == "requested"
    assert stored.post_job.push_status == "pushed"
    assert len(insights.requests) == 1


# ── Interrupted pushes, failed saves, startup recovery ───────────────────


async def test_interrupted_pending_reads_as_failed_and_retries(client, store, insights):
    job = await completed_job(store, push=True, push_status="pending")
    body = (await client.get(f"/enrich/{job.id}/post-job")).json()
    assert body["post_job"]["push_status"] == "failed"
    assert body["post_job"]["last_push_error"] == flow.INTERRUPTED_MESSAGE
    retry = await client.post(f"/enrich/{job.id}/insights-push")
    assert retry.status_code == 200
    assert retry.json()["post_job"]["push_status"] == "pushed"


async def test_failed_result_save_records_failed(store, insights, monkeypatch):
    job = await completed_job(store, push=True, push_status="failed")
    real_save = store.save
    calls = {"n": 0}

    async def flaky(j):
        calls["n"] += 1
        if calls["n"] == 3:  # 1 = retry's request, 2 = "pending", 3 = the result
            raise OSError("disk full")
        await real_save(j)

    monkeypatch.setattr(store, "save", flaky)
    with pytest.raises(flow.PostJobError) as caught:
        await flow.retry_push(store, job.id)
    assert caught.value.status_code == 500
    stored = await store.load(job.id)
    assert stored.post_job.push_status == "failed"
    assert stored.post_job.last_push_error == "The push result could not be saved; retry."
    assert not flow.is_push_in_flight(job.id)


async def test_patch_push_off_during_flight_keeps_truthful_status(store, insights, monkeypatch):
    import httpx

    gate = asyncio.Event()

    async def slow(request):
        await gate.wait()
        return httpx.Response(200, json={"created": 2, "existing": 0, "skipped": 0, "refused": 0})

    monkeypatch.setattr(flow, "push_transport", httpx.MockTransport(slow))
    job = await completed_job(store, push=False)
    await flow.apply_override(store, job.id, None, True)
    for _ in range(200):
        if flow.is_push_in_flight(job.id):
            break
        await asyncio.sleep(0.005)
    turned_off = await flow.apply_override(store, job.id, None, False)
    assert turned_off.post_job.push == "not_requested"
    assert turned_off.post_job.push_status == "pending"
    gate.set()
    await flow.drain()
    stored = await store.load(job.id)
    assert stored.post_job.push == "not_requested"
    assert stored.post_job.push_status == "pushed"


async def test_startup_recovery(store, insights):
    interrupted = await completed_job(store, push=True, push_status="pending")
    hookless = make_job(text=TEXT)  # completed, but its hook never ran
    hookless.result.propositions = [_proposition(s) for s in SENTENCES]
    hookless.post_job = flow.initial_state(False, True)
    await store.save(hookless)
    failed = make_job(text=TEXT, status=JobStatus.FAILED)
    failed.post_job = flow.initial_state(True, True)
    await store.save(failed)
    untouched = await completed_job(store, push=True, push_status="pushed")

    counts = await flow.recover_on_startup(store)
    await flow.drain()
    assert counts == {"interrupted": 1, "resumed": 1, "settled_failed": 1}
    assert (await store.load(interrupted.id)).post_job.last_push_error == flow.INTERRUPTED_MESSAGE
    assert (await store.load(hookless.id)).post_job.push_status == "pushed"
    settled = (await store.load(failed.id)).post_job
    assert (settled.review_status, settled.push_status) == ("not_required", "not_requested")
    assert (await store.load(untouched.id)).post_job.push_status == "pushed"
    assert len(insights.requests) == 1


async def test_revision_merge_never_rolls_back(store):
    job = await completed_job(store, push=False)
    stale = await store.load(job.id)
    await flow.apply_override(store, job.id, True, None)
    stale.result.metadata["note"] = "written later from a stale copy"
    await store.save(stale)
    stored = await store.load(job.id)
    assert stored.result.metadata["note"] == "written later from a stale copy"
    assert stored.post_job.review == "required"
    assert stored.post_job.revision >= 1
    assert uuid.UUID(str(stored.id)) == job.id
