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
    if not canon_file.is_file() or not _CACHE_FILE.is_file():
        pytest.skip("Both cached OWLs are required")
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


@pytest.mark.parametrize("endpoints,expected", [(["canon"], ["canon"]), (["folio"], ["folio"]), (["canon", "folio"], ["canon", "folio"]), ([], None)])
async def test_attach_only_curated_bridges(endpoints, expected):
    from app.models.annotation import Annotation, ConceptMatch, Span
    from app.models.job import Job
    from app.pipeline.stages.metadata_stage import MetadataStage
    item = next(b for b in load_bridges()["bridges"]
                if b["canon_label"].startswith("Commandment 07") and b["folio_label"] == "Fraud")
    job = Job()
    job.result.ontology_id = "both"
    concepts = [ConceptMatch(concept_text=oid, folio_iri=(CANON_SPEC if oid == "canon" else FOLIO_SPEC).base_iri + item[f"{oid}_hash"], region=f"{oid}_only") for oid in endpoints]
    concepts.append(ConceptMatch(concept_text="unbridged", folio_iri=CANON_SPEC.base_iri + "unbridged", region="canon_only"))
    job.result.annotations = [Annotation(span=Span(start=0, end=1, text="x"), concepts=concepts)]
    await MetadataStage(None).execute(job)
    matches = [b for b in job.result.bridges if b["canon_hash"] == item["canon_hash"] and b["folio_hash"] == item["folio_hash"]]
    assert (matches[0]["matched_on"] if matches else None) == expected
    assert all(b["canon_hash"] != "unbridged" for b in job.result.bridges)
    assert "matched_on" not in item


async def test_single_metadata_omits_bridges():
    from app.models.job import Job
    from app.pipeline.stages.metadata_stage import MetadataStage
    job = await MetadataStage(None).execute(Job())
    assert "bridges" not in job.result.model_dump()


def test_commandment_seven_has_larceny_and_fraud():
    targets = {b['folio_label'] for b in load_bridges()['bridges']
               if b['canon_label'].startswith('Commandment 07')}
    assert {'Larceny', 'Fraud'} <= targets


@pytest.mark.slow
@pytest.mark.timeout(180)
async def test_aquinas_offline_pipeline_attaches_legal_endpoints(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from app.config import settings
    from app.models.document import DocumentInput
    from app.models.job import Job
    from app.pipeline.orchestrator import PipelineOrchestrator
    from app.services.embedding.service import EmbeddingService
    from app.services.ontology.registry import OntologyRegistry
    from app.storage.job_store import JobStore
    index, services = cached_world(monkeypatch, tmp_path)
    registry = OntologyRegistry({'folio': FOLIO_SPEC, 'canon': CANON_SPEC})
    registry._services.update(services)
    import app.services.ontology.registry as module
    monkeypatch.setattr(module, '_registry', registry)
    for oid in ('canon', 'folio'):
        emb = EmbeddingService()
        emb._ontology_id = oid
        registry._embedding_services[oid] = emb
    for key in ('ner_cross_validation_enabled', 'pos_tagging_enabled', 'triple_extraction_enabled'):
        monkeypatch.setattr(settings, key, False)
    monkeypatch.setattr(settings, 'individual_regex_only', True)
    monkeypatch.setattr(settings, 'property_regex_only', True)
    monkeypatch.setattr('app.services.individual.citation_extractor.CitationExtractor.extract', AsyncMock(return_value=[]))
    monkeypatch.setattr('app.services.individual.entity_extractors.EntityExtractorRunner.extract', AsyncMock(return_value=[]))
    excerpt = "Theft is the secret taking of another's property, while robbery is the violent taking of it. Larceny and fraud are punished by human law, and restitution is owed to the person who was robbed."
    job = await PipelineOrchestrator(JobStore(base_dir=tmp_path), llm=None).run(
        Job(input=DocumentInput(content=excerpt, ontology='both')))
    assert job.status.value == 'completed', job.error
    for label in ('Larceny', 'Fraud'):
        assert any(b['canon_label'].startswith('Commandment 07')
                   and b['folio_label'] == label and 'folio' in b['matched_on']
                   for b in job.result.bridges)
