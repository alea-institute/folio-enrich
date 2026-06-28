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
