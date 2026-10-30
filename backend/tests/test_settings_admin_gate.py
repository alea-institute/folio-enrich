"""PUT /settings is admin-only for every server-wide field.

The settings singleton is shared by every visitor, so an anonymous caller on a
public deploy must not be able to re-route document text (default or per-task
LLM provider/model, Ollama tiers) or flip any other global switch. The gate is
``require_admin_fail_closed``: a public deploy without an admin token refuses,
a local install without one stays open, and a configured token must match.
"""
from __future__ import annotations

import pytest

from app.config import settings

ADMIN = "s3cret-admin"

# One representative value per field class in SettingsUpdate.
FIELD_CASES = [
    {"llm_provider": "ollama"},
    {"llm_model": "attacker-model"},
    {"llm_concept_provider": "custom"},
    {"llm_individual_provider": "ollama", "llm_individual_model": "m"},
    {"ollama_auto_manage": True},
    {"ollama_model_complex": "attacker:latest"},
    {"folio_auto_update": True},
    {"folio_update_check_interval_hours": 1},
    {"translation_matching_enabled": True},
    {"proposition_extraction_enabled": True},
    {"post_job_review_default": True},
    {"post_job_push_default": True},
    {"google_api_key": "attacker-key"},
]

_ALL_FIELDS = sorted({k for case in FIELD_CASES for k in case})


@pytest.fixture
def snapshot_settings():
    saved = {k: getattr(settings, k) for k in _ALL_FIELDS}
    saved["require_user_api_key"] = settings.require_user_api_key
    saved["admin_token"] = settings.admin_token
    try:
        yield saved
    finally:
        for k, v in saved.items():
            setattr(settings, k, v)


def _current() -> dict:
    return {k: getattr(settings, k) for k in _ALL_FIELDS}


@pytest.mark.parametrize("admin_token", [ADMIN, ""])
@pytest.mark.parametrize("payload", FIELD_CASES, ids=lambda p: ",".join(p))
async def test_public_anonymous_put_refused_and_unchanged(client, snapshot_settings, payload, admin_token):
    settings.require_user_api_key = True
    settings.admin_token = admin_token
    before = _current()
    resp = await client.put("/settings", json=payload)
    assert resp.status_code == 403
    assert _current() == before


async def test_public_wrong_token_refused(client, snapshot_settings):
    settings.require_user_api_key = True
    settings.admin_token = ADMIN
    before = _current()
    resp = await client.put("/settings", json={"llm_provider": "ollama"}, headers={"X-Admin-Token": "nope"})
    assert resp.status_code == 403
    assert _current() == before


async def test_refused_mixed_request_applies_nothing(client, snapshot_settings):
    """No partial application: harmless fields in a refused request stay put."""
    settings.require_user_api_key = True
    settings.admin_token = ADMIN
    before = _current()
    resp = await client.put("/settings", json={
        "translation_matching_enabled": not settings.translation_matching_enabled,
        "llm_concept_provider": "custom",
    })
    assert resp.status_code == 403
    assert _current() == before


async def test_public_admin_put_allowed(client, snapshot_settings):
    settings.require_user_api_key = True
    settings.admin_token = ADMIN
    settings.google_api_key = "server-key"
    resp = await client.put(
        "/settings",
        json={"llm_concept_provider": "groq", "ollama_model_complex": "q:14b", "google_api_key": "new"},
        headers={"X-Admin-Token": ADMIN},
    )
    assert resp.status_code == 200
    assert settings.llm_concept_provider == "groq"
    assert settings.ollama_model_complex == "q:14b"
    # BYOK: a server key is never stored, even by an admin.
    assert settings.google_api_key == "server-key"


async def test_local_without_token_stays_open(client, snapshot_settings):
    settings.require_user_api_key = False
    settings.admin_token = ""
    resp = await client.put("/settings", json={"llm_model": "local-model", "google_api_key": "k"})
    assert resp.status_code == 200
    assert settings.llm_model == "local-model"
    assert settings.google_api_key == "k"


async def test_local_with_token_requires_it(client, snapshot_settings):
    settings.require_user_api_key = False
    settings.admin_token = ADMIN
    before = _current()
    assert (await client.put("/settings", json={"llm_model": "x"})).status_code == 403
    assert _current() == before
    ok = await client.put("/settings", json={"llm_model": "x"}, headers={"X-Admin-Token": ADMIN})
    assert ok.status_code == 200
    assert settings.llm_model == "x"


async def test_empty_put_is_a_noop_without_token(client, snapshot_settings):
    settings.require_user_api_key = True
    settings.admin_token = ADMIN
    assert (await client.put("/settings", json={})).status_code == 200


async def test_reviewer_probe_cannot_reroute_task_llms(client, snapshot_settings, monkeypatch):
    """Regression for the review probe: an anonymous PUT on a public deploy
    re-pointed per-task providers, which beat the request's own provider."""
    settings.require_user_api_key = True
    settings.admin_token = ADMIN
    for task in ("individual", "concept"):
        monkeypatch.setattr(settings, f"llm_{task}_provider", "")
        monkeypatch.setattr(settings, f"llm_{task}_model", "")
    resp = await client.put("/settings", json={
        "llm_individual_provider": "ollama", "llm_concept_provider": "custom", "llm_provider": "ollama",
    })
    assert resp.status_code == 403
    assert settings.llm_individual_provider == ""
    assert settings.llm_concept_provider == ""
    from app.pipeline.orchestrator import TaskLLMs

    fallback = object()
    task_llms = TaskLLMs.from_settings(fallback=fallback, provider="openai", model="gpt-4o")
    assert task_llms.concept is fallback
    assert task_llms.individual is fallback
