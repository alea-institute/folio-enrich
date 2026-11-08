"""Deictic courts require a single court in the document, never fuzzy search."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.job import Job
from app.pipeline.stages.resolution_stage import ResolutionStage
from app.services.folio.folio_service import FOLIOConcept, FolioService
from app.services.folio.resolver import ConceptResolver


def court(iri, label):
    return FOLIOConcept(iri=iri, preferred_label=label, alternative_labels=[],
                        definition="", branch="Forums and Venues", parent_iris=[])


def resolver_with_courts(monkeypatch, courts):
    family = court("https://x/family", "Family Court")
    service = SimpleNamespace(ontology_id="folio", get_all_labels=lambda: {},
                              get_concept=lambda iri: next((c for c in courts if c.iri == iri), None))
    monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)
    resolver = ConceptResolver(service)
    monkeypatch.setattr(resolver, "_library_resolve_all", lambda *_: [])
    fork = MagicMock(return_value=[(family, .9)])
    monkeypatch.setattr(resolver, "_fork_resolve_all", fork)
    return resolver, fork


@pytest.mark.parametrize("text", ["This Court", "this Court", "the Court", "THAT COURT", "said court", "  this   COURT  "])
def test_deictic_court_never_fuzzy_resolves(monkeypatch, text):
    resolver, fork = resolver_with_courts(monkeypatch, [])
    assert resolver.resolve(text) is None
    assert resolver.resolve_multi(text) == []
    fork.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["llm", "reconciled"])
@pytest.mark.parametrize("labels,expected", [
    (["U.S. Ct. App. - 7th Circuit"], True),
    (["Supreme Court of Wisconsin"], True),
    (["Family Court"], True),
    ([], False),
    (["Supreme Court of Wisconsin", "U.S. Ct. App. - 7th Circuit"], False),
])
async def test_deictic_court_coreference_of_any_type(monkeypatch, source, labels, expected):
    courts = [court(f"https://x/court{index}", label) for index, label in enumerate(labels)]
    resolver, _ = resolver_with_courts(monkeypatch, courts)
    job = Job()
    concepts = [{"concept_text": "this Court", "source": source}]
    concepts += [{"concept_text": c.preferred_label, "folio_iri": c.iri, "source": source} for c in courts]
    job.result.metadata[f"{source}_concepts"] = concepts if source == "reconciled" else {"0": concepts}
    await ResolutionStage(resolver).execute(job)
    generic = [c for c in job.result.metadata["resolved_concepts"] if c["concept_text"] == "this Court"]
    assert bool(generic) is expected
    if expected:
        assert generic[0]["folio_iri"] == courts[0].iri
        assert generic[0]["_lineage_events"][-1]["action"] == "coreference"


def test_deictic_direct_iri_remains_available_for_coreference(monkeypatch):
    target = court("https://x/supreme", "Supreme Court")
    resolver, fork = resolver_with_courts(monkeypatch, [target])
    assert resolver.resolve("the Court", folio_iri=target.iri).folio_concept.iri == target.iri
    fork.assert_not_called()


def test_deictic_coreference_cache_cannot_supply_another_job(monkeypatch):
    target = court("https://x/supreme", "Supreme Court")
    resolver, _ = resolver_with_courts(monkeypatch, [target])
    assert resolver.resolve("this Court", folio_iri=target.iri)
    assert resolver.resolve("this Court") is None
    assert resolver.resolve("this Court", folio_iri="missing") is None


@pytest.mark.asyncio
async def test_deictic_does_not_link_court_costs(monkeypatch):
    costs = court("https://x/costs", "Court Costs")
    costs.branch = "Objectives"
    resolver, _ = resolver_with_courts(monkeypatch, [costs])
    job = Job()
    job.result.metadata["reconciled_concepts"] = [
        {"concept_text": "this Court"}, {"concept_text": "court costs", "folio_iri": costs.iri},
    ]
    await ResolutionStage(resolver).execute(job)
    assert [c["concept_text"] for c in job.result.metadata["resolved_concepts"]] == ["court costs"]


@pytest.mark.asyncio
async def test_deictic_does_not_restore_a_context_rejected_court(monkeypatch):
    from app.models.document import CanonicalText
    family = court("https://x/family", "Family Court")
    family.definition = "A family tribunal"
    resolver, fork = resolver_with_courts(monkeypatch, [family])
    fork.return_value = [(family, .9)]
    emb = MagicMock(index_size=1)
    emb.similarity_batch.return_value = [0.0]
    job = Job()
    job.result.canonical_text = CanonicalText(full_text="An appellate tribunal hears this Court.")
    job.result.metadata["reconciled_concepts"] = [
        {"concept_text": "this Court"}, {"concept_text": "appellate tribunal"},
    ]
    await ResolutionStage(resolver, embedding_service=emb).execute(job)
    assert job.result.metadata["resolved_concepts"] == []
