from __future__ import annotations

import logging
from typing import Any

from app.models.llm_models import ModelInfo
from app.services.llm.base import LLMProvider
from app.services.llm.json_utils import parse_json_response, with_schema_instruction

logger = logging.getLogger(__name__)

# Output budget per call. Structured extraction over long documents easily
# overruns 4096 tokens and the truncated JSON then fails to parse. Callers can
# still pass max_tokens explicitly.
DEFAULT_MAX_TOKENS = 8192

# Fallback list used when the models API is unreachable.
# Ordered: oldest/cheapest → newest/most powerful.
_FALLBACK_MODELS: list[ModelInfo] = [
    ModelInfo(id="claude-haiku-4-5-20251001", name="Claude Haiku 4.5", context_window=200000),
    ModelInfo(id="claude-sonnet-4-6", name="Claude Sonnet 4.6", context_window=200000),
    ModelInfo(id="claude-opus-4-6", name="Claude Opus 4.6", context_window=200000),
    ModelInfo(id="claude-opus-4-7", name="Claude Opus 4.7", context_window=200000),
    ModelInfo(id="claude-haiku-5-5", name="Claude Haiku 5.5", context_window=1000000),
    ModelInfo(id="claude-sonnet-5-5", name="Claude Sonnet 5.5", context_window=1000000),
    ModelInfo(id="claude-opus-5-5", name="Claude Opus 5.5", context_window=1000000),
]


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, model=model)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = anthropic.AsyncAnthropic(**kwargs)
        return self._client

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        return await self.chat(
            [{"role": "user", "content": prompt}], **kwargs
        )

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        client = self._get_client()
        max_tokens = kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS)

        # Separate system message from user/assistant messages
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
            else:
                chat_messages.append(msg)

        create_kwargs: dict[str, Any] = {
            "model": kwargs.pop("model", self.model or "claude-sonnet-4-6"),
            "max_tokens": max_tokens,
            "messages": chat_messages or [{"role": "user", "content": ""}],
        }
        if system_msg:
            create_kwargs["system"] = system_msg

        create_kwargs.update(kwargs)
        response = await client.messages.create(**create_kwargs)
        # Newer models can emit thinking blocks first; return the text blocks.
        return "".join(
            block.text
            for block in (response.content or [])
            if isinstance(getattr(block, "text", None), str)
        )

    async def structured(
        self, prompt: str, schema: dict, **kwargs: Any
    ) -> dict:
        text = await self.complete(with_schema_instruction(prompt, schema), **kwargs)
        return parse_json_response(text)

    async def test_connection(self) -> bool:
        client = self._get_client()
        response = await client.messages.create(
            model=self.model or "claude-sonnet-4-6",
            max_tokens=1,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return bool(response.content)

    async def list_models(self) -> list[ModelInfo]:
        try:
            client = self._get_client()
            models = []
            response = await client.models.list(limit=100)
            for m in response.data:
                models.append(
                    ModelInfo(
                        id=m.id,
                        name=getattr(m, "display_name", m.id),
                    )
                )
            return sorted(models, key=lambda m: m.id) if models else _FALLBACK_MODELS
        except Exception:
            logger.debug("Failed to list Anthropic models dynamically, using fallback", exc_info=True)
            return _FALLBACK_MODELS
