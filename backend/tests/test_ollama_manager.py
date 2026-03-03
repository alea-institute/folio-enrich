"""Tests for the OllamaManager service."""
from __future__ import annotations

import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ollama.manager import (
    TASK_TIER_MAP,
    ModelTier,
    OllamaInfo,
    OllamaManager,
    OllamaStatus,
    PullProgress,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset OllamaManager singleton between tests."""
    OllamaManager.reset_instance()
    yield
    OllamaManager.reset_instance()


# ── Task tier mapping ──────────────────────────────────────────

class TestTaskTierMap:
    def test_all_9_tasks_covered(self):
        expected = {"document_type", "area_of_law", "concept", "branch_judge",
                    "synthetic", "classifier", "extractor", "individual", "property"}
        assert set(TASK_TIER_MAP.keys()) == expected

    def test_simple_tasks(self):
        for task in ("document_type", "area_of_law"):
            assert TASK_TIER_MAP[task] == ModelTier.SIMPLE

    def test_medium_tasks(self):
        for task in ("concept", "branch_judge", "synthetic"):
            assert TASK_TIER_MAP[task] == ModelTier.MEDIUM

    def test_complex_tasks(self):
        for task in ("classifier", "extractor", "individual", "property"):
            assert TASK_TIER_MAP[task] == ModelTier.COMPLEX


# ── Model selection ────────────────────────────────────────────

class TestModelSelection:
    def test_get_model_for_simple_task(self):
        manager = OllamaManager.get_instance()
        model = manager.get_model_for_task("document_type")
        assert model == "qwen3:4b"

    def test_get_model_for_medium_task(self):
        manager = OllamaManager.get_instance()
        model = manager.get_model_for_task("concept")
        assert model == "qwen3:8b"

    def test_get_model_for_complex_task(self):
        manager = OllamaManager.get_instance()
        model = manager.get_model_for_task("classifier")
        assert model == "qwen3:14b"

    def test_unknown_task_defaults_to_medium(self):
        manager = OllamaManager.get_instance()
        model = manager.get_model_for_task("nonexistent_task")
        assert model == "qwen3:8b"

    def test_get_required_models(self):
        manager = OllamaManager.get_instance()
        models = manager.get_required_models()
        assert models == {"qwen3:4b", "qwen3:8b", "qwen3:14b"}

    def test_get_tier_config(self):
        manager = OllamaManager.get_instance()
        config = manager.get_tier_config()
        assert len(config) == 9
        assert config["document_type"]["tier"] == "simple"
        assert config["document_type"]["model"] == "qwen3:4b"
        assert config["classifier"]["tier"] == "complex"
        assert config["classifier"]["model"] == "qwen3:14b"


# ── Detection ──────────────────────────────────────────────────

class TestDetection:
    @pytest.mark.asyncio
    async def test_detect_running(self):
        manager = OllamaManager.get_instance()
        with patch.object(manager, '_find_binary', return_value='/usr/bin/ollama'), \
             patch.object(manager, '_api_reachable', new_callable=AsyncMock, return_value=True), \
             patch.object(manager, '_get_version', new_callable=AsyncMock, return_value='0.5.0'), \
             patch.object(manager, '_list_model_names', new_callable=AsyncMock, return_value=['qwen3:8b']):
            info = await manager.detect()
            assert info.status == OllamaStatus.RUNNING
            assert info.version == '0.5.0'
            assert info.models == ['qwen3:8b']

    @pytest.mark.asyncio
    async def test_detect_installed_not_running(self):
        manager = OllamaManager.get_instance()
        with patch.object(manager, '_find_binary', return_value='/usr/bin/ollama'), \
             patch.object(manager, '_api_reachable', new_callable=AsyncMock, return_value=False):
            info = await manager.detect()
            assert info.status == OllamaStatus.INSTALLED
            assert info.binary_path == '/usr/bin/ollama'

    @pytest.mark.asyncio
    async def test_detect_not_installed(self):
        manager = OllamaManager.get_instance()
        with patch.object(manager, '_find_binary', return_value=None), \
             patch.object(manager, '_api_reachable', new_callable=AsyncMock, return_value=False):
            info = await manager.detect()
            assert info.status == OllamaStatus.NOT_INSTALLED

    def test_find_binary_via_which(self):
        manager = OllamaManager.get_instance()
        with patch('shutil.which', return_value='/usr/bin/ollama'):
            assert manager._find_binary() == '/usr/bin/ollama'

    def test_find_binary_not_found(self):
        manager = OllamaManager.get_instance()
        with patch('shutil.which', return_value=None), \
             patch('platform.system', return_value='Linux'), \
             patch('os.path.isfile', return_value=False):
            assert manager._find_binary() is None


# ── Start / Stop ───────────────────────────────────────────────

class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_already_running(self):
        manager = OllamaManager.get_instance()
        with patch.object(manager, '_api_reachable', new_callable=AsyncMock, return_value=True):
            result = await manager.start()
            assert result is True

    @pytest.mark.asyncio
    async def test_start_no_binary(self):
        manager = OllamaManager.get_instance()
        with patch.object(manager, '_api_reachable', new_callable=AsyncMock, return_value=False), \
             patch.object(manager, '_find_binary', return_value=None):
            result = await manager.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_stop_no_managed_process(self):
        manager = OllamaManager.get_instance()
        OllamaManager._managed_process = None
        await manager.stop()  # Should not raise


# ── ensure_ready ───────────────────────────────────────────────

class TestEnsureReady:
    @pytest.mark.asyncio
    async def test_ensure_ready_already_running(self):
        manager = OllamaManager.get_instance()
        running_info = OllamaInfo(status=OllamaStatus.RUNNING, version='0.5.0', models=['qwen3:8b'])
        with patch.object(manager, 'detect', new_callable=AsyncMock, return_value=running_info):
            info = await manager.ensure_ready()
            assert info.status == OllamaStatus.RUNNING

    @pytest.mark.asyncio
    async def test_ensure_ready_installed_starts(self):
        manager = OllamaManager.get_instance()
        installed_info = OllamaInfo(status=OllamaStatus.INSTALLED, binary_path='/usr/bin/ollama')
        running_info = OllamaInfo(status=OllamaStatus.RUNNING, version='0.5.0')
        detect_mock = AsyncMock(side_effect=[installed_info, running_info])
        with patch.object(manager, 'detect', detect_mock), \
             patch.object(manager, 'start', new_callable=AsyncMock, return_value=True):
            info = await manager.ensure_ready()
            assert info.status == OllamaStatus.RUNNING


# ── System info ────────────────────────────────────────────────

class TestSystemInfo:
    def test_get_system_ram_gb(self):
        ram = OllamaManager.get_system_ram_gb()
        # Should return a positive number on any real system (or 0 if psutil missing)
        assert isinstance(ram, float)
        assert ram >= 0.0


# ── Cross-platform binary paths ───────────────────────────────

class TestCrossPlatform:
    def test_linux_fallback_paths(self):
        manager = OllamaManager.get_instance()
        with patch('shutil.which', return_value=None), \
             patch('platform.system', return_value='Linux'), \
             patch('os.path.isfile', side_effect=lambda p: p == '/usr/local/bin/ollama'), \
             patch('os.access', return_value=True):
            assert manager._find_binary() == '/usr/local/bin/ollama'

    def test_macos_fallback_paths(self):
        manager = OllamaManager.get_instance()
        with patch('shutil.which', return_value=None), \
             patch('platform.system', return_value='Darwin'), \
             patch('os.path.isfile', side_effect=lambda p: p == '/opt/homebrew/bin/ollama'), \
             patch('os.access', return_value=True):
            assert manager._find_binary() == '/opt/homebrew/bin/ollama'

    def test_windows_fallback_paths(self):
        manager = OllamaManager.get_instance()
        with patch('shutil.which', return_value=None), \
             patch('platform.system', return_value='Windows'), \
             patch.dict('os.environ', {'LOCALAPPDATA': 'C:\\Users\\test\\AppData\\Local'}), \
             patch('os.path.isfile', return_value=True), \
             patch('os.access', return_value=True):
            result = manager._find_binary()
            assert result is not None
            assert 'Ollama' in result
