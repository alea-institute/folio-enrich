"""Ollama tiering must follow the request's effective provider.

Server settings llm_provider=ollama with an empty llm_model turn on tier mode.
A request naming a non-Ollama provider without a key gets no fallback LLM
(None); tiering used to treat that None as "Ollama" and route every task to
Ollama tier models the caller never asked for.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import enrich as enrich_mod
from app.config import settings
from app.main import app
from app.pipeline.orchestrator import LLM_TASKS, TaskLLMs, _TASK_FIELD_MAP
from app.storage.job_store import JobStore


def _fields():
    return [_TASK_FIELD_MAP.get(t, t) for t in LLM_TASKS]


@pytest.fixture
def ollama_tier_settings(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "require_user_api_key", True)  # no server-key fallback
    for task in LLM_TASKS:
        monkeypatch.setattr(settings, f"llm_{task}_provider", "", raising=False)
        monkeypatch.setattr(settings, f"llm_{task}_model", "", raising=False)
    return settings


@pytest.mark.parametrize("provider", ["anthropic", "openai", "google"])
def test_keyless_non_ollama_request_gets_no_tier_models(ollama_tier_settings, provider):
    task_llms = TaskLLMs.from_settings(fallback=None, provider=provider, model="")
    assert all(getattr(task_llms, f) is None for f in _fields())


@pytest.mark.parametrize("provider", ["ollama", "Ollama"])
def test_ollama_request_without_fallback_still_tiers(ollama_tier_settings, provider):
    task_llms = TaskLLMs.from_settings(fallback=None, provider=provider, model="")
    s = ollama_tier_settings
    assert task_llms.document_type.model == s.ollama_model_simple
    assert task_llms.concept.model == s.ollama_model_medium
    assert task_llms.classifier.model == s.ollama_model_complex


def test_ollama_request_with_explicit_model_is_not_retiered(ollama_tier_settings):
    from app.services.llm.registry import get_provider

    fallback = get_provider("ollama", model="llama3:70b")
    task_llms = TaskLLMs.from_settings(fallback=fallback, provider="ollama", model="llama3:70b")
    assert all(getattr(task_llms, f) is fallback for f in _fields())


def test_enrich_route_passes_request_provider(ollama_tier_settings, tmp_path, monkeypatch):
    """End to end through POST /enrich: an Anthropic request with no key must
    build an orchestrator with no LLMs, not Ollama tier models."""
    monkeypatch.setattr(enrich_mod, "_job_store", JobStore(base_dir=tmp_path / "jobs"))
    captured = {}

    class _CapturingOrchestrator:
        def __init__(self, job_store, llm=None, task_llms=None):
            captured["llm"], captured["task_llms"] = llm, task_llms

        async def run(self, job):
            return job

    monkeypatch.setattr(enrich_mod, "PipelineOrchestrator", _CapturingOrchestrator)
    with TestClient(app) as client:
        r = client.post("/enrich", json={
            "content": "The tenant shall pay rent.", "format": "plain_text",
            "llm_provider": "anthropic",
        })
    assert r.status_code == 202, r.text
    assert captured["llm"] is None
    assert all(getattr(captured["task_llms"], f) is None for f in _fields())
