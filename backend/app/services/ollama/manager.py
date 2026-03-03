"""Ollama lifecycle manager — detect, install, start, stop, pull models."""
from __future__ import annotations

import asyncio
import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


class OllamaStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"  # binary found but server not running
    RUNNING = "running"


class ModelTier(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


# Map each pipeline task to a model tier
TASK_TIER_MAP: dict[str, ModelTier] = {
    "document_type": ModelTier.SIMPLE,
    "area_of_law": ModelTier.SIMPLE,
    "concept": ModelTier.MEDIUM,
    "branch_judge": ModelTier.MEDIUM,
    "synthetic": ModelTier.MEDIUM,
    "classifier": ModelTier.COMPLEX,
    "extractor": ModelTier.COMPLEX,
    "individual": ModelTier.COMPLEX,
    "property": ModelTier.COMPLEX,
}


@dataclass
class OllamaInfo:
    status: OllamaStatus
    version: str = ""
    binary_path: str = ""
    base_url: str = ""
    models: list[str] = field(default_factory=list)


@dataclass
class PullProgress:
    model: str
    status: str
    total_bytes: int = 0
    completed_bytes: int = 0
    percent: float = 0.0


class OllamaManager:
    """Singleton managing the Ollama lifecycle."""

    _instance: OllamaManager | None = None
    _managed_process: subprocess.Popen | None = None

    def __init__(self) -> None:
        from app.config import settings
        self._base_url = settings.ollama_base_url
        self._auto_manage = settings.ollama_auto_manage

    @classmethod
    def get_instance(cls) -> OllamaManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._managed_process = None

    # ── Detection ──────────────────────────────────────────────────

    async def detect(self) -> OllamaInfo:
        """Detect Ollama: find binary, check if API is reachable."""
        binary = self._find_binary()
        base_url = self._base_url

        # Check if API is reachable
        api_ok = await self._api_reachable()
        if api_ok:
            version = await self._get_version()
            models = await self._list_model_names()
            return OllamaInfo(
                status=OllamaStatus.RUNNING,
                version=version,
                binary_path=binary or "",
                base_url=base_url,
                models=models,
            )

        if binary:
            return OllamaInfo(
                status=OllamaStatus.INSTALLED,
                binary_path=binary,
                base_url=base_url,
            )

        return OllamaInfo(status=OllamaStatus.NOT_INSTALLED, base_url=base_url)

    def _find_binary(self) -> str | None:
        """Find the ollama binary on the system."""
        path = shutil.which("ollama")
        if path:
            return path

        # Platform-specific fallback paths
        system = platform.system()
        fallbacks: list[str] = []
        if system == "Linux":
            fallbacks = ["/usr/local/bin/ollama", "/usr/bin/ollama"]
        elif system == "Darwin":
            fallbacks = ["/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"]
        elif system == "Windows":
            import os
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                fallbacks = [f"{local_app}\\Programs\\Ollama\\ollama.exe"]

        for fb in fallbacks:
            import os
            if os.path.isfile(fb) and os.access(fb, os.X_OK):
                return fb

        return None

    async def _api_reachable(self) -> bool:
        """Check if the Ollama API responds."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def _get_version(self) -> str:
        """Get Ollama version from the API."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/api/version")
                if resp.status_code == 200:
                    return resp.json().get("version", "unknown")
        except Exception:
            pass
        return "unknown"

    async def _list_model_names(self) -> list[str]:
        """List locally available model names."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    # ── Installation ───────────────────────────────────────────────

    async def install(self) -> AsyncGenerator[str, None]:
        """Install Ollama. Yields progress messages."""
        system = platform.system()
        if system in ("Linux", "Darwin"):
            yield "Downloading Ollama install script..."
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout is not None
            async for line in proc.stdout:
                text = line.decode().strip()
                if text:
                    yield text
            await proc.wait()
            if proc.returncode == 0:
                yield "Ollama installed successfully"
            else:
                yield f"Installation failed (exit code {proc.returncode})"
        elif system == "Windows":
            yield "Downloading Ollama for Windows..."
            # Download the installer
            url = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
            import tempfile, os
            installer = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
            async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                resp = await client.get(url)
                with open(installer, "wb") as f:
                    f.write(resp.content)
            yield "Running installer..."
            proc = await asyncio.create_subprocess_exec(
                installer, "/SILENT",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await proc.wait()
            if proc.returncode == 0:
                yield "Ollama installed successfully"
            else:
                yield f"Installation failed (exit code {proc.returncode})"
        else:
            yield f"Unsupported platform: {system}"

    # ── Start / Stop ───────────────────────────────────────────────

    async def start(self, timeout: int = 30) -> bool:
        """Start `ollama serve` in the background. Returns True if server comes up."""
        if await self._api_reachable():
            logger.info("Ollama already running")
            return True

        binary = self._find_binary()
        if not binary:
            logger.error("Ollama binary not found — cannot start")
            return False

        logger.info("Starting Ollama server: %s serve", binary)
        self.__class__._managed_process = subprocess.Popen(
            [binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Poll until API responds
        for _ in range(timeout * 2):
            await asyncio.sleep(0.5)
            if await self._api_reachable():
                logger.info("Ollama server started (PID %d)", self._managed_process.pid)
                return True

        logger.error("Ollama server did not respond within %ds", timeout)
        return False

    async def stop(self) -> None:
        """Stop the managed Ollama process (only if we started it)."""
        proc = self.__class__._managed_process
        if proc is None:
            return

        try:
            proc.terminate()
            proc.wait(timeout=10)
            logger.info("Ollama server stopped (PID %d)", proc.pid)
        except Exception as e:
            logger.warning("Failed to stop Ollama: %s", e)
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            self.__class__._managed_process = None

    # ── Model management ───────────────────────────────────────────

    async def list_local_models(self) -> list[dict]:
        """List locally available models with details."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code == 200:
                    return resp.json().get("models", [])
        except Exception:
            pass
        return []

    async def pull_model(self, model: str) -> AsyncGenerator[PullProgress, None]:
        """Pull a model, yielding progress events."""
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/pull",
                json={"name": model, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    import json
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    percent = (completed / total * 100) if total else 0.0

                    yield PullProgress(
                        model=model,
                        status=data.get("status", ""),
                        total_bytes=total,
                        completed_bytes=completed,
                        percent=round(percent, 1),
                    )

    async def ensure_ready(self) -> OllamaInfo:
        """Orchestrate: detect → start if needed → return info."""
        info = await self.detect()

        if info.status == OllamaStatus.RUNNING:
            return info

        if info.status == OllamaStatus.INSTALLED:
            started = await self.start()
            if started:
                info = await self.detect()
            return info

        # NOT_INSTALLED — caller needs to run install
        return info

    # ── Tier-based model selection ─────────────────────────────────

    def get_model_for_task(self, task: str) -> str:
        """Return the tier-appropriate model name for a pipeline task."""
        from app.config import settings

        tier = TASK_TIER_MAP.get(task, ModelTier.MEDIUM)
        tier_attr = f"ollama_model_{tier.value}"
        return getattr(settings, tier_attr, settings.ollama_model_medium)

    def get_required_models(self) -> set[str]:
        """Deduplicated set of models across all tiers."""
        from app.config import settings
        return {
            settings.ollama_model_simple,
            settings.ollama_model_medium,
            settings.ollama_model_complex,
        }

    def get_tier_config(self) -> dict:
        """Return the full task-to-model mapping."""
        result = {}
        for task, tier in TASK_TIER_MAP.items():
            result[task] = {
                "tier": tier.value,
                "model": self.get_model_for_task(task),
            }
        return result

    # ── System info ────────────────────────────────────────────────

    @staticmethod
    def get_system_ram_gb() -> float:
        """Get total system RAM in GB."""
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except ImportError:
            # Fallback: read /proc/meminfo on Linux
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return round(kb / (1024 ** 2), 1)
            except Exception:
                pass
        return 0.0
