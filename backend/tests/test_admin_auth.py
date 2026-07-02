"""Admin-token gating of the mutating OWL-update routes (Phase 2b)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.auth import require_admin
from app.config import settings
from app.main import app

client = TestClient(app)


class TestRequireAdminDependency:
    def test_unset_token_allows(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "")
        assert require_admin(x_admin_token=None) is None
        assert require_admin(x_admin_token="anything") is None

    def test_set_token_requires_match(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "s3cret")
        with pytest.raises(HTTPException) as e1:
            require_admin(x_admin_token=None)
        assert e1.value.status_code == 403
        with pytest.raises(HTTPException):
            require_admin(x_admin_token="wrong")
        assert require_admin(x_admin_token="s3cret") is None


class TestUpdateRoutesGated:
    def test_check_requires_token_when_configured(self, monkeypatch):
        # Auth runs before the handler, so a missing token is a clean 403 (no fetch).
        monkeypatch.setattr(settings, "admin_token", "s3cret")
        r = client.post("/folio/update/check")
        assert r.status_code == 403

    def test_status_is_open(self):
        # Read-only status is not gated.
        r = client.get("/folio/update/status")
        assert r.status_code == 200
