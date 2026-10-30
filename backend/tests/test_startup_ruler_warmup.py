"""Startup warms the cached FOLIO EntityRuler off the event loop.

Building the shared ruler compiles every FOLIO label (seconds). Lifespan
schedules it as a background thread task so the first job does not pay for it,
startup is not blocked on it, and a failure never crashes startup.
"""
from __future__ import annotations

import threading
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app.main as main_mod
from app.pipeline.stages import entity_ruler_stage as ers


def _quiet_startup():
    """Skip the slow, unrelated startup work so only the warm-up is exercised."""
    return (
        patch.object(main_mod, "_manage_ollama", AsyncMock()),
        patch.object(main_mod, "_index_folio_embeddings", AsyncMock()),
    )


def test_lifespan_schedules_ruler_build_off_the_event_loop():
    calls: list[tuple[str, bool]] = []
    built = threading.Event()

    def fake_builder(ontology_id):
        calls.append((ontology_id, threading.current_thread() is threading.main_thread()))
        built.set()

    ollama, embed = _quiet_startup()
    with ollama, embed, patch.object(ers, "_get_ruler_bundle", side_effect=fake_builder):
        with TestClient(main_mod.app) as client:
            assert built.wait(10), "lifespan never scheduled the EntityRuler build"
            assert client.get("/health").status_code == 200

    assert len(calls) == 1
    ontology_id, on_main_thread = calls[0]
    assert ontology_id == main_mod.app.state.default_ontology
    assert not on_main_thread


def test_startup_does_not_wait_for_the_build():
    release = threading.Event()
    started = threading.Event()

    def slow_builder(ontology_id):
        started.set()
        release.wait(10)

    ollama, embed = _quiet_startup()
    with ollama, embed, patch.object(ers, "_get_ruler_bundle", side_effect=slow_builder):
        with TestClient(main_mod.app) as client:
            # Startup finished and serves requests while the build is still running.
            assert started.wait(10)
            assert client.get("/health").status_code == 200
            release.set()


def test_ruler_build_failure_is_logged_not_fatal(caplog):
    built = threading.Event()

    def broken_builder(ontology_id):
        built.set()
        raise RuntimeError("boom")

    ollama, embed = _quiet_startup()
    with ollama, embed, patch.object(ers, "_get_ruler_bundle", side_effect=broken_builder):
        with caplog.at_level("WARNING", logger="app.main"):
            with TestClient(main_mod.app) as client:
                assert built.wait(10)
                assert client.get("/health").status_code == 200
    assert any("EntityRuler warm-up failed" in r.getMessage() for r in caplog.records)
