"""Route tests for /enrich/{job_id}/insights-status and /insights/health."""

from __future__ import annotations

import asyncio
import json
import uuid
from functools import partial

import httpx
import pytest
from app.api.routes import enrich as enrich_mod
from app.config import settings
from app.main import app
from app.services import insights_client
from app.services.proposition.source import job_source_uri
from app.storage.job_store import JobStore
from fastapi.testclient import TestClient
from folio_propositions import ActorRef, Disposition, Proposition, content_iri

from tests.helpers import make_job

TOKEN = "tok-route-secret-abcdef"
BASE = "http://insights-private.internal:9123"


def iri(n: int) -> str:
    return f"urn:folio:shard/{n:032x}"


def proposition(pid: str, text: str, content_iri: str | None) -> Proposition:
    return Proposition(
        id=pid,
        start_char=0,
        end_char=len(text),
        text=text,
        proposition_type="Judicial Legal Conclusion",
        asserter=ActorRef(role="court"),
        validator=None,
        disposition=Disposition.ACCEPTED,
        content_iri=content_iri,
    )


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = JobStore(base_dir=tmp_path / "jobs")
    monkeypatch.setattr(enrich_mod, "_job_store", store)
    return store


@pytest.fixture
def http():
    return TestClient(app)


def save_job(store, propositions):
    job = make_job(text="We hold that the rule applies. The court denied the motion.")
    job.result.propositions = propositions
    asyncio.run(store.save(job))
    return job


def iri_for(job, text: str) -> str:
    """The IRI the route derives: same recipe as the export/push stamping."""
    return content_iri(job_source_uri(job), text)


def install_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(insights_client, "fetch_status", partial(insights_client.fetch_status, transport=transport))
    monkeypatch.setattr(insights_client, "fetch_health", partial(insights_client.fetch_health, transport=transport))


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", BASE)
    monkeypatch.setattr(settings, "insights_corpus", "")
    monkeypatch.setattr(settings, "insights_api_token", TOKEN)


def status_handler(present: set[str], seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok", "corpus": "default", "shards": 3})
        body = json.loads(request.content)
        if seen is not None:
            seen.append((request, body))
        results = []
        for value in body["iris"]:
            if value in present:
                results.append({"iri": value, "present": True, "shard_type": "hypothesis",
                                "epistemic_status": "hypothesis", "contested": True,
                                "supersedes": None, "superseded_by": iri(99),
                                "related": [{"iri": iri(50), "relation": "elaborates"}],
                                "contesting": [{"iri": iri(51), "relation": "contests"}],
                                "enrich_sources": []})
            else:
                results.append({"iri": value, "present": False})
        return httpx.Response(200, json={"corpus": "default", "insights_version": "0.1.0", "results": results})

    return handler


def test_unknown_job_is_404(http, store, configured):
    response = http.get(f"/enrich/{uuid.uuid4()}/insights-status")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_invalid_job_id_is_422(http, store):
    assert http.get("/enrich/not-a-uuid/insights-status").status_code == 422


def test_not_configured(http, store, monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "")
    job = save_job(store, [proposition("p1", "the rule applies", None)])
    body = http.get(f"/enrich/{job.id}/insights-status").json()
    assert body["connected"] is False
    assert body["state"] == "not_configured"
    assert body["results"] == {}
    assert body["propositions"] == {"p1": iri_for(job, "the rule applies")}


def test_connected_present_absent_dedupe(http, store, configured, monkeypatch):
    seen: list = []
    job = save_job(store, [
        proposition("p1", "the rule applies", None),
        proposition("p2", "the court denied the motion", None),
        proposition("p3", "the rule applies", None),
    ])
    a, b = iri_for(job, "the rule applies"), iri_for(job, "the court denied the motion")
    install_transport(monkeypatch, status_handler({a}, seen))
    response = http.get(f"/enrich/{job.id}/insights-status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["state"] == "connected"
    assert body["corpus"] == "default"
    assert set(body["results"]) == {a, b}
    assert body["results"][a]["present"] is True
    assert body["results"][a]["contested"] is True
    assert body["results"][a]["contesting"] == [{"iri": iri(51), "relation": "contests"}]
    assert body["results"][b]["present"] is False
    # Three propositions, two distinct IRIs: the map counts propositions.
    assert body["propositions"] == {"p1": a, "p2": b, "p3": a}
    assert len(seen) == 1
    assert seen[0][1]["iris"] == [a, b]
    # Bearer header goes upstream; neither token nor private URL reaches the browser.
    assert seen[0][0].headers["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in response.text
    assert "insights-private.internal" not in response.text


def test_iris_are_restamped_from_job_source(http, store, configured, monkeypatch):
    """Legacy (None) and stale stored IRIs both resolve to the export/push IRI."""
    seen: list = []
    install_transport(monkeypatch, status_handler(set(), seen))
    job = save_job(store, [proposition("p1", "the rule applies", None), proposition("p2", "x", iri(2))])
    body = http.get(f"/enrich/{job.id}/insights-status").json()
    assert body["connected"] is True
    assert body["propositions"] == {"p1": iri_for(job, "the rule applies"), "p2": iri_for(job, "x")}
    assert seen[0][1]["iris"] == [iri_for(job, "the rule applies"), iri_for(job, "x")]


def test_job_without_propositions_reports_health_state(http, store, configured, monkeypatch):
    paths: list[str] = []

    def handler(request):
        paths.append(request.url.path)
        assert request.url.path.endswith("/health"), "no status lookup expected"
        return httpx.Response(200, json={"status": "ok", "corpus": "default", "shards": 3})

    install_transport(monkeypatch, handler)
    job = save_job(store, [])
    body = http.get(f"/enrich/{job.id}/insights-status").json()
    assert body["state"] == "connected"
    assert body["results"] == {}
    assert paths == ["/api/bridge/v1/health"]


def test_job_without_propositions_unreachable(http, store, configured, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    install_transport(monkeypatch, handler)
    job = save_job(store, [])
    body = http.get(f"/enrich/{job.id}/insights-status").json()
    assert body["state"] == "unreachable"
    assert body["connected"] is False


def test_unreachable(http, store, configured, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    install_transport(monkeypatch, handler)
    job = save_job(store, [proposition("p1", "the rule applies", None)])
    response = http.get(f"/enrich/{job.id}/insights-status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["state"] == "unreachable"
    assert body["results"] == {}
    assert "insights-private.internal" not in response.text


def test_server_error(http, store, configured, monkeypatch):
    install_transport(monkeypatch, lambda r: httpx.Response(503))
    job = save_job(store, [proposition("p1", "the rule applies", None)])
    body = http.get(f"/enrich/{job.id}/insights-status").json()
    assert body["state"] == "error"
    assert body["connected"] is False
    assert "503" in body["message"]


def test_health_connected(http, configured, monkeypatch):
    install_transport(monkeypatch, status_handler(set()))
    response = http.get("/insights/health")
    assert response.status_code == 200
    body = response.json()
    # Public route: connection state and a generic message only.
    assert body == {"connected": True, "state": "connected", "message": "folio-insights is connected."}
    assert TOKEN not in response.text
    assert "default" not in response.text and "shards" not in response.text


def test_health_error_is_generic(http, configured, monkeypatch):
    install_transport(monkeypatch, lambda r: httpx.Response(404))
    body = http.get("/insights/health").json()
    assert body == {"connected": False, "state": "error", "message": "folio-insights is unavailable."}


def test_health_not_configured(http, monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "")
    body = http.get("/insights/health").json()
    assert body["state"] == "not_configured"
    assert body["connected"] is False


def test_router_is_mounted():
    paths = {route.path for route in app.routes}
    assert "/enrich/{job_id}/insights-status" in paths
    assert "/insights/health" in paths
