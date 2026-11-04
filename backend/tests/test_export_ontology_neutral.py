"""AC-1: exports must be ontology-neutral.

A Canon job must never leak the FOLIO base IRI/namespace into any of the 13 export
formats, and a FOLIO job must still carry FOLIO IRIs — proving the neutralization is
driven by the job's ontology, not a blanket string-strip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.job import Job
from app.services.export.registry import get_exporter, list_formats

_DEMOS = Path(__file__).resolve().parents[2] / "frontend" / "demos"
_FOLIO_BASE_IRI = b"folio.openlegalstandard.org"


def _load_job(rel_path: str) -> Job:
    data = json.loads((_DEMOS / rel_path).read_text())
    return Job.model_validate(data["cache"]["job"])


def _as_bytes(output) -> bytes:
    return output if isinstance(output, bytes) else output.encode("utf-8")


ALL_FORMATS = list_formats()


@pytest.fixture(scope="module")
def canon_job() -> Job:
    return _load_job("canon/sacraments.json")


@pytest.fixture(scope="module")
def folio_job() -> Job:
    return _load_job("nda.json")


def test_canon_job_loads_as_canon(canon_job: Job) -> None:
    assert canon_job.result.ontology_id == "canon"
    assert canon_job.result.base_iri == "https://ontology.catholicos.catholic/"


def test_folio_job_loads_as_folio(folio_job: Job) -> None:
    assert folio_job.result.ontology_id == "folio"
    assert folio_job.result.base_iri == "https://folio.openlegalstandard.org/"


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_canon_export_has_no_folio_base_iri(canon_job: Job, fmt: str) -> None:
    output = _as_bytes(get_exporter(fmt).export(canon_job))
    assert _FOLIO_BASE_IRI not in output, (
        f"Canon {fmt} export leaked the FOLIO base IRI"
    )


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_folio_export_still_has_folio_base_iri(folio_job: Job, fmt: str) -> None:
    # Formats that embed concept IRIs must still carry FOLIO IRIs for a FOLIO job.
    # A few formats (e.g. plain triples-only shapes) may legitimately omit them, so
    # we only assert presence for the IRI-bearing serializations.
    output = _as_bytes(get_exporter(fmt).export(folio_job))
    if fmt in {"json", "jsonld", "xml", "rdf", "csv", "neo4j", "html", "elasticsearch"}:
        assert _FOLIO_BASE_IRI in output, (
            f"FOLIO {fmt} export unexpectedly dropped FOLIO IRIs"
        )


from tests.test_union_service import union_registry


@pytest.fixture
async def both_job(union_registry, monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from app.config import settings
    from app.models.document import DocumentInput
    from app.pipeline.orchestrator import PipelineOrchestrator
    from app.services.embedding.service import EmbeddingService
    from app.services.ontology.bridges import load_bridges
    from app.storage.job_store import JobStore
    bridge = next(b for b in load_bridges()["bridges"]
                  if b["canon_label"].startswith("Commandment 07") and b["folio_label"] == "Fraud")
    for oid in ("canon", "folio"):
        service = union_registry.get_service(oid)
        graph = service._get_folio()
        only = next(c for c in graph.classes if c.label == oid)
        only.iri = service.spec.base_iri + bridge[f"{oid}_hash"]
        emb = EmbeddingService()
        emb._ontology_id = oid
        union_registry._embedding_services[oid] = emb
    for key in ("ner_cross_validation_enabled", "pos_tagging_enabled", "triple_extraction_enabled"):
        monkeypatch.setattr(settings, key, False)
    monkeypatch.setattr(settings, "individual_regex_only", True)
    monkeypatch.setattr(settings, "property_regex_only", True)
    monkeypatch.setattr("app.services.individual.citation_extractor.CitationExtractor.extract", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.services.individual.entity_extractors.EntityExtractorRunner.extract", AsyncMock(return_value=[]))
    job = await PipelineOrchestrator(JobStore(base_dir=tmp_path), llm=None).run(
        Job(input=DocumentInput(content="shared canon folio", ontology="both")))
    assert job.status.value == "completed", job.error
    return job


def _read_export(fmt, output):
    import io
    if fmt == "excel":
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(output))
        return str({ws.title: list(ws.values) for ws in wb})
    if fmt == "parquet":
        import pyarrow.parquet as pq
        table = pq.read_table(io.BytesIO(output))
        return str(table.to_pylist()) + str(table.schema.metadata)
    return output


@pytest.mark.parametrize("fmt", ALL_FORMATS)
async def test_both_exports_regions_peers_and_bridges(both_job, fmt):
    text = _read_export(fmt, get_exporter(fmt).export(both_job))
    assert "https://folio.openlegalstandard.org/" in text
    assert "https://ontology.catholicos.catholic/" in text
    for region in ("shared", "canon_only", "folio_only"):
        assert region in text
    assert "peer_iri" in text
    assert "bridges" in text
    assert "Commandment 07" in text
    assert "matched_on" in text


async def test_both_linked_data_namespaces(both_job):
    from rdflib import Graph, Namespace, RDF
    output = json.loads(get_exporter("jsonld").export(both_job))
    assert output["@context"]["folio"] == "https://folio.openlegalstandard.org/"
    assert output["@context"]["canon"] == "https://ontology.catholicos.catholic/"
    assert output["@context"]["enrich"] == "urn:folio-enrich:"
    graph = Graph().parse(data=get_exporter("rdf").export(both_job), format="turtle")
    ns = Namespace("urn:folio-enrich:")
    assert list(graph.triples((None, ns.region, None)))
    assert list(graph.triples((None, ns.bridges, None)))
    assert not any(str(p).startswith("https://folio.openlegalstandard.org/") for _, p, _ in graph)


async def test_both_parquet_preserves_concepts_alongside_individuals(both_job):
    import io
    import pyarrow.parquet as pq
    from app.models.annotation import Individual, Span
    both_job.result.individuals.append(Individual(name="Thomas", mention_text="Thomas", span=Span(start=0, end=6, text="Thomas")))
    table = pq.read_table(io.BytesIO(get_exporter('parquet').export(both_job)))
    assert {r['region'] for r in table.to_pylist() if r.get('record_type') == 'concept'} == {'shared', 'canon_only', 'folio_only'}
    assert any(r.get('name') == 'Thomas' for r in table.to_pylist())
    assert 'Commandment 07' in table.schema.metadata[b'bridges'].decode()
