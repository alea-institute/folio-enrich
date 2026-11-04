"""Overlap membership and drift through resident ontology registries."""
from types import SimpleNamespace
from pathlib import Path
import hashlib

import pytest

from app.services.folio.folio_service import FolioService
from app.services.ontology.registry import OntologyRegistry, reset_registry, set_registry
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC
from app.services.ontology.overlap import get_overlap_index


class _FakeFolio:
    def __init__(self, classes):
        self.classes = classes
        self._classes = {c.iri: c for c in classes}

    def __getitem__(self, iri):
        return self._classes.get(iri)

    def get_parents(self, iri):
        return []

    def get_folio_branches(self):
        return {}


def _cls(spec, key, label="Same", definition="Definition", **kw):
    return SimpleNamespace(iri=spec.base_iri + key, label=label,
                           definition=definition, sub_class_of=[], **kw)


@pytest.fixture(autouse=True)
def restore_registry():
    import app.services.ontology.registry as module
    previous = module._registry
    yield
    set_registry(previous)


def _install(monkeypatch, folio, canon):
    graphs = {"folio": _FakeFolio(folio), "canon": _FakeFolio(canon)}
    monkeypatch.setattr(FolioService, "_load_folio", lambda self: graphs[self.spec.id])
    registry = OntologyRegistry({"folio": FOLIO_SPEC, "canon": CANON_SPEC})
    set_registry(registry)
    return registry


def test_regions_drift_and_raw_labels(monkeypatch):
    _install(monkeypatch, [
        _cls(FOLIO_SPEC, "A1", "  Shared\n label "),
        _cls(FOLIO_SPEC, "F1"),
        _cls(FOLIO_SPEC, "L1", "Authority"),
        _cls(FOLIO_SPEC, "D1"),
    ], [
        _cls(CANON_SPEC, "A1", "Shared label"),
        _cls(CANON_SPEC, "C1"),
        _cls(CANON_SPEC, "L1", "Authority (Source and Scope)"),
        _cls(CANON_SPEC, "D1", definition="Changed definition"),
        SimpleNamespace(iri="http://webprotege.stanford.edu/External", label="External",
                        definition="", sub_class_of=[]),
    ])
    index = get_overlap_index()
    shared = index.lookup("A1")
    assert shared.region == "shared" and not shared.drifted
    assert shared.folio_iri == FOLIO_SPEC.base_iri + "A1"
    assert shared.canon_iri == CANON_SPEC.base_iri + "A1"
    assert index.lookup("F1").region == "folio_only"
    assert index.lookup("C1").region == "canon_only"
    assert index.lookup("C1").folio_label is None
    assert index.lookup("External").region == "canon_only"
    label = index.lookup("L1")
    assert label.drifted and label.label_drift and not label.definition_drift
    assert (label.folio_label, label.canon_label) == ("Authority", "Authority (Source and Scope)")
    definition = index.lookup("D1")
    assert definition.drifted and definition.definition_drift and not definition.label_drift
    assert index.lookup("absent") is None
    assert index.summary() == dict(shared=3, folio_only=1, canon_only=2,
                                   label_drifted=1, definition_drifted=1)
    assert get_overlap_index() is index


def test_exclusions_and_registry_replacement(monkeypatch):
    canon_root = _cls(CANON_SPEC, "Hidden", "ZZZZ - Deprecated")
    child = _cls(CANON_SPEC, "Child")
    child.sub_class_of = [canon_root.iri]
    registry = _install(monkeypatch, [
        _cls(FOLIO_SPEC, "A1", deprecated=True),
        _cls(FOLIO_SPEC, "Child"),
    ], [_cls(CANON_SPEC, "A1"), canon_root, child])
    assert all(service._folio is None for service in registry._services.values())
    first = get_overlap_index()
    set_registry(registry)
    assert get_overlap_index() is not first
    assert first.lookup("A1").region == "canon_only"
    assert first.lookup("Hidden") is None
    assert first.lookup("Child").region == "folio_only"
    _install(monkeypatch, [_cls(FOLIO_SPEC, "New")], [_cls(CANON_SPEC, "New")])
    assert get_overlap_index().lookup("A1") is None
    assert get_overlap_index().lookup("New").region == "shared"
    reset_registry()
    monkeypatch.setattr(OntologyRegistry, "from_settings", classmethod(lambda cls: registry))
    assert get_overlap_index().lookup("A1").region == "canon_only"


@pytest.mark.slow
def test_cached_real_ontology_overlap(monkeypatch, tmp_path):
    from app.services.folio.owl_cache import _CACHE_FILE

    canon_file = Path.home() / ".folio/cache/http" / (
        hashlib.blake2b(CANON_SPEC.coords.owl_url.encode()).hexdigest() + ".owl")
    if not _CACHE_FILE.is_file() or not canon_file.is_file():
        pytest.skip("Both cached ontology OWLs are required")

    # The dependency initializes a home-directory log at import time.
    import logging.handlers
    handler = logging.handlers.RotatingFileHandler
    with monkeypatch.context() as patch:
        patch.setattr(logging.handlers, "RotatingFileHandler",
                      lambda filename, **kw: handler(tmp_path / "alea.log", **kw))
        from folio import FOLIO

    # Use the real registry and parser, reading cached bytes without ingestion/network.
    def load_cached(self):
        path = canon_file if self.spec.id == "canon" else _CACHE_FILE
        with monkeypatch.context() as patch:
            patch.setattr(FOLIO, "load_owl", staticmethod(lambda **kw: path.read_text()))
            return FOLIO(llm=SimpleNamespace())

    monkeypatch.setattr(FolioService, "_load_folio", load_cached)
    set_registry(OntologyRegistry({"folio": FOLIO_SPEC, "canon": CANON_SPEC}))
    index = get_overlap_index()
    counts = index.summary()
    definition_only = sum(r.definition_drift and not r.label_drift for r in index.entries.values())
    print(f"Overlap counts: {counts}; definition_only={definition_only}")
    assert counts["shared"] == 14407
    assert counts["label_drifted"] == 12
    assert counts["definition_drifted"] == 7
    assert definition_only == 5

    # Excluded Canon labels must not drop the entire deterministic stage.
    import asyncio
    from app.models.document import CanonicalText, DocumentInput
    from app.models.job import Job
    from app.pipeline.stages.entity_ruler_stage import EntityRulerStage
    from app.services.ontology.registry import get_registry

    union = get_registry().get_service('both')
    labels = union.get_all_labels_multi()
    entries = [entry for bucket in labels.values() for entry in bucket]
    with_region = sum(getattr(entry.concept, 'region', None) is not None for entry in entries)
    print(f'Union labels={len(labels)}; entries with region={with_region}; without region={len(entries) - with_region}')
    assert with_region == len(entries)
    assert all(labels.values())
    text = 'We pray the Marian Rosary. The SALI Ontology describes theft.'
    job = Job(input=DocumentInput(content=text, ontology='both'))
    job.result.canonical_text = CanonicalText(full_text=text)
    asyncio.run(EntityRulerStage().execute(job))
    concepts = [c for a in job.result.annotations for c in a.concepts]
    assert concepts
    assert all(c.region for c in concepts)
    print(f'EntityRuler completed: {len(concepts)} concepts; matches={[c.concept_text for c in concepts]}')
