"""Phase 2a: ontology threaded request -> job -> result, plus /ontologies routes.

Offline — no pipeline run or OWL load required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.enrich import EnrichRequest
from app.main import app
from app.models.document import DocumentInput
from app.models.job import Job
from app.pipeline.orchestrator import PipelineOrchestrator

client = TestClient(app)


class TestEnrichRequestOntology:
    def test_default_is_folio(self):
        assert EnrichRequest(content="x").ontology == "folio"

    def test_valid_ontology_accepted(self):
        assert EnrichRequest(content="x", ontology="folio").ontology == "folio"

    def test_empty_falls_back_to_default(self):
        assert EnrichRequest(content="x", ontology="").ontology == "folio"

    def test_canon_accepted(self):
        # canon is enabled as of PR #14 -> passes validation
        assert EnrichRequest(content="x", ontology="canon").ontology == "canon"

    def test_unknown_rejected(self):
        # an id with no spec is still a deterministic rejection
        with pytest.raises(ValidationError):
            EnrichRequest(content="x", ontology="bogus")


class TestJobOntologyProperty:
    def test_none_input_defaults_to_folio(self):
        assert Job().ontology == "folio"  # input is None

    def test_reads_from_input(self):
        job = Job(input=DocumentInput(content="x", ontology="folio"))
        assert job.ontology == "folio"

    def test_document_input_defaults_to_folio(self):
        assert DocumentInput(content="x").ontology == "folio"


class TestResultStamping:
    def test_stamps_from_input(self):
        job = Job(input=DocumentInput(content="x", ontology="folio"))
        PipelineOrchestrator._stamp_ontology(job)
        assert job.result.ontology_id == "folio"
        assert job.result.ontology_name == "FOLIO"
        assert job.result.base_iri == "https://folio.openlegalstandard.org/"

    def test_stamps_default_when_input_missing(self):
        job = Job()
        PipelineOrchestrator._stamp_ontology(job)
        assert job.result.ontology_id == "folio"

    def test_jobresult_defaults_are_folio(self):
        # legacy persisted jobs (no ontology fields) deserialize/export as FOLIO
        job = Job()
        assert job.result.ontology_id == "folio"
        assert job.result.base_iri == "https://folio.openlegalstandard.org/"


class TestOntologiesRoutes:
    def test_list_ontologies(self):
        r = client.get("/ontologies")
        assert r.status_code == 200
        body = r.json()
        assert body["default"] == "folio"
        assert "embeddings_available" in body
        ids = [o["id"] for o in body["ontologies"]]
        assert ids == ["folio", "canon"]  # canon enabled as of PR #14
        folio = body["ontologies"][0]
        assert folio["display_name"] == "FOLIO"
        assert folio["default"] is True
        canon = body["ontologies"][1]
        assert canon["display_name"] == "Catholic Semantic Canon"
        assert canon["default"] is False

    def test_get_folio(self):
        r = client.get("/ontologies/folio")
        assert r.status_code == 200
        assert r.json()["base_iri"] == "https://folio.openlegalstandard.org/"

    def test_get_canon_enabled(self):
        # canon is enabled as of PR #14 -> metadata returned, not 404
        r = client.get("/ontologies/canon")
        assert r.status_code == 200
        assert r.json()["base_iri"] == "https://ontology.catholicos.catholic/"

    def test_get_unknown_ontology_404(self):
        r = client.get("/ontologies/bogus")
        assert r.status_code == 404
        assert "Enabled" in r.json()["detail"]


class TestEnrichRouteOntologyBoundary:
    def test_post_enrich_rejects_unknown_ontology_422(self):
        # End-to-end: a bad ontology is a 422 at the route, not a 500 deep in the pipeline
        r = client.post("/enrich", json={"content": "hello", "ontology": "bogus"})
        assert r.status_code == 422
        assert "folio" in r.text  # enabled list surfaced in the error


async def test_both_request_stamping_and_mode(client):
    assert EnrichRequest(content='x', ontology='both').ontology == 'both'
    job = Job(input=DocumentInput(content='x', ontology='both'))
    PipelineOrchestrator._stamp_ontology(job)
    assert job.result.ontology_id == 'both'
    assert job.result.ontology_name == 'FOLIO + Catholic Semantic Canon'
    assert job.result.base_iri == 'https://folio.openlegalstandard.org/'
    assert job.result.peer_base_iri == 'https://ontology.catholicos.catholic/'
    payload = (await client.get('/ontologies')).json()
    assert payload['modes'] == [{'id': 'both', 'display_name': 'Enrich against both', 'default': False}]
    assert payload['default'] == 'folio'


@pytest.mark.parametrize('ontology', ['folio', 'canon'])
def test_single_ontology_omits_peer_base_iri(ontology):
    job = Job(input=DocumentInput(content='x', ontology=ontology))
    PipelineOrchestrator._stamp_ontology(job)
    assert 'peer_base_iri' not in job.model_dump(mode='json')
    assert 'peer_base_iri' not in job.model_dump(mode='json')['result']
    assert 'peer_base_iri' not in job.model_dump_json()


@pytest.mark.parametrize('unavailable', [None, 'canon', 'folio'])
async def test_both_start_boundary(monkeypatch, tmp_path, unavailable, client):
    from app.api.routes import enrich
    from app.services.folio.folio_service import FolioService
    from app.services.ontology.registry import OntologyRegistry, get_registry, set_registry
    from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC
    from app.storage.job_store import JobStore
    from tests.test_union_service import Graph

    previous = get_registry()
    registry = OntologyRegistry({'folio': FOLIO_SPEC, 'canon': CANON_SPEC})
    set_registry(registry)
    def load(self):
        if self.ontology_id == unavailable:
            raise RuntimeError('offline')
        return Graph(self.spec)
    monkeypatch.setattr(FolioService, '_load_folio', load)
    monkeypatch.setattr(enrich, '_job_store', JobStore(base_dir=tmp_path))
    # Keep the test at the request boundary; later pipeline wiring is separate.
    async def run(self, job):
        self._stamp_ontology(job)
    monkeypatch.setattr(PipelineOrchestrator, 'run', run)
    try:
        response = await client.post('/enrich', json={'content': 'x', 'ontology': 'both'})
        if unavailable:
            assert response.status_code == 503
            assert ('Catholic Semantic Canon' if unavailable == 'canon' else 'FOLIO') in response.json()['detail']
            assert not list(tmp_path.glob('*.json'))
            if unavailable == 'canon':
                assert (await client.post('/enrich', json={'content': 'x', 'ontology': 'folio'})).status_code == 202
        else:
            assert response.status_code == 202
            saved = (await client.get('/enrich/' + response.json()['job_id'])).json()
            assert saved['result']['ontology_id'] == 'both'
    finally:
        set_registry(previous)
