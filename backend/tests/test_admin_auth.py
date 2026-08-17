"""Admin-token gating of the mutating OWL-update routes (Phase 2b)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.auth import require_admin, require_annotation
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


class TestRequireAnnotationDependency:
    def test_unset_tokens_allow_local_annotation(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "")
        monkeypatch.setattr(settings, "annotation_token", "")
        assert require_annotation(x_annotation_token=None, x_admin_token=None) is None

    def test_scoped_or_admin_token_allows_annotation(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "admin-secret")
        monkeypatch.setattr(settings, "annotation_token", "annotation-secret")

        assert (
            require_annotation(
                x_annotation_token="annotation-secret",
                x_admin_token=None,
                annotation_cookie=None,
                annotation_origin=None,
                request_host=None,
            )
            is None
        )
        assert (
            require_annotation(
                x_annotation_token=None,
                x_admin_token="admin-secret",
                annotation_cookie=None,
                annotation_origin=None,
                request_host=None,
            )
            is None
        )
        # Legacy browser values remain usable after the UI switches header names.
        assert (
            require_annotation(
                x_annotation_token="admin-secret",
                x_admin_token=None,
                annotation_cookie=None,
                annotation_origin=None,
                request_host=None,
            )
            is None
        )
        assert (
            require_annotation(
                x_annotation_token=None,
                x_admin_token=None,
                annotation_cookie="annotation-secret",
                annotation_origin="https://propositions.example",
                request_host="propositions.example",
            )
            is None
        )

    def test_wrong_annotation_token_is_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "admin-secret")
        monkeypatch.setattr(settings, "annotation_token", "annotation-secret")

        with pytest.raises(HTTPException) as exc:
            require_annotation(
                x_annotation_token="wrong",
                x_admin_token=None,
                annotation_cookie=None,
                annotation_origin=None,
                request_host=None,
            )
        assert exc.value.status_code == 403

    def test_cookie_requires_same_origin(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "")
        monkeypatch.setattr(settings, "annotation_token", "annotation-secret")

        with pytest.raises(HTTPException) as missing:
            require_annotation(None, None, "annotation-secret", None, "propositions.example")
        assert missing.value.status_code == 403
        with pytest.raises(HTTPException) as sibling:
            require_annotation(
                None,
                None,
                "annotation-secret",
                "https://mapper.example",
                "propositions.example",
            )
        assert sibling.value.status_code == 403

    def test_annotation_token_cannot_authorize_admin_route(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "admin-secret")
        monkeypatch.setattr(settings, "annotation_token", "annotation-secret")

        with pytest.raises(HTTPException):
            require_admin(x_admin_token="annotation-secret")


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

    def test_annotation_token_cannot_authorize_update_route(self, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "admin-secret")
        monkeypatch.setattr(settings, "annotation_token", "annotation-secret")
        r = client.post(
            "/folio/update/check", headers={"X-Annotation-Token": "annotation-secret"}
        )
        assert r.status_code == 403
