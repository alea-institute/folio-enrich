"""Post-job flow: optional review step, then optional push to folio-insights.

Covers the four review x push combinations end to end through POST /enrich and
a real (flat-mode) pipeline run, server defaults, per-job overrides at
submission and at completion, review completion triggering the push, retry
after a failure, idempotent re-push, the not-configured state, token hygiene,
and legacy jobs without ``post_job``.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest
from folio_propositions import ActorRef, Disposition, Proposition

from app.api.routes import enrich as enrich_mod
from app.api.routes import export as export_mod
from app.config import settings
from app.models.document import CanonicalText, TextChunk
from app.models.job import Job, JobStatus
from app.pipeline.orchestrator import PipelineOrchestrator
from app.pipeline.stages.base import PipelineStage
from app.services import insights_client
from app.services.post_job import flow
from app.storage.job_store import JobStore
from tests.helpers import make_job

TOKEN = "tok-post-job-secret-0123456789"
BASE = "http://insights-private.internal:9321"
TEXT = "We hold that the rule applies. The court denied the motion."
SENTENCES = ("We hold that the rule applies.", "The court denied the motion.")


def _proposition(text: str) -> Proposition:
    start = TEXT.index(text)
    return Proposition(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, text)),
        start_char=start,
        end_char=start + len(text),
        text=text,
        proposition_type="Judicial Legal Conclusion",
        asserter=ActorRef(role="court"),
        validator=None,
        disposition=Disposition.ACCEPTED,
    )


class FakePropositionStage(PipelineStage):
    """Stands in for the whole pipeline: canonical text + two propositions."""

    @property
    def name(self) -> str:
        return "fake_propositions"

    async def execute(self, job: Job) -> Job:
        job.result.canonical_text = CanonicalText(
            full_text=TEXT,
            chunks=[TextChunk(text=TEXT, start_offset=0, end_offset=len(TEXT), chunk_index=0)],
        )
        job.result.propositions = [_proposition(s) for s in SENTENCES]
        return job


class FakeInsights:
    """Mock insights ingest route: idempotent per content IRI, like the real one."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.bodies: list[dict] = []
        self.stored: set[str] = set()
        self.fail_next: list[int] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_next:
            return httpx.Response(self.fail_next.pop(0), json={"detail": f"boom {BASE} {TOKEN}"})
        assert request.url.path == "/api/bridge/v1/ingest"
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"detail": "bad token"})
        body = json.loads(request.content)
        self.bodies.append(body)
        iris = [p["content_iri"] for p in body["propositions"]]
        created = [i for i in iris if i not in self.stored]
        existing = [i for i in iris if i in self.stored]
        self.stored.update(iris)
        return httpx.Response(200, json={
            "corpus": request.url.params.get("corpus") or "default",
            "created": len(created), "existing": len(existing), "skipped": 0, "refused": 0,
            "created_iris": created, "existing_iris": existing, "skipped_iris": [], "refused_iris": [],
        })


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = JobStore(base_dir=tmp_path / "jobs")
    monkeypatch.setattr(enrich_mod, "_job_store", store)
    monkeypatch.setattr(export_mod, "_job_store", store)

    def flat_orchestrator(job_store, llm=None, task_llms=None):
        return PipelineOrchestrator(job_store, stages=[FakePropositionStage()])

    monkeypatch.setattr(enrich_mod, "PipelineOrchestrator", flat_orchestrator)
    return store


@pytest.fixture
def insights(monkeypatch):
    fake = FakeInsights()
    monkeypatch.setattr(settings, "insights_api_url", BASE)
    monkeypatch.setattr(settings, "insights_api_token", TOKEN)
    monkeypatch.setattr(settings, "insights_corpus", "scratch")
    monkeypatch.setattr(settings, "insights_framework_id", "fw-1")
    monkeypatch.setattr(flow, "push_transport", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture(autouse=True)
def defaults(monkeypatch):
    monkeypatch.setattr(settings, "post_job_review_default", False)
    monkeypatch.setattr(settings, "post_job_push_default", False)


async def submit(client, **fields) -> str:
    body = {"content": TEXT, "format": "plain_text", **fields}
    response = await client.post("/enrich", json=body)
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


async def settle(store: JobStore, job_id: str) -> dict:
    """Wait for the pipeline task, then for any background push."""
    for _ in range(500):
        job = await store.load(uuid.UUID(job_id))
        if job is not None and job.status in (JobStatus.COMPLETED, JobStatus.FAILED) \
                and job.post_job is not None and job.post_job.review_status != "pending_job":
            break
        await asyncio.sleep(0.01)
    else:  # pragma: no cover - diagnostic
        raise AssertionError("job did not finish")
    await flow.drain()
    job = await store.load(uuid.UUID(job_id))
    return job.post_job.model_dump(mode="json")


# ── The four combinations ────────────────────────────────────────────────


async def test_no_review_no_push(client, store, insights):
    job_id = await submit(client, review_before_continuing=False, push_to_insights=False)
    state = await settle(store, job_id)
    assert state["review"] == "skipped" and state["push"] == "not_requested"
    assert state["review_status"] == "not_required"
    assert state["push_status"] == "not_requested"
    assert insights.requests == []


async def test_no_review_push(client, store, insights):
    job_id = await submit(client, review_before_continuing=False, push_to_insights=True)
    state = await settle(store, job_id)
    assert state["review_status"] == "not_required"
    assert state["push_status"] == "pushed"
    assert state["push_attempts"] == 1
    assert state["last_push_report"] == {"created": 2, "existing": 0, "skipped": 0, "refused": 0, "corpus": "scratch"}
    assert len(insights.requests) == 1
    request = insights.requests[0]
    assert request.method == "POST"
    assert dict(request.url.params) == {"corpus": "scratch", "framework_id": "fw-1"}
    assert request.headers["content-type"] == "application/json"
    # The body is the same shared-schema record the pull export serves.
    export = await client.get(f"/enrich/{job_id}/export", params={"format": "propositions"})
    assert export.status_code == 200
    pulled = export.json()
    pushed = insights.bodies[0]
    assert pushed["propositions"] == pulled["propositions"]
    assert pushed["source_uri"] == pulled["source_uri"]


async def test_review_no_push(client, store, insights):
    job_id = await submit(client, review_before_continuing=True, push_to_insights=False)
    state = await settle(store, job_id)
    assert state["review_status"] == "awaiting_review"
    assert state["push_status"] == "not_requested"
    response = await client.post(f"/enrich/{job_id}/review/complete")
    assert response.status_code == 200
    body = response.json()
    assert body["post_job"]["review_status"] == "completed"
    assert body["post_job"]["review_completed_at"]
    await flow.drain()
    assert body["post_job"]["push_status"] == "not_requested"
    assert insights.requests == []


async def test_review_then_push(client, store, insights):
    job_id = await submit(client, review_before_continuing=True, push_to_insights=True)
    state = await settle(store, job_id)
    assert state["review_status"] == "awaiting_review"
    assert state["push_status"] == "waiting_for_review"
    assert insights.requests == []  # the push waits for the review

    # Manual push is refused while the review is pending.
    refused = await client.post(f"/enrich/{job_id}/insights-push")
    assert refused.status_code == 409

    response = await client.post(f"/enrich/{job_id}/review/complete")
    assert response.status_code == 200
    await flow.drain()
    state = (await client.get(f"/enrich/{job_id}/post-job")).json()["post_job"]
    assert state["review_status"] == "completed"
    assert state["push_status"] == "pushed"
    assert state["last_push_report"]["created"] == 2
    assert len(insights.requests) == 1

    # Completing again is idempotent and does not push again.
    again = await client.post(f"/enrich/{job_id}/review/complete")
    assert again.status_code == 200
    await flow.drain()
    assert len(insights.requests) == 1


# ── Defaults and overrides ───────────────────────────────────────────────


async def test_server_defaults_apply_when_request_omits_fields(client, store, insights, monkeypatch):
    put = await client.put("/settings", json={"post_job_review_default": False, "post_job_push_default": True})
    assert put.status_code == 200
    got = (await client.get("/settings")).json()
    assert got["post_job_review_default"] is False
    assert got["post_job_push_default"] is True
    assert got["insights_configured"] is True
    assert BASE not in json.dumps(got) and TOKEN not in json.dumps(got)

    job_id = await submit(client)
    state = await settle(store, job_id)
    assert state["review"] == "skipped"
    assert state["push"] == "requested"
    assert state["push_status"] == "pushed"


async def test_review_default_applies(client, store, insights, monkeypatch):
    monkeypatch.setattr(settings, "post_job_review_default", True)
    job_id = await submit(client)
    state = await settle(store, job_id)
    assert state["review"] == "required"
    assert state["review_status"] == "awaiting_review"
    assert state["push_status"] == "not_requested"


async def test_submission_override_beats_server_default(client, store, insights, monkeypatch):
    monkeypatch.setattr(settings, "post_job_review_default", True)
    monkeypatch.setattr(settings, "post_job_push_default", True)
    job_id = await submit(client, review_before_continuing=False, push_to_insights=False)
    state = await settle(store, job_id)
    assert state["review_status"] == "not_required"
    assert state["push_status"] == "not_requested"
    assert insights.requests == []


async def test_submission_response_reports_initial_state(client, store, insights):
    response = await client.post("/enrich", json={"content": TEXT, "review_before_continuing": True, "push_to_insights": True})
    body = response.json()
    assert body["post_job"]["review_status"] == "pending_job"
    assert body["post_job"]["push_status"] == "waiting_for_job"
    await settle(store, body["job_id"])


async def test_patch_override_at_completion(client, store, insights):
    job_id = await submit(client, review_before_continuing=True, push_to_insights=False)
    await settle(store, job_id)

    turned_on = await client.patch(f"/enrich/{job_id}/post-job", json={"push_to_insights": True})
    assert turned_on.status_code == 200
    assert turned_on.json()["post_job"]["push_status"] == "waiting_for_review"
    await flow.drain()
    assert insights.requests == []

    skipped = await client.patch(f"/enrich/{job_id}/post-job", json={"review_before_continuing": False})
    assert skipped.status_code == 200
    assert skipped.json()["post_job"]["review_status"] == "not_required"
    await flow.drain()
    state = (await client.get(f"/enrich/{job_id}/post-job")).json()["post_job"]
    assert state["push_status"] == "pushed"
    assert len(insights.requests) == 1


async def test_patch_push_on_after_skipped_review_pushes(client, store, insights):
    job_id = await submit(client, review_before_continuing=False, push_to_insights=False)
    await settle(store, job_id)
    await client.patch(f"/enrich/{job_id}/post-job", json={"push_to_insights": True})
    await flow.drain()
    state = (await client.get(f"/enrich/{job_id}/post-job")).json()["post_job"]
    assert state["push_status"] == "pushed"


async def test_patch_review_on_after_completion_holds_push(client, store, insights):
    job_id = await submit(client, review_before_continuing=False, push_to_insights=False)
    await settle(store, job_id)
    body = (await client.patch(f"/enrich/{job_id}/post-job", json={"review_before_continuing": True, "push_to_insights": True})).json()
    assert body["post_job"]["review_status"] == "awaiting_review"
    assert body["post_job"]["push_status"] == "waiting_for_review"
    await flow.drain()
    assert insights.requests == []


async def test_patch_push_off_cancels_waiting_push(client, store, insights):
    job_id = await submit(client, review_before_continuing=True, push_to_insights=True)
    await settle(store, job_id)
    body = (await client.patch(f"/enrich/{job_id}/post-job", json={"push_to_insights": False})).json()
    assert body["post_job"]["push_status"] == "not_requested"
    await client.post(f"/enrich/{job_id}/review/complete")
    await flow.drain()
    assert insights.requests == []


# ── Failures, retry, idempotency, configuration ──────────────────────────


async def test_failure_then_retry(client, store, insights):
    insights.fail_next = [503]
    job_id = await submit(client, push_to_insights=True)
    state = await settle(store, job_id)
    assert state["push_status"] == "failed"
    assert state["last_push_error"] == "folio-insights returned a server error (503)."
    assert state["push_attempts"] == 1

    retry = await client.post(f"/enrich/{job_id}/insights-push")
    assert retry.status_code == 200
    state = retry.json()["post_job"]
    assert state["push_status"] == "pushed"
    assert state["push_attempts"] == 2
    assert state["last_push_error"] is None


@pytest.mark.parametrize("code,message", [
    (401, "folio-insights rejected the configured credentials."),
    (404, "folio-insights ingest is disabled or the corpus is unknown."),
    (413, "folio-insights refused the record as too large."),
])
async def test_http_errors_are_sanitized_failures(client, store, insights, code, message):
    insights.fail_next = [code]
    job_id = await submit(client, push_to_insights=True)
    state = await settle(store, job_id)
    assert state["push_status"] == "failed"
    assert state["last_push_error"] == message


async def test_repush_is_idempotent(client, store, insights):
    """Two jobs over the same text push the same content IRIs: no duplicates."""
    first = await submit(client, push_to_insights=True)
    await settle(store, first)
    second = await submit(client, push_to_insights=True)
    state = await settle(store, second)
    assert state["push_status"] == "pushed"
    assert state["last_push_error"] is None
    assert state["last_push_report"]["created"] == 0
    assert state["last_push_report"]["existing"] == 2
    assert len(insights.stored) == 2  # no duplicate shards
    assert [p["content_iri"] for p in insights.bodies[0]["propositions"]] == \
        [p["content_iri"] for p in insights.bodies[1]["propositions"]]


async def test_retry_route_is_retry_only(client, store, insights):
    pushed = await submit(client, push_to_insights=True)
    await settle(store, pushed)
    response = await client.post(f"/enrich/{pushed}/insights-push")
    assert response.status_code == 409
    assert "PATCH" in response.json()["detail"]

    never = await submit(client, push_to_insights=False)
    await settle(store, never)
    assert (await client.post(f"/enrich/{never}/insights-push")).status_code == 409
    assert len(insights.requests) == 1


async def test_retry_after_not_configured(client, store, insights, monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "")
    job_id = await submit(client, push_to_insights=True)
    assert (await settle(store, job_id))["push_status"] == "not_configured"
    monkeypatch.setattr(settings, "insights_api_url", BASE)
    retry = await client.post(f"/enrich/{job_id}/insights-push")
    assert retry.status_code == 200
    assert retry.json()["post_job"]["push_status"] == "pushed"


async def test_not_configured(client, store, monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "")
    job_id = await submit(client, push_to_insights=True)
    state = await settle(store, job_id)
    assert state["push_status"] == "not_configured"
    payload = (await client.get(f"/enrich/{job_id}/post-job")).json()
    assert payload["insights_configured"] is False


async def test_token_and_url_never_exposed(client, store, insights):
    insights.fail_next = [500]
    job_id = await submit(client, review_before_continuing=False, push_to_insights=True)
    await settle(store, job_id)
    responses = [
        await client.get(f"/enrich/{job_id}"),
        await client.get(f"/enrich/{job_id}/post-job"),
        await client.post(f"/enrich/{job_id}/insights-push"),
        await client.patch(f"/enrich/{job_id}/post-job", json={"push_to_insights": True}),
    ]
    on_disk = (store.base_dir / f"{job_id}.json").read_text()
    for text in [r.text for r in responses] + [on_disk]:
        assert TOKEN not in text
        assert BASE not in text
        assert "insights-private.internal" not in text


async def test_concurrent_triggers_push_once(store, insights, monkeypatch):
    gate = asyncio.Event()
    calls: list[httpx.Request] = []

    async def slow(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        await gate.wait()
        return httpx.Response(200, json={"created": 2, "existing": 0, "skipped": 0, "refused": 0})

    monkeypatch.setattr(flow, "push_transport", httpx.MockTransport(slow))
    job = make_job(text=TEXT)
    job.result.propositions = [_proposition(s) for s in SENTENCES]
    job.post_job = flow.initial_state(False, True)
    await store.save(job)
    await flow.on_job_completed(store, job)  # schedules the background push
    for _ in range(200):
        if flow.is_push_in_flight(job.id):
            break
        await asyncio.sleep(0.005)
    with pytest.raises(flow.PostJobError):
        await flow.retry_push(store, job.id)
    with pytest.raises(flow.PostJobError):
        await flow.run_push(store, job.id)
    gate.set()
    await flow.drain()
    assert len(calls) == 1
    stored = await store.load(job.id)
    assert stored.post_job.push_status == "pushed"
    assert stored.post_job.push_attempts == 1


# ── State-machine guards and legacy jobs ─────────────────────────────────


async def test_unknown_job_404(client, store):
    missing = uuid.uuid4()
    assert (await client.get(f"/enrich/{missing}/post-job")).status_code == 404
    assert (await client.patch(f"/enrich/{missing}/post-job", json={})).status_code == 404
    assert (await client.post(f"/enrich/{missing}/review/complete")).status_code == 404
    assert (await client.post(f"/enrich/{missing}/insights-push")).status_code == 404


async def test_actions_before_completion_are_409(client, store, insights):
    job = make_job(text=TEXT, status=JobStatus.ENRICHING)
    job.post_job = flow.initial_state(True, True)
    await store.save(job)
    assert (await client.post(f"/enrich/{job.id}/review/complete")).status_code == 409
    assert (await client.post(f"/enrich/{job.id}/insights-push")).status_code == 409
    # Changing the choices before completion is allowed and only records intent.
    body = (await client.patch(f"/enrich/{job.id}/post-job", json={"push_to_insights": False})).json()
    assert body["post_job"]["push_status"] == "not_requested"
    assert body["post_job"]["review_status"] == "pending_job"


async def test_failed_job_rejects_override(client, store):
    job = make_job(text=TEXT, status=JobStatus.FAILED)
    job.post_job = flow.initial_state(False, True)
    await store.save(job)
    assert (await client.patch(f"/enrich/{job.id}/post-job", json={"push_to_insights": True})).status_code == 409


async def test_failed_pipeline_does_not_push(store, insights):
    class Boom(PipelineStage):
        name = "boom"

        async def execute(self, job):
            raise RuntimeError("fail")

    job = make_job(text=TEXT, status=JobStatus.PENDING)
    job.post_job = flow.initial_state(False, True)
    await store.save(job)
    orchestrator = PipelineOrchestrator(store, stages=[Boom()])
    # Stage failures are tolerated (job completes); force a hard failure instead.
    orchestrator.stages = None  # type: ignore[assignment]
    await orchestrator.run(job)
    await flow.drain()
    stored = await store.load(job.id)
    assert stored.status == JobStatus.FAILED
    assert insights.requests == []
    # Failed pipeline jobs get no review and no push.
    assert stored.post_job.review_status == "not_required"
    assert stored.post_job.push_status == "not_requested"


async def test_legacy_job_without_post_job_loads(client, store, insights):
    job = make_job(text=TEXT)
    job.result.propositions = [_proposition(s) for s in SENTENCES]
    raw = json.loads(job.model_dump_json())
    assert "post_job" not in raw  # unset field is not serialized
    (store.base_dir / f"{job.id}.json").write_text(json.dumps(raw))

    loaded = await store.load(job.id)
    assert loaded.post_job is None
    payload = (await client.get(f"/enrich/{job.id}/post-job")).json()
    assert payload["legacy"] is True
    assert payload["post_job"]["review_status"] == "not_required"
    assert payload["post_job"]["push_status"] == "not_requested"
    assert "post_job" not in (await client.get(f"/enrich/{job.id}")).json()

    # A legacy job can still be pushed on request (PATCH; the retry route is retry-only).
    assert (await client.post(f"/enrich/{job.id}/insights-push")).status_code == 409
    requested = await client.patch(f"/enrich/{job.id}/post-job", json={"push_to_insights": True})
    assert requested.status_code == 200
    assert requested.json()["legacy"] is False
    await flow.drain()
    payload = (await client.get(f"/enrich/{job.id}/post-job")).json()
    assert payload["post_job"]["push_status"] == "pushed"


# ── Client ───────────────────────────────────────────────────────────────


async def test_push_record_protocol_and_network_errors(monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", BASE)
    monkeypatch.setattr(settings, "insights_api_token", TOKEN)
    monkeypatch.setattr(settings, "insights_corpus", "")
    monkeypatch.setattr(settings, "insights_framework_id", "")

    seen: list[httpx.Request] = []

    def bad_shape(request):
        seen.append(request)
        return httpx.Response(200, json={"created": "two"})

    result = await insights_client.push_record({"propositions": []}, transport=httpx.MockTransport(bad_shape))
    assert result.state == "failed"
    assert result.message == "folio-insights returned an unexpected response."
    assert dict(seen[0].url.params) == {}  # empty corpus/framework are omitted

    def down(request):
        raise httpx.ConnectError("no route", request=request)

    result = await insights_client.push_record({}, transport=httpx.MockTransport(down))
    assert result.state == "failed"
    assert result.message == "folio-insights could not be reached."

    monkeypatch.setattr(settings, "insights_api_url", "ftp://nope")
    result = await insights_client.push_record({})
    assert result.state == "failed"
    monkeypatch.setattr(settings, "insights_api_url", "")
    result = await insights_client.push_record({})
    assert result.state == "not_configured"
