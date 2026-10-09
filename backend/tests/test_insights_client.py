"""Unit tests for the folio-insights bridge client (no network)."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from app.config import settings
from app.services import insights_client
from app.services.insights_client import (
    MAX_IRIS_PER_REQUEST,
    fetch_health,
    fetch_status,
)

BASE = "http://insights.test"
TOKEN = "tok-secret-1234567890"


def iri(n: int) -> str:
    return f"urn:folio:shard/{n:032x}"


def present_result(value: str, **extra) -> dict:
    result = {
        "iri": value,
        "present": True,
        "shard_type": "hypothesis",
        "epistemic_status": "hypothesis",
        "contested": False,
        "supersedes": None,
        "superseded_by": None,
        "related": [{"iri": iri(900), "relation": "elaborates"}],
        "contesting": [],
        "enrich_sources": [{"document_id": "doc-1", "proposition_id": "p-1", "proposition_type": "Legal Proposition"}],
    }
    result.update(extra)
    return result


def absent_result(value: str) -> dict:
    return {"iri": value, "present": False, "shard_type": None, "epistemic_status": None,
            "contested": False, "supersedes": None, "superseded_by": None,
            "related": [], "contesting": [], "enrich_sources": []}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", BASE + "/")
    monkeypatch.setattr(settings, "insights_corpus", "")
    monkeypatch.setattr(settings, "insights_api_token", "")
    monkeypatch.setattr(settings, "insights_timeout_seconds", 3.0)


def status_transport(present: set[str], calls: list[httpx.Request] | None = None, corpus: str = "default"):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        assert request.url.path == "/api/bridge/v1/status"
        body = json.loads(request.content)
        assert len(body["iris"]) <= MAX_IRIS_PER_REQUEST
        results = [present_result(v) if v in present else absent_result(v) for v in body["iris"]]
        return httpx.Response(200, json={"corpus": corpus, "insights_version": "0.1.0", "results": results})

    return httpx.MockTransport(handler)


async def test_not_configured_makes_no_request(monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "")

    def explode(request):  # pragma: no cover - must not be called
        raise AssertionError("no request expected")

    status = await fetch_status([iri(1)], transport=httpx.MockTransport(explode))
    assert status.state == "not_configured"
    assert status.connected is False
    assert status.results == {}


async def test_invalid_scheme_is_error(monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "file:///etc/passwd")
    status = await fetch_status([iri(1)])
    assert status.state == "error"
    assert "file" not in (status.message or "")


async def test_connected_present_and_absent(configured):
    calls: list[httpx.Request] = []
    status = await fetch_status([iri(1), iri(2), iri(1)], transport=status_transport({iri(1)}, calls))
    assert status.state == "connected"
    assert status.connected
    assert status.corpus == "default"
    assert status.insights_version == "0.1.0"
    assert len(calls) == 1
    sent = json.loads(calls[0].content)
    assert sent == {"iris": [iri(1), iri(2)], "corpus": None}
    assert status.results[iri(1)]["present"] is True
    assert status.results[iri(1)]["epistemic_status"] == "hypothesis"
    assert status.results[iri(1)]["related"] == [{"iri": iri(900), "relation": "elaborates"}]
    assert status.results[iri(2)]["present"] is False
    assert status.results[iri(2)]["related"] == []


async def test_configured_corpus_is_sent(configured, monkeypatch):
    monkeypatch.setattr(settings, "insights_corpus", "palsgraf")
    calls: list[httpx.Request] = []
    status = await fetch_status([iri(1)], transport=status_transport(set(), calls, corpus="palsgraf"))
    assert json.loads(calls[0].content)["corpus"] == "palsgraf"
    assert status.corpus == "palsgraf"


async def test_unknown_result_fields_are_dropped(configured):
    def handler(request):
        return httpx.Response(200, json={"corpus": "default", "results": [
            present_result(iri(1), internal_path="/srv/secret", contested=True, superseded_by=iri(3)),
        ]})

    status = await fetch_status([iri(1)], transport=httpx.MockTransport(handler))
    result = status.results[iri(1)]
    assert "internal_path" not in result
    assert result["contested"] is True
    assert result["superseded_by"] == iri(3)


async def test_chunks_above_500(configured):
    calls: list[httpx.Request] = []
    iris = [iri(n) for n in range(1, 1203)]
    status = await fetch_status(iris, transport=status_transport({iri(7), iri(1100)}, calls))
    assert status.connected
    assert [len(json.loads(c.content)["iris"]) for c in calls] == [500, 500, 202]
    assert len(status.results) == 1202
    assert status.results[iri(1100)]["present"] is True


async def test_empty_iri_list_uses_health_check(configured):
    paths: list[str] = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"status": "ok", "corpus": "default", "shards": 0})

    status = await fetch_status([], transport=httpx.MockTransport(handler))
    assert status.state == "connected"
    assert status.corpus == "default"
    assert status.results == {}
    assert paths == ["/api/bridge/v1/health"]


async def test_empty_iri_list_reports_unreachable(configured):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    status = await fetch_status([], transport=httpx.MockTransport(handler))
    assert status.state == "unreachable"
    assert status.connected is False


@pytest.mark.parametrize("exc", [
    lambda r: httpx.DecodingError("bad gzip", request=r),
    lambda r: httpx.TooManyRedirects("loop", request=r),
    lambda r: httpx.InvalidURL("http://insights.test/bad"),
    lambda r: httpx.StreamConsumed(),
])
async def test_other_httpx_errors_are_error_state(configured, exc, caplog):
    def handler(request):
        raise exc(request)

    with caplog.at_level(logging.DEBUG):
        status = await fetch_status([iri(1)], transport=httpx.MockTransport(handler))
        health = await fetch_health(transport=httpx.MockTransport(handler))
    assert status.state == "error" and health.state == "error"
    for message in (status.message, health.message):
        assert "insights.test" not in message
    assert "insights.test/bad" not in caplog.text


@pytest.mark.parametrize("url", ["http://[::1", "http://host:99999", "https://", "ftp://insights.test"])
async def test_malformed_base_urls_never_raise(monkeypatch, url):
    monkeypatch.setattr(settings, "insights_api_url", url)
    status = await fetch_status([iri(1)])
    assert status.state == "error"
    assert url not in status.message


async def test_connect_error_is_unreachable(configured, caplog):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    with caplog.at_level(logging.INFO):
        status = await fetch_status([iri(1)], transport=httpx.MockTransport(handler))
    assert status.state == "unreachable"
    assert status.connected is False
    assert "insights.test" not in (status.message or "")
    assert "insights.test" not in caplog.text


async def test_timeout_is_unreachable(configured):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    status = await fetch_status([iri(1)], transport=httpx.MockTransport(handler))
    assert status.state == "unreachable"


@pytest.mark.parametrize("code", [500, 502, 503])
async def test_5xx_is_error(configured, code):
    status = await fetch_status([iri(1)], transport=httpx.MockTransport(lambda r: httpx.Response(code, text="boom")))
    assert status.state == "error"
    assert status.status_code == code
    assert str(code) in status.message


async def test_404_unknown_corpus(configured):
    status = await fetch_status([iri(1)], transport=httpx.MockTransport(lambda r: httpx.Response(404, json={"detail": "x"})))
    assert status.state == "error"
    assert status.status_code == 404
    assert "corpus" in status.message


async def test_malformed_payload_is_error(configured):
    status = await fetch_status([iri(1)], transport=httpx.MockTransport(lambda r: httpx.Response(200, text="not json")))
    assert status.state == "error"
    status = await fetch_status([iri(1)], transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": [{"present": True}]})))
    assert status.state == "error"


async def test_token_sent_as_bearer_and_never_echoed(configured, monkeypatch, caplog):
    monkeypatch.setattr(settings, "insights_api_token", TOKEN)
    calls: list[httpx.Request] = []
    with caplog.at_level(logging.DEBUG):
        status = await fetch_status([iri(1)], transport=status_transport(set(), calls))
        failed = await fetch_status([iri(1)], transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    assert calls[0].headers["Authorization"] == f"Bearer {TOKEN}"
    for value in (status, failed):
        assert TOKEN not in repr(value)
    assert TOKEN not in caplog.text


async def test_no_token_means_no_authorization_header(configured):
    calls: list[httpx.Request] = []
    await fetch_status([iri(1)], transport=status_transport(set(), calls))
    assert "Authorization" not in calls[0].headers


async def test_health_connected(configured, monkeypatch):
    monkeypatch.setattr(settings, "insights_api_token", TOKEN)
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.path == "/api/bridge/v1/health"
        return httpx.Response(200, json={"status": "ok", "corpus": "default", "shards": 42})

    health = await fetch_health(transport=httpx.MockTransport(handler))
    assert health.state == "connected"
    assert health.shards == 42
    assert health.corpus == "default"
    assert seen[0].headers["Authorization"] == f"Bearer {TOKEN}"


async def test_health_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "insights_api_url", "  ")
    health = await fetch_health()
    assert health.state == "not_configured"


async def test_health_unreachable(configured):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    health = await fetch_health(transport=httpx.MockTransport(handler))
    assert health.state == "unreachable"


async def test_timeout_setting_is_applied(configured, monkeypatch):
    monkeypatch.setattr(settings, "insights_timeout_seconds", 1.5)
    assert insights_client._timeout().read == 1.5
    monkeypatch.setattr(settings, "insights_timeout_seconds", 0)
    assert insights_client._timeout().read == 3.0
