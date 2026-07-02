"""PR #14: per-ontology embedding gating + no cross-ontology contamination.

The process-global embedding index/service is built once at startup for the
default ontology (FOLIO). A job for another ontology (Canon) must NOT score its
candidates against FOLIO's vectors — every consumer gates on
``EmbeddingService.matches_ontology(job.ontology)`` and degrades gracefully.

These are offline: no OWL load or network required (the registry only *constructs*
services lazily; it doesn't fetch until a concept is resolved).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.document import DocumentInput
from app.models.job import Job
from app.pipeline.stages.reconciliation_stage import ReconciliationStage
from app.services.embedding.service import EmbeddingService
from app.services.folio.folio_service import FolioService


class TestMatchesOntology:
    def test_default_index_is_folio(self):
        svc = EmbeddingService()
        assert svc.matches_ontology("folio")
        assert svc.matches_ontology(None)  # None -> default folio
        assert not svc.matches_ontology("canon")

    def test_none_index_id_treated_as_folio(self):
        svc = EmbeddingService()
        svc._ontology_id = None  # defensive: None normalizes to folio
        assert svc.matches_ontology("folio")
        assert not svc.matches_ontology("canon")

    def test_index_folio_labels_tags_ontology(self):
        svc = EmbeddingService()
        # Feed a tiny fake service so no network/OWL is touched.
        fake = MagicMock()
        fake.get_all_labels.return_value = {}
        svc.index_folio_labels(fake, ontology_id="canon")
        assert svc._ontology_id == "canon"
        assert svc.matches_ontology("canon")
        assert not svc.matches_ontology("folio")


class TestReconciliationStageGate:
    """The reconciliation embedding-triage path must be skipped for a mismatched
    ontology, falling back to the plain (vector-free) reconcile()."""

    def _stage(self, index_ontology="folio"):
        emb = MagicMock()
        emb.matches_ontology.side_effect = lambda oid: (oid or "folio") == index_ontology
        reconciler = MagicMock()
        reconciler._embedding_service = emb
        reconciler.reconcile.return_value = []
        reconciler.reconcile_with_embedding_triage.return_value = []
        return ReconciliationStage(reconciler=reconciler), reconciler

    async def test_uses_triage_for_matching_ontology(self):
        stage, reconciler = self._stage(index_ontology="folio")
        job = Job(input=DocumentInput(content="x", ontology="folio"))
        await stage.execute(job)
        reconciler.reconcile_with_embedding_triage.assert_called_once()
        reconciler.reconcile.assert_not_called()

    async def test_skips_triage_for_mismatched_ontology(self):
        # FOLIO index + a Canon job -> plain reconcile, no FOLIO-vector triage.
        stage, reconciler = self._stage(index_ontology="folio")
        job = Job(input=DocumentInput(content="x", ontology="canon"))
        await stage.execute(job)
        reconciler.reconcile.assert_called_once()
        reconciler.reconcile_with_embedding_triage.assert_not_called()


class TestNoCrossOntologyContamination:
    """IT-1 (structural): distinct ontologies resolve through distinct, cached
    services, so a Canon job can never reach FOLIO's concept graph and vice versa."""

    def test_registry_returns_distinct_cached_services(self):
        folio = FolioService.get_instance("folio")
        canon = FolioService.get_instance("canon")
        assert folio is not canon
        # Same id -> same cached singleton (no per-request rebuild/clobber).
        assert folio is FolioService.get_instance("folio")
        assert canon is FolioService.get_instance("canon")

    def test_services_carry_their_own_ontology_identity(self):
        folio = FolioService.get_instance("folio")
        canon = FolioService.get_instance("canon")
        assert folio.ontology_id == "folio"
        assert canon.ontology_id == "canon"
        # Canon IRIs live under a different namespace than FOLIO's — the structural
        # guarantee that resolved Canon concepts can't carry FOLIO IRIs.
        assert folio.spec.base_iri == "https://folio.openlegalstandard.org/"
        assert canon.spec.base_iri == "https://ontology.catholicos.catholic/"
