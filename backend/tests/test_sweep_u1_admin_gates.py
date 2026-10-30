"""U1: privileged Ollama and feedback routes require the admin token.

Public posture (``require_user_api_key``) rejects missing/wrong tokens and fails
closed when no admin token is configured; local posture stays open.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import feedback as feedback_routes
from app.config import settings
from app.main import app
from app.services.ollama.manager import OllamaInfo, OllamaManager, OllamaStatus

client = TestClient(app)

GATED = [
    ("post", "/ollama/setup", None),
    ("post", "/ollama/start", None),
    ("post", "/ollama/stop", None),
    ("post", "/ollama/pull", {"model": "qwen3:4b"}),
    ("delete", "/feedback", None),
    ("delete", "/feedback/some-id", None),
    ("get", "/feedback/export?format=json", None),
]


async def _no_pull(self, model):
    if False:
        yield None


@pytest.fixture(autouse=True)
def _mocks(monkeypatch):
    """Nothing installs, starts, pulls or touches the real feedback store."""
    OllamaManager.reset_instance()
    running = OllamaInfo(status=OllamaStatus.RUNNING, base_url="http://localhost:11434", models=[])
    install = AsyncMock(side_effect=AssertionError("install must never run in tests"))
    store = feedback_routes._feedback_store
    with patch.object(OllamaManager, "detect", new_callable=AsyncMock, return_value=running), \
         patch.object(OllamaManager, "install", install), \
         patch.object(OllamaManager, "start", new_callable=AsyncMock, return_value=True), \
         patch.object(OllamaManager, "stop", new_callable=AsyncMock), \
         patch.object(OllamaManager, "get_required_models", return_value=set()), \
         patch.object(OllamaManager, "pull_model", _no_pull), \
         patch.object(store, "delete_all", new_callable=AsyncMock, return_value=0), \
         patch.object(store, "delete", new_callable=AsyncMock, return_value=True), \
         patch.object(store, "list_all", new_callable=AsyncMock, return_value=[]):
        yield
    OllamaManager.reset_instance()


def _call(method, path, body, headers=None):
    kwargs = {"headers": headers or {}}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(path, **kwargs)


def _public(monkeypatch, token):
    monkeypatch.setattr(settings, "require_user_api_key", True)
    monkeypatch.setattr(settings, "admin_token", token)


@pytest.mark.parametrize("method,path,body", GATED)
class TestPublicPosture:
    def test_missing_token_rejected(self, monkeypatch, method, path, body):
        _public(monkeypatch, "s3cret")
        assert _call(method, path, body).status_code == 403

    def test_wrong_token_rejected(self, monkeypatch, method, path, body):
        _public(monkeypatch, "s3cret")
        r = _call(method, path, body, {"X-Admin-Token": "wrong"})
        assert r.status_code == 403

    def test_correct_token_accepted(self, monkeypatch, method, path, body):
        _public(monkeypatch, "s3cret")
        r = _call(method, path, body, {"X-Admin-Token": "s3cret"})
        assert r.status_code == 200

    def test_no_token_configured_fails_closed(self, monkeypatch, method, path, body):
        _public(monkeypatch, "")
        assert _call(method, path, body).status_code == 403
        assert _call(method, path, body, {"X-Admin-Token": ""}).status_code == 403
        assert _call(method, path, body, {"X-Admin-Token": "anything"}).status_code == 403


@pytest.mark.parametrize("method,path,body", GATED)
class TestLocalPosture:
    def test_local_without_token_open(self, monkeypatch, method, path, body):
        monkeypatch.setattr(settings, "require_user_api_key", False)
        monkeypatch.setattr(settings, "admin_token", "")
        assert _call(method, path, body).status_code == 200

    def test_local_with_token_still_enforced(self, monkeypatch, method, path, body):
        monkeypatch.setattr(settings, "require_user_api_key", False)
        monkeypatch.setattr(settings, "admin_token", "s3cret")
        assert _call(method, path, body).status_code == 403
        assert _call(method, path, body, {"X-Admin-Token": "s3cret"}).status_code == 200


class TestOpenRoutesStayOpen:
    def test_public_reads_and_feedback_submit_not_admin_gated(self, monkeypatch):
        _public(monkeypatch, "s3cret")
        with patch.object(OllamaManager, "get_system_ram_gb", return_value=8.0), \
             patch.object(OllamaManager, "list_local_models", new_callable=AsyncMock, return_value=[]):
            assert client.get("/ollama/status").status_code == 200
            assert client.get("/ollama/models").status_code == 200
            assert client.get("/ollama/tier-config").status_code == 200
        with patch.object(feedback_routes._feedback_store, "get_insights", new_callable=AsyncMock,
                          return_value=feedback_routes.InsightsSummary()):
            assert client.get("/feedback/insights").status_code == 200
        # Submission stays open: an unknown job is a 404, never an auth error.
        r = client.post("/feedback", json={
            "job_id": "00000000-0000-0000-0000-000000000000",
            "annotation_id": "a", "rating": "up",
        })
        assert r.status_code == 404
