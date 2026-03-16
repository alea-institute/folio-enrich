"""Tests for FOLIO update API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.folio.owl_updater import OWLUpdateManager


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset OWLUpdateManager singleton between tests."""
    OWLUpdateManager.reset_instance()
    yield
    OWLUpdateManager.reset_instance()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_status_shape(self, client):
        with patch("app.api.routes.folio_update.get_owl_status", return_value={"cached": True, "etag": "abc"}):
            r = await client.get("/folio/update/status")
            assert r.status_code == 200
            data = r.json()
            assert "update" in data
            assert "owl_cache" in data
            assert "folio_stats" in data
            assert data["update"]["update_available"] is False
            assert data["update"]["update_in_progress"] is False

    @pytest.mark.asyncio
    async def test_status_includes_folio_stats(self, client):
        """When FOLIO is loaded, status should include concept/label/property counts."""
        mock_svc = MagicMock()
        mock_svc._folio = MagicMock()  # Simulate loaded FOLIO
        mock_svc.get_concept_count = MagicMock(return_value=2847)
        mock_svc.get_label_count = MagicMock(return_value=4312)
        mock_svc.get_property_count = MagicMock(return_value=189)

        with patch("app.api.routes.folio_update.get_owl_status", return_value={"cached": True}), \
             patch("app.services.folio.folio_service.FolioService.get_instance", return_value=mock_svc):
            r = await client.get("/folio/update/status")
            assert r.status_code == 200
            data = r.json()
            stats = data["folio_stats"]
            assert stats["concept_count"] == 2847
            assert stats["label_count"] == 4312
            assert stats["property_count"] == 189


class TestCheckUpdate:
    @pytest.mark.asyncio
    async def test_check_no_update(self, client):
        with patch.object(OWLUpdateManager, "check", new_callable=AsyncMock, return_value=False), \
             patch.object(OWLUpdateManager, "get_status", return_value={"update_available": False}):
            r = await client.post("/folio/update/check")
            assert r.status_code == 200
            data = r.json()
            assert data["update_available"] is False

    @pytest.mark.asyncio
    async def test_check_update_available(self, client):
        with patch.object(OWLUpdateManager, "check", new_callable=AsyncMock, return_value=True), \
             patch.object(OWLUpdateManager, "get_status", return_value={"update_available": True}):
            r = await client.post("/folio/update/check")
            assert r.status_code == 200
            data = r.json()
            assert data["update_available"] is True


class TestApplyUpdate:
    @pytest.mark.asyncio
    async def test_apply_success(self, client):
        stats = {"concepts_before": 100, "concepts_after": 105}
        with patch.object(OWLUpdateManager, "apply", new_callable=AsyncMock, return_value=stats), \
             patch.object(OWLUpdateManager, "get_status", return_value={"update_available": False}):
            r = await client.post("/folio/update/apply")
            assert r.status_code == 200
            data = r.json()
            assert data["applied"] is True
            assert data["reload_stats"]["concepts_after"] == 105

    @pytest.mark.asyncio
    async def test_apply_nothing_to_do(self, client):
        with patch.object(OWLUpdateManager, "apply", new_callable=AsyncMock, return_value=None), \
             patch.object(OWLUpdateManager, "get_status", return_value={"update_available": False}):
            r = await client.post("/folio/update/apply")
            assert r.status_code == 200
            data = r.json()
            assert data["applied"] is False


class TestRollbackUpdate:
    @pytest.mark.asyncio
    async def test_rollback_success(self, client):
        stats = {"concepts_before": 105, "concepts_after": 100}
        with patch.object(OWLUpdateManager, "rollback", new_callable=AsyncMock, return_value=stats), \
             patch.object(OWLUpdateManager, "get_status", return_value={"update_available": False}):
            r = await client.post("/folio/update/rollback")
            assert r.status_code == 200
            data = r.json()
            assert data["rolled_back"] is True

    @pytest.mark.asyncio
    async def test_rollback_no_previous(self, client):
        with patch.object(OWLUpdateManager, "rollback", new_callable=AsyncMock, return_value=None), \
             patch.object(OWLUpdateManager, "get_status", return_value={"error": "No previous version"}):
            r = await client.post("/folio/update/rollback")
            assert r.status_code == 200
            data = r.json()
            assert data["rolled_back"] is False
