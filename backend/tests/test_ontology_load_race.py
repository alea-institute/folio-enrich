"""Offline regression coverage for concurrent ontology initialization and writes."""

import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.folio import folio_service as fs_mod
from app.services.folio.folio_service import FolioService
from app.services.ontology import ingestion
from app.services.ontology.spec import CANON_SPEC


def test_concurrent_lazy_load_publishes_complete_service(monkeypatch):
    service = FolioService()
    folio = SimpleNamespace(classes=[])
    start = threading.Barrier(5)
    loads = []
    building = threading.Event()
    finish_build = threading.Event()

    def load(self):
        loads.append(1)
        time.sleep(0.05)
        return folio

    def build(self):
        building.set()
        assert finish_build.wait(5), "branch build was not released"
        self._branch_map = {"root": "Root"}

    monkeypatch.setattr(FolioService, "_load_folio", load)
    monkeypatch.setattr(FolioService, "_build_branch_map", build)

    def get():
        start.wait(timeout=5)
        result = service._get_folio()
        assert service._branch_map == {"root": "Root"}
        return result

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(get) for _ in range(5)]
        try:
            assert building.wait(5), "branch build did not start"
            assert service._folio is None  # No half-built object on the fast path.
        finally:
            finish_build.set()
        results = [future.result(timeout=5) for future in futures]

    assert len(loads) == 1
    assert all(result is folio for result in results)
    assert service._get_folio() is folio
    assert len(loads) == 1


def _stub_http(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from folio import FOLIO

    data = b"<validated-owl/>"
    monkeypatch.setattr(ingestion, "fetch_and_validate_owl", lambda *a, **kw: (data, "sha"))
    monkeypatch.setattr(ingestion, "assert_label_coverage", lambda *a: None)
    cache_hash = hashlib.blake2b(CANON_SPEC.coords.owl_url.encode()).hexdigest()
    cache_file = tmp_path / ".folio" / "cache" / "http" / f"{cache_hash}.owl"

    def read_cache(**kwargs):
        assert cache_file.read_bytes() == data
        return data.decode()

    monkeypatch.setattr(FOLIO, "load_cache", read_cache)
    monkeypatch.setattr(fs_mod, "_construct_folio", lambda **kw: object())
    return data, cache_file


def test_concurrent_http_cache_writers_use_unique_temps(monkeypatch, tmp_path):
    data, cache_file = _stub_http(monkeypatch, tmp_path)
    # Force both writers to finish writing before either publishes. The old shared
    # .tmp name then reliably loses one writer's file at the first replacement.
    ready = threading.Barrier(2)
    original_os_replace = os.replace

    def os_replace(source, target):
        ready.wait(timeout=5)
        return original_os_replace(source, target)

    monkeypatch.setattr(os, "replace", os_replace)
    services = [FolioService(CANON_SPEC), FolioService(CANON_SPEC)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(svc._load_http_via_hardened_ingestion, CANON_SPEC.coords)
                   for svc in services]
        results = [future.result(timeout=5) for future in futures]
    assert len(results) == 2
    assert cache_file.read_bytes() == data
    assert not list(tmp_path.rglob("*.tmp"))


def test_http_cache_temp_is_removed_on_replace_failure(monkeypatch, tmp_path):
    _, cache_file = _stub_http(monkeypatch, tmp_path)

    def fail_replace(*args):
        raise OSError("replacement failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        FolioService(CANON_SPEC)._load_http_via_hardened_ingestion(CANON_SPEC.coords)
    assert not cache_file.exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_reload_serializes_with_cold_load(monkeypatch):
    service = FolioService()
    folio = SimpleNamespace(classes=[])
    loading = threading.Event()
    finish = threading.Event()
    reader_started = threading.Event()
    loads = []

    def load(self):
        loads.append(1)
        loading.set()
        assert finish.wait(5), "reload was not released"
        return folio

    monkeypatch.setattr(FolioService, "_load_folio", load)
    monkeypatch.setattr(FolioService, "_build_branch_map",
                        lambda self: setattr(self, "_branch_map", {"root": "Root"}))
    monkeypatch.setattr(FolioService, "get_all_labels", lambda self: {})
    monkeypatch.setattr(FolioService, "get_all_labels_multi", lambda self: {})
    monkeypatch.setattr(FolioService, "get_all_property_labels", lambda self: {})

    def read():
        reader_started.set()
        return service._get_folio()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reload = pool.submit(service._reload)
        try:
            assert loading.wait(5)
            reader = pool.submit(read)
            assert reader_started.wait(5)
            time.sleep(0.05)
            assert not reader.done()
            assert len(loads) == 1
        finally:
            finish.set()
        assert reload.result(timeout=5) == {"concepts_before": 0, "concepts_after": 0}
        assert reader.result(timeout=5) is folio
    assert len(loads) == 1
    assert service._branch_map == {"root": "Root"}
