"""PR #14: per-ontology embedding gating + no cross-ontology contamination.

The process-global embedding index/service is built once at startup for the
default ontology (FOLIO). A job for another ontology (Canon) must NOT score its
candidates against FOLIO's vectors — every consumer gates on
``EmbeddingService.matches_ontology(job.ontology)`` and degrades gracefully.

These are offline: no OWL load or network required (the registry only *constructs*
services lazily; it doesn't fetch until a concept is resolved).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from app.models.document import DocumentInput
from app.models.job import Job
from app.pipeline.stages.reconciliation_stage import ReconciliationStage
from app.services.embedding.service import EmbeddingService
from app.services.folio.folio_service import FolioService
from app.services.ontology.registry import OntologyRegistry
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC


class _FakeProvider:
    """Deterministic in-process embedding provider — no SentenceTransformer, no
    network. One instance stands in for the registry's shared MiniLM."""

    model_name = "all-MiniLM-L6-v2"

    def _vec(self, text: str) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        v = rng.standard_normal(8)
        return v / (np.linalg.norm(v) or 1.0)

    def encode(self, texts):
        return np.vstack([self._vec(t) for t in texts])

    def encode_single(self, text):
        return self._vec(text)


def _fake_labels(mapping: dict[str, str]) -> dict:
    """Build a get_all_labels()-shaped dict from {label: iri} without loading OWL."""
    return {
        lbl: SimpleNamespace(
            concept=SimpleNamespace(iri=iri), matched_label=lbl, label_type="preferred",
        )
        for lbl, iri in mapping.items()
    }


def _two_ontology_registry(monkeypatch, tmp_path):
    """A fresh registry with FOLIO + Canon whose label sources are faked (offline)
    and whose shared provider is the deterministic fake. Cache writes go to tmp."""
    import app.services.embedding.service as svc_mod

    monkeypatch.setattr(svc_mod, "_LABEL_CACHE_DIR", tmp_path / "emb_cache")

    reg = OntologyRegistry({"folio": FOLIO_SPEC, "canon": CANON_SPEC}, default_id="folio")
    reg._shared_provider = _FakeProvider()  # bypass real MiniLM load

    folio_svc = reg.get_service("folio")
    canon_svc = reg.get_service("canon")
    monkeypatch.setattr(
        folio_svc, "get_all_labels",
        lambda: _fake_labels({"breach of contract": "folio:R1", "motion to dismiss": "folio:R2"}),
    )
    monkeypatch.setattr(
        canon_svc, "get_all_labels",
        lambda: _fake_labels({"eucharist": "canon:C1", "holy trinity": "canon:C2"}),
    )
    return reg


class TestRegistryPerOntologyEmbeddingService:
    """WS-1: registry-keyed per-ontology embedding services for live Canon parity."""

    def test_distinct_cached_instances_tagged_by_ontology(self, monkeypatch, tmp_path):
        reg = _two_ontology_registry(monkeypatch, tmp_path)
        folio_es = reg.get_embedding_service("folio")
        canon_es = reg.get_embedding_service("canon")

        assert folio_es is not canon_es
        assert folio_es._ontology_id == "folio"
        assert canon_es._ontology_id == "canon"
        # Cached per ontology — same id returns the same object (no rebuild/clobber).
        assert reg.get_embedding_service("folio") is folio_es
        assert reg.get_embedding_service("canon") is canon_es
        assert folio_es.matches_ontology("folio") and not folio_es.matches_ontology("canon")
        assert canon_es.matches_ontology("canon") and not canon_es.matches_ontology("folio")

    def test_no_cross_ontology_leakage_in_search(self, monkeypatch, tmp_path):
        reg = _two_ontology_registry(monkeypatch, tmp_path)
        folio_es = reg.get_embedding_service("folio")
        canon_es = reg.get_embedding_service("canon")

        folio_labels = {"breach of contract", "motion to dismiss"}
        canon_labels = {"eucharist", "holy trinity"}

        # A search on one ontology can only ever surface that ontology's own labels.
        for r in folio_es.search("contract dispute", top_k=5):
            assert r.label in folio_labels
        for r in canon_es.search("sacrament", top_k=5):
            assert r.label in canon_labels

    def test_all_ontologies_share_one_provider(self, monkeypatch, tmp_path):
        reg = _two_ontology_registry(monkeypatch, tmp_path)
        folio_es = reg.get_embedding_service("folio")
        canon_es = reg.get_embedding_service("canon")
        # Exactly one SentenceTransformer (here: one fake) across ontologies.
        assert folio_es._provider is canon_es._provider is reg._shared_provider

    def test_canon_cache_keyed_by_pinned_owl_sha(self, monkeypatch, tmp_path):
        reg = _two_ontology_registry(monkeypatch, tmp_path)
        canon_es = reg.get_embedding_service("canon")
        canon_sha16 = CANON_SPEC.coords.owl_sha256[:16]
        # The Canon vectors are cached on disk keyed by the pinned Canon OWL sha.
        cache_path = canon_es._label_cache_path(canon_sha16)
        assert canon_sha16 in cache_path.name
        assert cache_path.exists(), "warm Canon cache should have been written under the pinned sha"

    def test_default_build_does_not_build_canon(self, monkeypatch, tmp_path):
        """FOLIO-only deploys pay no Canon cost — building the default ontology
        must not eagerly build Canon (it stays lazy until first requested)."""
        reg = _two_ontology_registry(monkeypatch, tmp_path)
        reg.get_embedding_service("folio")
        assert "canon" not in reg._embedding_services
        # First Canon request builds it lazily.
        reg.get_embedding_service("canon")
        assert "canon" in reg._embedding_services


class TestStageBindsPerOntologyServiceAtRuntime:
    """With registry_embeddings=True (production wiring), a gated stage fetches the
    embedding service for the JOB's ontology at run time — Canon jobs bind Canon."""

    async def test_reconciliation_binds_canon_service_for_canon_job(self, monkeypatch):
        canon_emb = MagicMock()
        canon_emb._ontology_id = "canon"
        canon_emb.index_size = 0  # empty → falls back to plain reconcile (no real vectors)
        canon_emb.matches_ontology.side_effect = lambda oid: (oid or "folio") == "canon"

        seen = {}

        def fake_get(oid=None):
            seen["oid"] = oid
            return canon_emb

        monkeypatch.setattr(
            "app.services.ontology.registry.get_embedding_service", fake_get
        )
        stage = ReconciliationStage(registry_embeddings=True)
        job = Job(input=DocumentInput(content="x", ontology="canon"))
        await stage.execute(job)

        assert seen["oid"] == "canon"
        assert stage.reconciler._embedding_service is canon_emb

    async def test_reconciliation_binds_folio_service_for_folio_job(self, monkeypatch):
        folio_emb = MagicMock()
        folio_emb._ontology_id = "folio"
        folio_emb.index_size = 0
        folio_emb.matches_ontology.side_effect = lambda oid: (oid or "folio") == "folio"

        seen = {}

        def fake_get(oid=None):
            seen["oid"] = oid
            return folio_emb

        monkeypatch.setattr(
            "app.services.ontology.registry.get_embedding_service", fake_get
        )
        stage = ReconciliationStage(registry_embeddings=True)
        job = Job(input=DocumentInput(content="x", ontology="folio"))
        await stage.execute(job)

        assert seen["oid"] == "folio"
        assert stage.reconciler._embedding_service is folio_emb


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
        emb.index_size = 100
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
