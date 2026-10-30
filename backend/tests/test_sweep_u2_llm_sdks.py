"""U2 regression: the openai and anthropic SDKs must be installed dependencies.

Both are imported lazily by the provider classes, so a missing SDK only surfaced at
call time as ModuleNotFoundError (breaking Ollama, OpenAI, Mistral, Groq, LM Studio,
xAI, Llama, GitHub Models and Anthropic). These tests build each client offline with a
fake key and touch the API surfaces the providers call.
"""

from __future__ import annotations

from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.openai_compat import OpenAICompatProvider


def test_openai_compat_client_constructs_offline():
    import openai

    provider = OpenAICompatProvider(api_key="sk-fake", base_url="http://127.0.0.1:9/v1")
    client = provider._get_client()
    assert isinstance(client, openai.AsyncOpenAI)
    assert callable(client.chat.completions.create)
    assert callable(client.models.list)


def test_openai_compat_client_constructs_without_key():
    # Ollama / LM Studio run without a key; the provider substitutes "no-key".
    provider = OpenAICompatProvider(base_url="http://127.0.0.1:9/v1")
    assert provider._get_client() is not None


def test_anthropic_client_constructs_offline():
    import anthropic

    provider = AnthropicProvider(api_key="sk-ant-fake")
    client = provider._get_client()
    assert isinstance(client, anthropic.AsyncAnthropic)
    assert callable(client.messages.create)
    assert callable(client.models.list)


def test_openai_embedding_provider_constructs_offline():
    from app.services.embedding.providers.openai import OpenAIEmbeddingProvider

    # Known model -> no dimension probe, so no network call.
    provider = OpenAIEmbeddingProvider(
        model="text-embedding-3-small", api_key="sk-fake", base_url="http://127.0.0.1:9/v1"
    )
    assert provider._dim == 1536
    assert callable(provider._client.embeddings.create)
