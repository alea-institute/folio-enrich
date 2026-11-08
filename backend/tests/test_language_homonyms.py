"""Place/language homonyms retain the place without inferring language intent."""
from types import SimpleNamespace

import pytest

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.document import CanonicalText
from app.models.job import Job
from app.pipeline.stages.reconciliation_stage import ReconciliationStage
from app.pipeline.stages.resolution_stage import ResolutionStage
from app.pipeline.stages.string_match_stage import StringMatchStage
from app.services.folio.folio_service import FOLIOConcept, FolioService, LabelInfo
from app.services.folio.resolver import ConceptResolver


def make_concept(branch, label="Delaware"):
    return FOLIOConcept(iri=f"https://x/{branch}", preferred_label=label,
                        alternative_labels=["US+DE"] if branch == "Location" else [],
                        definition="", branch=branch, parent_iris=[])


def setup_service(monkeypatch, locations=True):
    language = make_concept("Language")
    concepts = [language, make_concept("Location")] if locations else [language]
    infos = [LabelInfo(c, "preferred", c.preferred_label) for c in concepts]
    service = SimpleNamespace(ontology_id="folio", get_concept=lambda iri: next((c for c in concepts if c.iri == iri), None),
                              get_all_labels=lambda: {"delaware": infos[0]},
                              get_all_labels_multi=lambda: {"delaware": infos})
    monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)
    resolver = ConceptResolver(service)
    monkeypatch.setattr(resolver, "_library_resolve_all", lambda *_: [])
    monkeypatch.setattr(resolver, "_fork_resolve_all", lambda *_: [(language, .9)])
    return resolver, concepts


@pytest.mark.parametrize("text", ["Delaware", "State of Delaware"])
def test_location_wins_language_resolution(monkeypatch, text):
    resolver, _ = setup_service(monkeypatch)
    result = resolver.resolve(text, branches=["Location"])
    assert result.folio_concept.branch == "Location"


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_ruler_reconciliation_resolution_stringmatch_preserves_state(monkeypatch, reverse):
    resolver, concepts = setup_service(monkeypatch)
    if reverse:
        concepts.reverse()
    job = Job()
    job.result.canonical_text = CanonicalText(full_text="This agreement is governed by Delaware law.")
    start = job.result.canonical_text.full_text.index("Delaware")
    job.result.metadata["ruler_concepts"] = [ConceptMatch(
        concept_text="Delaware", folio_iri=c.iri, branches=[c.branch], confidence=1,
        source="entity_ruler").model_dump() for c in concepts]
    job.result.metadata["llm_concepts"] = {"0": [{"concept_text": "Delaware", "branches": ["Location"], "confidence": .9}]}
    job.result.annotations = [Annotation(span=Span(start=start, end=start+8, text="Delaware"),
                                         concepts=[ConceptMatch(concept_text="Delaware", branches=["Location"], source="llm")])]
    await ReconciliationStage().execute(job)
    await ResolutionStage(resolver).execute(job)
    await StringMatchStage().execute(job)
    assert len(job.result.annotations) == 1
    assert job.result.annotations[0].concepts[0].branches == ["Location"]


@pytest.mark.asyncio
@pytest.mark.parametrize("source,hints,text,keep", [
    ("entity_ruler", ["Language"], "Delaware law applies.", False),
    ("llm", ["Location"], "State of Delaware law applies.", False),
    ("llm", [], "Delaware law applies.", False),
    ("llm", ["language"], "Delaware is spoken here.", True),
    ("entity_ruler", ["Language"], "The Delaware LANGUAGE is spoken here.", True),
    ("llm", [], "Delaware language skills are needed.", True),
    ("llm", [], "Delaware languages are studied.", False),
])
async def test_language_requires_intent(monkeypatch, source, hints, text, keep):
    resolver, concepts = setup_service(monkeypatch, locations=False)
    job = Job()
    job.result.canonical_text = CanonicalText(full_text=text)
    mention = {"concept_text": "State of Delaware" if text.startswith("State") else "Delaware",
               "branches": hints, "source": source}
    if source == "entity_ruler":
        mention["folio_iri"] = concepts[0].iri
    job.result.metadata["reconciled_concepts"] = [mention]
    await ResolutionStage(resolver).execute(job)
    assert bool(job.result.metadata["resolved_concepts"]) is keep


@pytest.mark.asyncio
async def test_reconciler_does_not_turn_ruler_branch_into_language_hint(monkeypatch):
    resolver, concepts = setup_service(monkeypatch, locations=False)
    job = Job()
    job.result.canonical_text = CanonicalText(full_text="Delaware law applies.")
    job.result.metadata["ruler_concepts"] = [ConceptMatch(
        concept_text="Delaware", folio_iri=concepts[0].iri, branches=["Language"],
        confidence=1, source="entity_ruler").model_dump()]
    job.result.metadata["llm_concepts"] = {"0": [{"concept_text": "Delaware", "branches": ["Location"], "confidence": .9}]}
    await ReconciliationStage().execute(job)
    await ResolutionStage(resolver).execute(job)
    assert job.result.metadata["resolved_concepts"] == []


@pytest.mark.asyncio
async def test_stringmatch_does_not_overwrite_different_iri_at_same_span(monkeypatch):
    _, concepts = setup_service(monkeypatch)
    job = Job()
    job.result.canonical_text = CanonicalText(full_text="Delaware")
    job.result.annotations = [Annotation(span=Span(start=0, end=8, text="Delaware"), concepts=[ConceptMatch(
        concept_text="Delaware", folio_iri=concepts[0].iri)])]
    job.result.metadata["resolved_concepts"] = [{"concept_text": "Delaware", "folio_iri": c.iri,
                                                "folio_label": c.preferred_label, "branches": [c.branch],
                                                "confidence": 1} for c in concepts]
    await StringMatchStage().execute(job)
    assert {a.concepts[0].folio_iri for a in job.result.annotations} == {c.iri for c in concepts}
    assert len({id(a) for a in job.result.annotations}) == 2
