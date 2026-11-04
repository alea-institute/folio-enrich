"""Curated bridge validity and the Canon pin-bump work queue."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.ontology.bridges import load_bridges, validate
from app.services.ontology.overlap import OverlapIndex, OverlapRecord
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC
from scripts import bridge_queue


def bridge():
    return dict(canon_hash="C1", canon_label="Moral concept", folio_hash="F1",
                folio_label="Legal concept", match_type="related",
                rationale="The concepts overlap.", review_status="model")


def world():
    index = SimpleNamespace(entries={
        "C1": OverlapRecord("C1", "canon_only", canon_iri=CANON_SPEC.base_iri + "C1",
                            canon_label="Moral concept"),
        "F1": OverlapRecord("F1", "folio_only", folio_iri=FOLIO_SPEC.base_iri + "F1"),
    })
    index.lookup = index.entries.get
    services = {}
    for spec, key in [(CANON_SPEC, "C1"), (FOLIO_SPEC, "F1")]:
        concepts = {spec.base_iri + key: SimpleNamespace(deprecated=False)}
        services[spec.id] = SimpleNamespace(spec=spec, concepts=concepts,
                                             get_concept=concepts.get)
    return index, services


def test_valid_bridge():
    index, services = world()
    assert validate([bridge()], index, services) == []


@pytest.mark.parametrize("ontology,key", [("canon", "C1"), ("folio", "F1")])
def test_missing_endpoint_names_bridge(ontology, key):
    index, services = world()
    services[ontology].concepts.clear()
    problems = validate([bridge()], index, services)
    assert any(ontology in p.lower() and "missing" in p.lower()
               and "C1" in p and "F1" in p for p in problems)


@pytest.mark.parametrize("ontology,key", [("canon", "C1"), ("folio", "F1")])
def test_deprecated_endpoint(ontology, key):
    index, services = world()
    services[ontology].concepts[services[ontology].spec.base_iri + key].deprecated = True
    # Deprecated endpoints may have already disappeared from the overlap index.
    del index.entries[key]
    assert any(ontology in p.lower() and "deprecated" in p.lower()
               for p in validate([bridge()], index, services))


def test_canon_endpoint_became_shared():
    index, services = world()
    index.entries["C1"] = OverlapRecord("C1", "shared", canon_iri=CANON_SPEC.base_iri + "C1")
    assert any("canon_only" in p for p in validate([bridge()], index, services))


@pytest.mark.parametrize("field,value", [("match_type", "exact"), ("review_status", "unreviewed")])
def test_invalid_metadata(field, value):
    index, services = world()
    item = bridge()
    item[field] = value
    assert any(field in p for p in validate([item], index, services))


def test_committed_bridge_data():
    data = load_bridges()
    assert data is load_bridges()
    assert data["canon_pin"] == CANON_SPEC.coords.owl_sha256
    assert data["folio_pin"] == "44657b4ed844f5f9c9c48869184606b4fc671471a8263d79d241de87809fa239"
    baseline = data["evaluated_canon_only"]
    assert baseline == sorted(set(baseline))
    assert 40 <= len(data["bridges"]) <= 60
    for item in data["bridges"]:
        assert set(bridge()) <= item.keys()
        assert all(isinstance(item[field], str) and item[field].strip() for field in bridge())
        assert item["canon_hash"] in baseline
        assert item["review_status"] in {"model", "damien"}
        assert item["match_type"] in {"close", "related"}


@pytest.mark.parametrize("has_new", [True, False])
def test_queue_lists_only_unevaluated_canon_only(monkeypatch, capsys, has_new):
    index, _ = world()
    index.entries["S1"] = OverlapRecord("S1", "shared", canon_label="Shared concept")
    if has_new:
        index.entries["C2"] = OverlapRecord("C2", "canon_only", canon_label="New moral concept")
    monkeypatch.setattr(bridge_queue, "get_overlap_index", lambda: index)
    monkeypatch.setattr(bridge_queue, "load_bridges", lambda: {"evaluated_canon_only": ["C1"]})
    assert bridge_queue.main() == 0
    assert capsys.readouterr().out == ("C2\tNew moral concept\n1 Canon-only concepts queued\n"
                                           if has_new else "0 Canon-only concepts queued\n")


def cached_world(monkeypatch, tmp_path):
    """Parse cached OWLs through the real services, with no network or home writes."""
    from app.services.folio.folio_service import FolioService
    from app.services.folio.owl_cache import _CACHE_FILE
    from app.services.ontology.registry import OntologyRegistry

    canon_file = Path.home() / ".folio/cache/http" / (
        hashlib.blake2b(CANON_SPEC.coords.owl_url.encode()).hexdigest() + ".owl")
    assert canon_file.is_file() and _CACHE_FILE.is_file(), "Both cached OWLs are required"
    assert hashlib.sha256(canon_file.read_bytes()).hexdigest() == CANON_SPEC.coords.owl_sha256
    assert hashlib.sha256(_CACHE_FILE.read_bytes()).hexdigest() == load_bridges()["folio_pin"]
    import logging.handlers
    handler = logging.handlers.RotatingFileHandler
    with monkeypatch.context() as patch:
        patch.setattr(logging.handlers, "RotatingFileHandler",
                      lambda filename, **kw: handler(tmp_path / "alea.log", **kw))
        from folio import FOLIO

    def load_cached(self):
        path = canon_file if self.spec.id == "canon" else _CACHE_FILE
        with monkeypatch.context() as patch:
            patch.setattr(FOLIO, "load_owl", staticmethod(lambda **kw: path.read_text()))
            return FOLIO(llm=SimpleNamespace())

    monkeypatch.setattr(FolioService, "_load_folio", load_cached)
    registry = OntologyRegistry({"folio": FOLIO_SPEC, "canon": CANON_SPEC})
    return OverlapIndex(registry), {key: registry.get_service(key) for key in ("canon", "folio")}


@pytest.mark.slow
@pytest.mark.timeout(120)
def test_committed_bridges_against_cached_ontologies(monkeypatch, tmp_path):
    index, services = cached_world(monkeypatch, tmp_path)
    data = load_bridges()
    assert validate(data["bridges"], index, services) == []
    assert data["evaluated_canon_only"] == sorted(
        key for key, record in index.entries.items() if record.region == "canon_only")
