"""U2 regression: the FastAPI app version must track pyproject, not a stale literal."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

from app import main


def test_app_version_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert main.app.version == pyproject["project"]["version"]


def test_app_version_falls_back_when_not_installed(monkeypatch):
    def _missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", _missing)
    assert main._app_version() == "0.0.0+unknown"
