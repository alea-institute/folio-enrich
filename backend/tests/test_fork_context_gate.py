"""Recall fallback must have contextual evidence before StringMatch expands it."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.models.document import CanonicalText
from app.models.job import Job
from app.pipeline.stages.resolution_stage import ResolutionStage
from app.pipeline.stages.string_match_stage import StringMatchStage
from app.services.folio.folio_service import FOLIOConcept, FolioService
from app.services.folio.resolver import ConceptResolver


def concept():
    return FOLIOConcept(iri="https://x/bananas", preferred_label="Bananas",
                        alternative_labels=[], definition="A fruit", branch="Asset Type", parent_iris=[])


@pytest.mark.parametrize("path", ["library", "fork", "direct", "exact_court"])
def test_resolver_records_resolution_path(monkeypatch, path):
    fc = concept()
    service = SimpleNamespace(ontology_id="folio", get_concept=lambda iri: fc)
    resolver = ConceptResolver(service)
    monkeypatch.setattr(resolver, "_exact_court_or_caption", lambda text: (fc, 1.0) if path == "exact_court" else None)
    monkeypatch.setattr(resolver, "_library_resolve_all", lambda *args: [(fc, .9)] if path == "library" else [])
    monkeypatch.setattr(resolver, "_fork_resolve_all", lambda *args: [(fc, .8)])
    result = resolver.resolve("CEO", folio_iri=fc.iri if path == "direct" else None)
    assert result.resolution_path == path


@pytest.mark.parametrize("sim,hints,path,keep", [
    (.00, ["Asset Type"], "fork", False),
    (.149, ["Asset Type"], "fork", False),
    (.15, ["asset type"], "fork", True),
    (.299, ["Actor / Player"], "fork", False),
    (.20, [], "fork", False),
    (.30, [], "fork", True),
    (.00, [], "library", True),
    (.00, [], "direct", True),
    (.00, [], "exact_court", True),
])
def test_fork_context_thresholds(sim, hints, path, keep):
    emb = MagicMock(index_size=1)
    emb.similarity_batch.return_value = [sim]
    stage = ResolutionStage(resolver=MagicMock(), embedding_service=emb)
    concepts = [{"concept_text": "CEO", "folio_definition": "A fruit", "confidence": .9,
                 "branches": ["Asset Type"], "_branch_hints": hints, "_resolution_path": path}]
    stage._apply_embedding_context_scores(concepts, "The CEO signed.")
    assert bool(concepts) is keep


@pytest.mark.parametrize("unavailable", ["none", "empty", "mismatch", "error", "no_definition", "disabled"])
def test_no_evidence_or_disabled_keeps_fork(monkeypatch, unavailable):
    emb = MagicMock(index_size=0 if unavailable == "empty" else 1)
    emb.matches_ontology.return_value = unavailable != "mismatch"
    emb.similarity_batch.return_value = [.0]
    if unavailable == "error":
        emb.similarity_batch.side_effect = RuntimeError("unavailable")
    if unavailable == "disabled":
        monkeypatch.setattr(settings, "fork_context_gate_enabled", False)
    stage = ResolutionStage(resolver=MagicMock(), embedding_service=None if unavailable == "none" else emb)
    concepts = [{"concept_text": "CEO", "folio_definition": "" if unavailable == "no_definition" else "fruit",
                 "confidence": .9, "branches": ["Asset Type"], "_resolution_path": "fork"}]
    stage._apply_embedding_context_scores(concepts, "The CEO signed.")
    assert len(concepts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("sim,remaining", [(0.0, 0), (.20, 0), (.30, 1)])
async def test_dropped_fork_stays_out_of_stringmatch_metadata(monkeypatch, sim, remaining):
    service = SimpleNamespace(ontology_id="folio", get_all_labels=lambda: {})
    monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)
    resolver = ConceptResolver(service)
    monkeypatch.setattr(resolver, "_exact_court_or_caption", lambda *_: None)
    monkeypatch.setattr(resolver, "_library_resolve_all", lambda *_: [])
    monkeypatch.setattr(resolver, "_fork_resolve_all", lambda *_: [(concept(), .9)])
    emb = MagicMock(index_size=1)
    emb.similarity_batch.return_value = [sim]
    job = Job()
    job.result.canonical_text = CanonicalText(full_text="The CEO signed.")
    job.result.metadata["reconciled_concepts"] = [{"concept_text": "CEO", "branches": ["Actor / Player"]}]
    await ResolutionStage(resolver, embedding_service=emb).execute(job)
    resolved = job.result.metadata["resolved_concepts"]
    assert len(resolved) == remaining
    assert all("_resolution_path" not in rc and "_branch_hints" not in rc for rc in resolved)
    assert f"dropped {1 - remaining} fork" in job.result.metadata["activity_log"][-1]["msg"]
    await StringMatchStage().execute(job)
    assert len(job.result.annotations) == remaining
