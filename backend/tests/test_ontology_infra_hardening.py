"""WS-3: internal infra hardening for the multi-ontology system.

Covers, all offline (no OWL load / no network):
- 3a: FolioService._reload() invalidates the derived branch-detail cache.
- 3b: _reload() is build-then-swap — it rebinds fields to freshly built ones.
- 3c: the registry evicts the LRU NON-default ontology past the ceiling, never
      the default.
- 3e: set_registry/reset_registry inject a registry cleanly through the accessors.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from app.services.folio import folio_service as fs_mod
from app.services.folio.folio_service import FolioService
from app.services.llm.prompts import templates
from app.services.ontology.registry import (
    OntologyRegistry,
    get_registry,
    reset_registry,
    set_registry,
)
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC


# --------------------------------------------------------------------------- 3a/3b


def _stub_reload_builders(monkeypatch, new_folio):
    """Make _reload run offline: _load_folio returns new_folio; the cache builders
    populate the instance's caches with sentinels (so we can assert the swap)."""
    monkeypatch.setattr(FolioService, "_load_folio", lambda self: new_folio)
    monkeypatch.setattr(FolioService, "_build_branch_map",
                        lambda self: setattr(self, "_branch_map", {"b": "B"}))

    def _labels(self):
        self._labels_cache = {"l": "sentinel"}
        return self._labels_cache

    def _labels_multi(self):
        self._labels_multi_cache = {"l": ["sentinel"]}
        return self._labels_multi_cache

    def _prop_labels(self):
        self._property_labels_cache = {"p": "sentinel"}
        return self._property_labels_cache

    monkeypatch.setattr(FolioService, "get_all_labels", _labels)
    monkeypatch.setattr(FolioService, "get_all_labels_multi", _labels_multi)
    monkeypatch.setattr(FolioService, "get_all_property_labels", _prop_labels)


def test_reload_clears_branch_detail_cache(monkeypatch):
    new_folio = SimpleNamespace(classes=[1, 2, 3])
    _stub_reload_builders(monkeypatch, new_folio)

    svc = FolioService(FOLIO_SPEC)
    svc._folio = SimpleNamespace(classes=[1])
    templates._BRANCH_DETAIL_CACHE["folio"] = "STALE"
    templates._BRANCH_DETAIL_CACHE["canon"] = "keep me"
    try:
        svc._reload()
        # Only this ontology's derived branch string is dropped; others untouched.
        assert "folio" not in templates._BRANCH_DETAIL_CACHE
        assert templates._BRANCH_DETAIL_CACHE.get("canon") == "keep me"
    finally:
        templates._BRANCH_DETAIL_CACHE.pop("canon", None)


def test_reload_is_build_then_swap(monkeypatch):
    new_folio = SimpleNamespace(classes=[1, 2, 3])
    _stub_reload_builders(monkeypatch, new_folio)

    svc = FolioService(FOLIO_SPEC)
    old_folio = SimpleNamespace(classes=[1])
    svc._folio = old_folio
    svc._search_cache[("x", "", 1)] = ["stale"]

    stats = svc._reload()

    # Fields rebound to the freshly built objects (swapped, not left half-built).
    assert svc._folio is new_folio
    assert svc._branch_map == {"b": "B"}
    assert svc._labels_cache == {"l": "sentinel"}
    assert svc._labels_multi_cache == {"l": ["sentinel"]}
    assert svc._property_labels_cache == {"p": "sentinel"}
    assert svc._lemma_map is None          # rebuilt lazily, re-keyed to new owl_hash
    assert svc._search_cache == {}         # stale entries dropped
    assert stats == {"concepts_before": 1, "concepts_after": 3}


def test_clear_branch_detail_cache_all(monkeypatch):
    templates._BRANCH_DETAIL_CACHE["folio"] = "a"
    templates._BRANCH_DETAIL_CACHE["canon"] = "b"
    templates.clear_branch_detail_cache(None)
    assert templates._BRANCH_DETAIL_CACHE == {}


# ------------------------------------------------------------------------------- 3c


def _fake_spec(spec_id: str):
    # A distinct spec id reusing FOLIO's shape — get_service only *constructs* a
    # FolioService (lazy, no load), so the coords are never fetched in this test.
    return dataclasses.replace(FOLIO_SPEC, id=spec_id, display_name=spec_id)


def test_lru_eviction_drops_least_recently_used_non_default(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_resident_ontologies", 1)
    specs = {"folio": FOLIO_SPEC, "one": _fake_spec("one"), "two": _fake_spec("two")}
    reg = OntologyRegistry(specs, default_id="folio")

    reg.get_service("folio")
    reg.get_service("one")
    # Pin 'one' as strictly older than whatever 'two' gets on build.
    reg._last_access["one"] = 1.0
    reg.get_service("two")  # building 'two' pushes non-default resident to 2 > 1

    assert "two" in reg._services         # most recent non-default kept
    assert "one" not in reg._services     # LRU non-default evicted
    assert "folio" in reg._services       # default never evicted


def test_default_ontology_is_never_evicted(monkeypatch):
    from app.config import settings

    # Ceiling 0 => every NON-default is evicted, but the default must survive.
    monkeypatch.setattr(settings, "max_resident_ontologies", 0)
    specs = {"folio": FOLIO_SPEC, "one": _fake_spec("one")}
    reg = OntologyRegistry(specs, default_id="folio")

    reg.get_service("folio")
    reg.get_service("one")

    assert "one" not in reg._services
    assert "folio" in reg._services


# ------------------------------------------------------------------------------- 3e


def test_set_and_reset_registry_inject_cleanly():
    try:
        custom = OntologyRegistry({"folio": FOLIO_SPEC, "canon": CANON_SPEC},
                                  default_id="folio")
        set_registry(custom)

        # Every accessor now resolves to the injected registry.
        assert get_registry() is custom
        assert FolioService.get_instance() is custom.get_service("folio")

        # reset_registry drops it; the next access rebuilds a fresh one from settings.
        reset_registry()
        rebuilt = get_registry()
        assert rebuilt is not custom
    finally:
        # Leave the process-global in a from-settings state for the rest of the suite.
        reset_registry()
