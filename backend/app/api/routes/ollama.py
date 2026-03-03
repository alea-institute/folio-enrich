"""Ollama management API routes."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.services.ollama.manager import OllamaManager, OllamaStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ollama", tags=["ollama"])


class PullRequest(BaseModel):
    model: str | None = None  # None = pull all tier models


@router.get("/status")
async def ollama_status() -> dict:
    """Current Ollama status: installed/running/models + available RAM."""
    manager = OllamaManager.get_instance()
    info = await manager.detect()
    return {
        "status": info.status.value,
        "version": info.version,
        "binary_path": info.binary_path,
        "base_url": info.base_url,
        "models": info.models,
        "ram_gb": manager.get_system_ram_gb(),
        "required_models": sorted(manager.get_required_models()),
        "missing_models": sorted(
            manager.get_required_models() - set(info.models)
        ) if info.status == OllamaStatus.RUNNING else [],
    }


@router.post("/setup")
async def ollama_setup() -> EventSourceResponse:
    """Full auto-setup: install + start + pull all tier models. SSE stream."""
    async def event_stream():
        manager = OllamaManager.get_instance()

        # Step 1: Detect
        yield {"event": "status", "data": json.dumps({"step": "detect", "message": "Checking for Ollama..."})}
        info = await manager.detect()

        # Step 2: Install if needed
        if info.status == OllamaStatus.NOT_INSTALLED:
            yield {"event": "status", "data": json.dumps({"step": "install", "message": "Installing Ollama..."})}
            async for msg in manager.install():
                yield {"event": "install", "data": json.dumps({"message": msg})}

        # Step 3: Start if needed
        info = await manager.detect()
        if info.status != OllamaStatus.RUNNING:
            yield {"event": "status", "data": json.dumps({"step": "start", "message": "Starting Ollama server..."})}
            started = await manager.start()
            if not started:
                yield {"event": "error", "data": json.dumps({"message": "Failed to start Ollama server"})}
                return

        # Step 4: Pull missing models
        info = await manager.detect()
        required = manager.get_required_models()
        local_models = set(info.models)
        missing = required - local_models

        if missing:
            yield {"event": "status", "data": json.dumps({"step": "pull", "message": f"Downloading {len(missing)} model(s)..."})}
            for model in sorted(missing):
                yield {"event": "pull_start", "data": json.dumps({"model": model})}
                try:
                    async for progress in manager.pull_model(model):
                        yield {"event": "pull_progress", "data": json.dumps({
                            "model": progress.model,
                            "status": progress.status,
                            "total_bytes": progress.total_bytes,
                            "completed_bytes": progress.completed_bytes,
                            "percent": progress.percent,
                        })}
                except Exception as e:
                    yield {"event": "pull_error", "data": json.dumps({"model": model, "error": str(e)})}

        yield {"event": "complete", "data": json.dumps({"message": "Ollama setup complete"})}

    return EventSourceResponse(event_stream())


@router.post("/start")
async def ollama_start() -> dict:
    """Start Ollama server only."""
    manager = OllamaManager.get_instance()
    started = await manager.start()
    return {"started": started}


@router.post("/stop")
async def ollama_stop() -> dict:
    """Stop managed Ollama process."""
    manager = OllamaManager.get_instance()
    await manager.stop()
    return {"stopped": True}


@router.post("/pull")
async def ollama_pull(req: PullRequest) -> EventSourceResponse:
    """Pull specific model or all tier models. SSE stream."""
    async def event_stream():
        manager = OllamaManager.get_instance()

        if req.model:
            models = [req.model]
        else:
            models = sorted(manager.get_required_models())

        for model in models:
            yield {"event": "pull_start", "data": json.dumps({"model": model})}
            try:
                async for progress in manager.pull_model(model):
                    yield {"event": "pull_progress", "data": json.dumps({
                        "model": progress.model,
                        "status": progress.status,
                        "total_bytes": progress.total_bytes,
                        "completed_bytes": progress.completed_bytes,
                        "percent": progress.percent,
                    })}
            except Exception as e:
                yield {"event": "pull_error", "data": json.dumps({"model": model, "error": str(e)})}

        yield {"event": "complete", "data": json.dumps({"message": "Pull complete"})}

    return EventSourceResponse(event_stream())


@router.get("/models")
async def ollama_models() -> dict:
    """List locally available models."""
    manager = OllamaManager.get_instance()
    models = await manager.list_local_models()
    return {"models": models}


@router.get("/tier-config")
async def ollama_tier_config() -> dict:
    """Current task-to-model tier mapping."""
    manager = OllamaManager.get_instance()
    return {"tasks": manager.get_tier_config()}
