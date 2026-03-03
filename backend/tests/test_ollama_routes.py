"""Tests for Ollama API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ollama.manager import OllamaInfo, OllamaManager, OllamaStatus


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset OllamaManager singleton between tests."""
    OllamaManager.reset_instance()
    yield
    OllamaManager.reset_instance()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestOllamaStatus:
    @pytest.mark.asyncio
    async def test_status_shape(self, client):
        running_info = OllamaInfo(
            status=OllamaStatus.RUNNING,
            version='0.5.0',
            binary_path='/usr/bin/ollama',
            base_url='http://localhost:11434',
            models=['qwen3:8b', 'qwen3:4b'],
        )
        with patch.object(OllamaManager, 'detect', new_callable=AsyncMock, return_value=running_info), \
             patch.object(OllamaManager, 'get_system_ram_gb', return_value=16.0):
            r = await client.get('/ollama/status')
            assert r.status_code == 200
            data = r.json()
            assert data['status'] == 'running'
            assert data['version'] == '0.5.0'
            assert 'models' in data
            assert 'ram_gb' in data
            assert 'required_models' in data
            assert 'missing_models' in data

    @pytest.mark.asyncio
    async def test_status_not_installed(self, client):
        info = OllamaInfo(status=OllamaStatus.NOT_INSTALLED, base_url='http://localhost:11434')
        with patch.object(OllamaManager, 'detect', new_callable=AsyncMock, return_value=info), \
             patch.object(OllamaManager, 'get_system_ram_gb', return_value=8.0):
            r = await client.get('/ollama/status')
            assert r.status_code == 200
            data = r.json()
            assert data['status'] == 'not_installed'


class TestOllamaTierConfig:
    @pytest.mark.asyncio
    async def test_tier_config_returns_all_9_tasks(self, client):
        r = await client.get('/ollama/tier-config')
        assert r.status_code == 200
        data = r.json()
        tasks = data['tasks']
        assert len(tasks) == 9
        expected = {"document_type", "area_of_law", "concept", "branch_judge",
                    "synthetic", "classifier", "extractor", "individual", "property"}
        assert set(tasks.keys()) == expected
        # Check structure
        for task_info in tasks.values():
            assert 'tier' in task_info
            assert 'model' in task_info
            assert task_info['tier'] in ('simple', 'medium', 'complex')


class TestOllamaModels:
    @pytest.mark.asyncio
    async def test_models_endpoint(self, client):
        mock_models = [
            {"name": "qwen3:8b", "size": 5000000000},
            {"name": "qwen3:4b", "size": 2500000000},
        ]
        with patch.object(OllamaManager, 'list_local_models', new_callable=AsyncMock, return_value=mock_models):
            r = await client.get('/ollama/models')
            assert r.status_code == 200
            data = r.json()
            assert len(data['models']) == 2


class TestOllamaStartStop:
    @pytest.mark.asyncio
    async def test_start(self, client):
        with patch.object(OllamaManager, 'start', new_callable=AsyncMock, return_value=True):
            r = await client.post('/ollama/start')
            assert r.status_code == 200
            assert r.json()['started'] is True

    @pytest.mark.asyncio
    async def test_stop(self, client):
        with patch.object(OllamaManager, 'stop', new_callable=AsyncMock):
            r = await client.post('/ollama/stop')
            assert r.status_code == 200
            assert r.json()['stopped'] is True
