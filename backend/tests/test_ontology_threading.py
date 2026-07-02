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

    def test_unknown_or_disabled_rejected(self):
        # canon is defined but not enabled -> deterministic rejection
        with pytest.raises(ValidationError):
            EnrichRequest(content="x", ontology="canon")
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
        assert ids == ["folio"]
        folio = body["ontologies"][0]
        assert folio["display_name"] == "FOLIO"
        assert folio["default"] is True

    def test_get_folio(self):
        r = client.get("/ontologies/folio")
        assert r.status_code == 200
        assert r.json()["base_iri"] == "https://folio.openlegalstandard.org/"

    def test_get_disabled_ontology_404(self):
        r = client.get("/ontologies/canon")
        assert r.status_code == 404
        assert "Enabled" in r.json()["detail"]


class TestEnrichRouteOntologyBoundary:
    def test_post_enrich_rejects_disabled_ontology_422(self):
        # End-to-end: a bad ontology is a 422 at the route, not a 500 deep in the pipeline
        r = client.post("/enrich", json={"content": "hello", "ontology": "canon"})
        assert r.status_code == 422
        assert "folio" in r.text  # enabled list surfaced in the error

    def test_post_enrich_rejects_unknown_ontology_422(self):
        r = client.post("/enrich", json={"content": "hello", "ontology": "bogus"})
        assert r.status_code == 422
