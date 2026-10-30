"""U6 bug sweep: LLM provider structured output, model IDs, settings task list."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.config import settings
from app.models.llm_models import LLMProviderType
from app.services.llm.registry import DEFAULT_BASE_URLS, DEFAULT_MODELS, KNOWN_MODELS

SCHEMA = {
    "type": "object",
    "properties": {"propositions": {"type": "array", "items": {"type": "object"}}},
}


# ── OpenAI-compatible structured() ──────────────────────────────


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _openai_provider(content: str):
    from app.services.llm.openai_compat import OpenAICompatProvider

    provider = OpenAICompatProvider(api_key="k", model="m")
    completions = _FakeCompletions(content)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return provider, completions


async def test_openai_compat_structured_sends_json_instruction_and_schema() -> None:
    provider, completions = _openai_provider('{"propositions": []}')

    result = await provider.structured("Find spans.", schema=SCHEMA)

    assert result == {"propositions": []}
    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    content = call["messages"][0]["content"]
    assert content.startswith("Find spans.")
    assert "JSON" in content
    assert '"propositions"' in content
    assert '"type": "array"' in content


async def test_openai_compat_structured_tolerates_fences_and_trailing_text() -> None:
    provider, _ = _openai_provider('```json\n{"propositions": [1]}\n```')
    assert await provider.structured("p", schema=SCHEMA) == {"propositions": [1]}

    provider, _ = _openai_provider('{"propositions": [2]}\nHope this helps!')
    assert await provider.structured("p", schema=SCHEMA) == {"propositions": [2]}


# ── Anthropic ───────────────────────────────────────────────────


class _FakeMessages:
    def __init__(self, blocks: list) -> None:
        self.blocks = blocks
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=self.blocks)


def _anthropic_provider(blocks: list):
    from app.services.llm.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider(api_key="k", model="claude-sonnet-4-6")
    messages = _FakeMessages(blocks)
    provider._client = SimpleNamespace(messages=messages)
    return provider, messages


async def test_anthropic_structured_tolerates_prose_around_json() -> None:
    provider, messages = _anthropic_provider(
        [SimpleNamespace(type="text", text='Here you go:\n{"propositions": []}\nDone.')]
    )
    assert await provider.structured("p", schema=SCHEMA) == {"propositions": []}
    sent = messages.calls[0]["messages"][0]["content"]
    assert "JSON" in sent and '"propositions"' in sent


async def test_anthropic_default_max_tokens_raised_and_overridable() -> None:
    provider, messages = _anthropic_provider([SimpleNamespace(type="text", text="ok")])
    await provider.complete("hi")
    assert messages.calls[0]["max_tokens"] == 8192
    await provider.complete("hi", max_tokens=100)
    assert messages.calls[1]["max_tokens"] == 100


async def test_anthropic_skips_thinking_blocks() -> None:
    provider, _ = _anthropic_provider([
        SimpleNamespace(type="thinking", thinking="hmm", signature="s"),
        SimpleNamespace(type="text", text='{"propositions": [3]}'),
    ])
    assert await provider.structured("p", schema=SCHEMA) == {"propositions": [3]}


def test_anthropic_client_honors_base_url(monkeypatch) -> None:
    from app.services.llm.anthropic_provider import AnthropicProvider

    seen: list[dict] = []
    fake_sdk = types.ModuleType("anthropic")
    fake_sdk.AsyncAnthropic = lambda **kwargs: seen.append(kwargs) or object()
    monkeypatch.setitem(sys.modules, "anthropic", fake_sdk)

    AnthropicProvider(api_key="k", base_url="https://proxy.example.com")._get_client()
    AnthropicProvider(api_key="k")._get_client()

    assert seen[0] == {"api_key": "k", "base_url": "https://proxy.example.com"}
    assert seen[1] == {"api_key": "k"}


# ── Cohere ──────────────────────────────────────────────────────


async def test_cohere_structured_tolerates_trailing_text(monkeypatch) -> None:
    from app.services.llm.cohere_provider import CohereProvider

    provider = CohereProvider(api_key="k", model="command-a-03-2025")
    prompts: list[str] = []

    async def fake_complete(prompt: str, **kwargs) -> str:
        prompts.append(prompt)
        return '{"propositions": []} trailing words'

    monkeypatch.setattr(provider, "complete", fake_complete)
    assert await provider.structured("p", schema=SCHEMA) == {"propositions": []}
    assert "JSON" in prompts[0]


# ── Google default model fallback ───────────────────────────────


async def test_google_without_model_uses_registry_default(monkeypatch) -> None:
    from app.services.llm.google_provider import GoogleProvider

    provider = GoogleProvider(api_key="k", model=None)
    urls: list[str] = []

    async def fake_post(url, body, max_retries=5):
        urls.append(url)
        return {"candidates": [{"content": {"parts": [{"text": '{"a": 1} extra'}]}}]}

    monkeypatch.setattr(provider, "_post_with_retry", fake_post)
    assert await provider.structured("p", schema=SCHEMA) == {"a": 1}
    await provider.complete("p")

    expected = f"/models/{DEFAULT_MODELS[LLMProviderType.google]}:generateContent"
    assert all(url.endswith(expected) for url in urls)
    assert not any("gemini-2.0-flash" in url for url in urls)


# ── Registry model IDs ──────────────────────────────────────────

_RETIRED_IDS = {
    "gemini-2.0-flash", "gemini-3-pro-preview", "gemini-3.5-flash",
    "grok-3", "grok-3-mini", "grok-4-0709",
    "gpt-4.1-nano", "o3-mini", "o4-mini",
    "claude-sonnet-4-5-20250929",
    "llama-4-scout", "llama-4-maverick", "llama-3.3-70b-instruct",
}


def test_no_retired_model_ids_in_registry() -> None:
    from app.services.llm.anthropic_provider import _FALLBACK_MODELS

    listed = {m.id for models in KNOWN_MODELS.values() for m in models}
    listed |= {m.id for m in _FALLBACK_MODELS}
    listed |= set(DEFAULT_MODELS.values())
    assert not (listed & _RETIRED_IDS)


def test_cloud_defaults_are_listed_models() -> None:
    # PROD pins only the provider, so each cloud default must resolve to a
    # model that the provider's known list (and so the dropdown) carries.
    for provider in (
        LLMProviderType.google, LLMProviderType.xai, LLMProviderType.meta_llama,
        LLMProviderType.openai, LLMProviderType.anthropic,
    ):
        assert DEFAULT_MODELS[provider], provider
        assert DEFAULT_MODELS[provider] in {m.id for m in KNOWN_MODELS[provider]}, provider
    assert type(settings).model_fields["llm_model"].default == ""


def test_meta_base_url_points_at_model_api() -> None:
    assert DEFAULT_BASE_URLS[LLMProviderType.meta_llama] == "https://api.meta.ai/v1"


# ── Proposition prompt ──────────────────────────────────────────


async def test_proposition_prompt_requests_json_with_propositions_key(monkeypatch) -> None:
    from app.models.document import DocumentInput
    from app.models.job import Job
    from app.pipeline.stages.ingestion_stage import IngestionStage
    from app.pipeline.stages.normalization_stage import NormalizationStage
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    class CaptureLLM:
        model = "capture"
        prompts: list[str] = []

        async def structured(self, prompt: str, schema: dict, **kwargs) -> dict:
            self.prompts.append(prompt)
            return {"propositions": []}

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    job = Job(
        id=UUID("b415b8ef-bff3-5b0b-a06a-e379bf128c36"),
        input=DocumentInput(content="The statute requires notice."),
    )
    job = await NormalizationStage().execute(await IngestionStage().execute(job))
    llm = CaptureLLM()
    await EarlyPropositionStage(llm=llm).execute(job)

    prompt = llm.prompts[0]
    assert "JSON" in prompt
    assert '"propositions"' in prompt


# ── GET /settings task overrides ────────────────────────────────


async def test_get_settings_exposes_every_llm_task_override(client, monkeypatch) -> None:
    from app.pipeline.orchestrator import LLM_TASKS

    for task in LLM_TASKS:
        monkeypatch.setattr(settings, f"llm_{task}_provider", "groq")
        monkeypatch.setattr(settings, f"llm_{task}_model", f"model-{task}")

    response = await client.get("/settings")
    assert response.status_code == 200
    overrides = response.json()["task_llm_overrides"]
    assert set(overrides) == set(LLM_TASKS)
    assert overrides["property"] == {"provider": "groq", "model": "model-property"}


async def test_put_settings_accepts_new_task_overrides(client, monkeypatch) -> None:
    for task in ("individual", "property", "document_type"):
        monkeypatch.setattr(settings, f"llm_{task}_provider", "")
        monkeypatch.setattr(settings, f"llm_{task}_model", "")

    response = await client.put("/settings", json={
        "llm_individual_model": "m-ind",
        "llm_property_provider": "xai",
        "llm_document_type_model": "m-doc",
    })
    assert response.status_code == 200
    assert settings.llm_individual_model == "m-ind"
    assert settings.llm_property_provider == "xai"
    assert settings.llm_document_type_model == "m-doc"
