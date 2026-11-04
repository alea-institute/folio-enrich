"""Bake-only Codex CLI adapter. Deliberately absent from the web provider registry."""
from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path
import tempfile
from typing import Any

from app.models.llm_models import ModelInfo
from app.services.llm.base import LLMProvider
from app.services.llm.json_utils import parse_json_response

# Shared across provider instances. Override before starting the bake process.
_CALL_SLOTS = asyncio.Semaphore(int(os.environ.get("CODEX_CLI_MAX_CONCURRENCY", "3")))


def _strict_compatible(schema: dict) -> bool:
    """Conservatively use strict output only for the supported JSON Schema subset.

    In particular, inspect nested objects, definitions and array items, without
    rewriting the caller's schema or making optional fields required.
    """
    allowed = {
        "type", "properties", "required", "additionalProperties", "items",
        "enum", "anyOf", "$ref", "$defs", "definitions", "description", "title",
    }

    def supported(node: Any) -> bool:
        if not isinstance(node, dict) or set(node) - allowed:
            return False
        if node.get("type") == "object" or "properties" in node:
            props = node.get("properties", {})
            required = node.get("required")
            if (node.get("additionalProperties") is not False
                    or not isinstance(required, list)
                    or set(required) != set(props)):
                return False
        for key in ("properties", "$defs", "definitions"):
            if key in node and not all(supported(v) for v in node[key].values()):
                return False
        if "items" in node and not supported(node["items"]):
            return False
        if "anyOf" in node and not all(supported(v) for v in node["anyOf"]):
            return False
        return True

    return schema.get("type") == "object" and "anyOf" not in schema and supported(schema)


class CodexCLIProvider(LLMProvider):
    """Run ephemeral, read-only CLI calls using the local subscription login.

    Prompts always travel over stdin. Each call starts outside the repository,
    in its own temporary directory. CODEX_CLI_MAX_CONCURRENCY (default 3) limits
    all instances in the bake process; timeout is in seconds.
    """

    def __init__(
        self, model: str | None = None, *, effort: str = "medium",
        timeout: float = 300,
    ) -> None:
        super().__init__(model=model or "gpt-6.1-sol")
        if effort not in {"low", "medium", "high"}:
            raise ValueError("Codex CLI effort must be low, medium, or high")
        self.effort = effort
        self.timeout = timeout

    async def _run(self, prompt: str, schema: dict | None = None, **kwargs: Any) -> str:
        model = kwargs.get("model") or self.model
        async with _CALL_SLOTS:
            with tempfile.TemporaryDirectory(prefix="folio_codex_") as cwd:
                output = Path(cwd) / "out.txt"
                args = [
                    "codex", "exec", "--skip-git-repo-check", "--ephemeral",
                    "-s", "read-only", "-m", model,
                    "-c", f"model_reasoning_effort={self.effort}", "-o", str(output),
                ]
                if schema is not None:
                    schema_path = Path(cwd) / "schema.json"
                    schema_path.write_text(json.dumps(schema), encoding="utf-8")
                    args.extend(["--output-schema", str(schema_path)])
                args.append("-")
                try:
                    process = await asyncio.create_subprocess_exec(
                        *args, cwd=cwd, start_new_session=True, stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
                    )
                except OSError as exc:
                    raise RuntimeError(f"Codex CLI model {model}: could not start: {exc}") from exc

                # Shield communication so timeout/cancellation can reap the process
                # and retain its stderr before the temporary directory is removed.
                communication = asyncio.create_task(process.communicate(prompt.encode("utf-8")))
                try:
                    _, stderr = await asyncio.wait_for(
                        asyncio.shield(communication), timeout=self.timeout,
                    )
                except (TimeoutError, asyncio.CancelledError) as exc:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # The child may have exited just as the deadline fired.
                    _, stderr = await communication
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    raise RuntimeError(
                        f"Codex CLI model {model} timed out after {self.timeout}s; "
                        f"stderr tail: {stderr.decode(errors='replace')[-2000:]}"
                    ) from exc

                detail = f"stderr tail: {stderr.decode(errors='replace')[-2000:]}"
                if process.returncode != 0:
                    raise RuntimeError(
                        f"Codex CLI model {model} exited {process.returncode}; {detail}"
                    )
                text = output.read_text(encoding="utf-8").strip() if output.exists() else ""
                if not text:
                    raise RuntimeError(f"Codex CLI model {model} returned empty output; {detail}")
                return text

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        return await self._run(prompt, **kwargs)

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        prompt = "\n\n".join(
            f"{message.get('role', 'user')}: {message.get('content', '')}"
            for message in messages
        )
        return await self.complete(prompt, **kwargs)

    async def structured(self, prompt: str, schema: dict, **kwargs: Any) -> dict:
        if _strict_compatible(schema):
            text = await self._run(prompt, schema=schema, **kwargs)
        else:
            text = await self._run(
                f"{prompt}\n\nReturn only JSON matching this schema:\n{json.dumps(schema)}",
                **kwargs,
            )
        return parse_json_response(text)

    async def test_connection(self) -> bool:
        try:
            return bool(await self.complete("Reply with OK."))
        except RuntimeError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        # The CLI has no model-list endpoint. Advertise only the configured model;
        # subscription availability is verified by test_connection when requested.
        return [ModelInfo(id=self.model, name=self.model)]
