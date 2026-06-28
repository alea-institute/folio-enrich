"""Tests for bring-your-own-key enforcement (FOLIO_ENRICH_REQUIRE_USER_API_KEY).

When enabled, a server-stored API key must never be used to serve requests:
- key resolution ignores the stored key (only an explicit/request key is honored)
- the /settings and /health/detail endpoints report the LLM as unconfigured
This keeps anonymous visitors on public deployments from spending the
operator's key.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.models.llm_models import LLMProviderType
from app.api.routes.settings import _get_api_key_for_provider
from app.api.routes.health import _check_llm


@pytest.fixture
def google_key_configured():
    """Configure a server-side Google key and restore state afterwards."""
    prev_key = settings.google_api_key
    prev_provider = settings.llm_provider
    prev_require = settings.require_user_api_key
    settings.google_api_key = "server-side-secret"
    settings.llm_provider = "google"
    try:
        yield
    finally:
        settings.google_api_key = prev_key
        settings.llm_provider = prev_provider
        settings.require_user_api_key = prev_require


def test_fallback_used_when_not_required(google_key_configured):
    """Default (flag off): the stored server key is used as a fallback."""
    settings.require_user_api_key = False
    assert _get_api_key_for_provider(LLMProviderType.google) == "server-side-secret"


def test_fallback_blocked_when_required(google_key_configured):
    """Flag on: the stored server key is NOT used when no explicit key is given."""
    settings.require_user_api_key = True
    assert _get_api_key_for_provider(LLMProviderType.google) is None


def test_explicit_key_still_honored_when_required(google_key_configured):
    """Flag on: a request-supplied key is still honored (BYOK works)."""
    settings.require_user_api_key = True
    assert (
        _get_api_key_for_provider(LLMProviderType.google, explicit_key="user-key")
        == "user-key"
    )


def test_health_reports_unconfigured_when_required(google_key_configured):
    """Flag on: the LLM health chip reports no_api_key despite a stored key."""
    settings.require_user_api_key = True
    result = _check_llm()
    assert result["status"] == "no_api_key"


def test_health_reports_configured_when_not_required(google_key_configured):
    """Default: the LLM health chip reports configured when a key is stored."""
    settings.require_user_api_key = False
    result = _check_llm()
    assert result["status"] == "configured"


async def test_settings_endpoint_hides_key_when_required(client, google_key_configured):
    """Flag on: /settings reports the stored key as unset."""
    settings.require_user_api_key = True
    resp = await client.get("/settings")
    data = resp.json()
    assert data["require_user_api_key"] is True
    assert data["google_api_key_set"] is False


async def test_providers_endpoint_hides_key_when_required(client, google_key_configured):
    """Flag on: /settings/providers reports the stored key as unset."""
    settings.require_user_api_key = True
    resp = await client.get("/settings/providers")
    data = resp.json()
    assert data["providers"]["google"]["api_key_set"] is False


async def test_put_settings_does_not_persist_key_when_required(client, google_key_configured):
    """Flag on: PUT /settings never writes a server-side key (defense in depth).

    On a public deployment the settings singleton is shared across visitors, so
    storing one user's key there is the very leak BYOK prevents. Non-key fields
    must still update.
    """
    settings.require_user_api_key = True
    settings.google_api_key = "original-server-key"
    resp = await client.put(
        "/settings",
        json={"google_api_key": "attacker-supplied-key", "llm_provider": "anthropic"},
    )
    assert resp.status_code == 200
    assert settings.google_api_key == "original-server-key"  # unchanged
    assert settings.llm_provider == "anthropic"  # non-key field still updates


async def test_put_settings_persists_key_when_not_required(client, google_key_configured):
    """Default (flag off): PUT /settings persists the key as before (regression)."""
    settings.require_user_api_key = False
    resp = await client.put("/settings", json={"google_api_key": "new-stored-key"})
    assert resp.status_code == 200
    assert settings.google_api_key == "new-stored-key"


async def test_synthetic_requires_key_when_required(client, google_key_configured):
    """Flag on, no key: /synthetic returns an actionable 400, not a 500."""
    settings.require_user_api_key = True
    resp = await client.post("/synthetic", json={"doc_type": "Motion to Dismiss"})
    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]


async def test_synthetic_honors_explicit_key_when_required(
    client, google_key_configured, monkeypatch
):
    """Flag on: an explicit (request) key is honored and reaches the provider."""
    settings.require_user_api_key = True
    captured: dict = {}

    def fake_get_provider(provider_type, api_key=None, model=None):
        captured["api_key"] = api_key
        return object()

    async def fake_generate(self, doc_type="", length="", jurisdiction=""):
        return "SYNTHETIC DOC"

    monkeypatch.setattr("app.api.routes.synthetic.get_provider", fake_get_provider)
    monkeypatch.setattr(
        "app.api.routes.synthetic.SyntheticGenerator.generate", fake_generate
    )
    resp = await client.post(
        "/synthetic", json={"doc_type": "Motion to Dismiss", "api_key": "user-key"}
    )
    assert resp.status_code == 200
    assert captured["api_key"] == "user-key"
    assert resp.json()["document"] == "SYNTHETIC DOC"
