"""Offline union pipeline and serialization contracts."""
import json

import pytest

from tests.test_union_service import union_registry
from app.models.annotation import ConceptMatch, Annotation, Span
from app.models.document import DocumentInput
from app.models.job import Job
from app.pipeline.orchestrator import PipelineOrchestrator
from app.storage.job_store import JobStore
from app.services.embedding.service import EmbeddingService


@pytest.mark.parametrize('regex_only', [False, True])
async def test_rule_pipeline_consumes_union(union_registry, monkeypatch, tmp_path, regex_only):
    from app.config import settings
    from app.services.ontology.union_service import UnionService
    monkeypatch.setattr(settings, 'ner_cross_validation_enabled', False)
    monkeypatch.setattr(settings, 'pos_tagging_enabled', False)
    monkeypatch.setattr(settings, 'triple_extraction_enabled', False)
    monkeypatch.setattr(settings, 'individual_regex_only', True)
    monkeypatch.setattr(settings, 'property_regex_only', regex_only)
    for oid in ('folio', 'canon'):
        emb = EmbeddingService()
        emb._ontology_id = oid
        union_registry._embedding_services[oid] = emb
    for oid in ('folio', 'canon'):
        graph = union_registry.get_service(oid)._get_folio()
        shared_class = next(c for c in graph.classes if c.label == 'shared')
        shared_class.label = 'theft'
        shared_class.definition = 'Taking without consent' if oid == 'canon' else 'Theft'
    consumed = []
    original = UnionService.get_all_labels
    def labels(self):
        consumed.append('union_labels')
        return original(self)
    monkeypatch.setattr(UnionService, 'get_all_labels', labels)
    from unittest.mock import AsyncMock
    monkeypatch.setattr('app.services.individual.citation_extractor.CitationExtractor.extract', AsyncMock(return_value=[]))
    monkeypatch.setattr('app.services.individual.entity_extractors.EntityExtractorRunner.extract', AsyncMock(return_value=[]))
    pipeline = PipelineOrchestrator(JobStore(base_dir=tmp_path), llm=None)
    job = await pipeline.run(Job(input=DocumentInput(content='theft canon folio', ontology='both')))
    assert job.status.value == 'completed', job.error
    assert consumed
    concepts = [c for a in job.result.annotations for c in a.concepts if c.state != 'backup']
    assert {c.region for c in concepts} == {'shared', 'canon_only', 'folio_only'}
    shared = [c for c in concepts if c.iri_hash == 'shared']
    assert len(shared) == 1
    assert shared[0].folio_iri == 'https://folio.openlegalstandard.org/shared'
    assert shared[0].peer_iri == 'https://ontology.catholicos.catholic/shared'
    assert shared[0].drifted is True
    assert shared[0].peer_branches == []
    assert any('LLM stages skipped' in event['msg'] for event in job.result.metadata['activity_log'])


@pytest.mark.parametrize('oid,base', [('folio', 'https://folio.openlegalstandard.org/'), ('canon', 'https://ontology.catholicos.catholic/')])
def test_single_job_omits_union_fields(oid, base):
    job = Job(input=DocumentInput(content='theft', ontology=oid))
    job.result.base_iri = base
    job.result.annotations = [Annotation(span=Span(start=0,end=5,text='theft'), concepts=[ConceptMatch(concept_text='theft', folio_iri=base+'theft')])]
    data = job.model_dump(mode='json')
    concept = data['result']['annotations'][0]['concepts'][0]
    keys = {'region', 'peer_iri', 'peer_label', 'peer_branches', 'drifted', 'peer_base_iri', 'bridges'}
    assert not keys & concept.keys()
    assert all(f'"{key}":' not in json.dumps(data) for key in keys)
    if oid == 'canon':
        assert 'https://folio.openlegalstandard.org/' not in str(data)


async def test_each_stage_uses_requested_union(union_registry, monkeypatch, tmp_path):
    """Observe real service boundaries, including embedding and prompt consumers."""
    from contextvars import ContextVar
    from unittest.mock import AsyncMock
    from app.config import settings
    from app.services.folio.folio_service import FolioService
    from app.pipeline.orchestrator import build_stages
    from app.services.llm.prompts import templates
    from tests.helpers import FakeLLMProvider
    active = ContextVar('active', default='construction')
    seen = {}
    get = FolioService.get_instance
    def service(oid=None):
        result = get(oid)
        seen.setdefault(active.get(), []).append(result.ontology_id)
        return result
    monkeypatch.setattr(FolioService, 'get_instance', staticmethod(service))
    import app.services.ontology.registry as registry_module
    def embeddings(oid=None):
        result = union_registry.get_embedding_service(oid)
        assert result.matches_ontology('both')
        seen.setdefault(active.get(), []).append('both')
        return result
    monkeypatch.setattr(registry_module, 'get_embedding_service', embeddings)
    for oid in ('folio', 'canon'):
        emb = EmbeddingService()
        emb._ontology_id = oid
        union_registry._embedding_services[oid] = emb
    monkeypatch.setattr(templates, '_BRANCH_DETAIL_CACHE', {'folio': 'Folio roots', 'canon': 'Canon roots'})
    branch_detail = templates.get_branch_detail
    def detail(oid='folio'):
        if oid == 'both':
            seen.setdefault(active.get(), []).append('both')
        return branch_detail(oid)
    monkeypatch.setattr('app.services.llm.prompts.concept_identification.get_branch_detail', detail)
    monkeypatch.setattr('app.services.concept.branch_judge.get_branch_detail', detail)
    monkeypatch.setattr(settings, 'pos_tagging_enabled', False)
    monkeypatch.setattr(settings, 'triple_extraction_enabled', False)
    monkeypatch.setattr(settings, 'individual_regex_only', False)
    monkeypatch.setattr(settings, 'property_regex_only', False)
    monkeypatch.setattr('app.services.individual.citation_extractor.CitationExtractor.extract', AsyncMock(return_value=[]))
    monkeypatch.setattr('app.services.individual.entity_extractors.EntityExtractorRunner.extract', AsyncMock(return_value=[]))
    stages = build_stages(FakeLLMProvider({'concepts': [], 'properties': [], 'individuals': [], 'branch': 'Concept'}))
    job = Job(input=DocumentInput(content='shared canon folio', ontology='both'))
    wanted = {'entity_ruler', 'llm_concept_identification', 'reconciliation', 'resolution', 'branch_judge', 'string_matching', 'early_individual_extraction', 'llm_individual_linking', 'early_property_extraction', 'llm_property_linking'}
    for stage in stages:
        if stage.name not in wanted | {'ingestion', 'normalization'}:
            continue
        active.set(stage.name)
        job = await stage.execute(job)
    assert wanted <= seen.keys(), seen
    assert set(seen['entity_ruler']) == {'folio', 'both'}, seen
    assert all(set(seen[name]) == {'both'} for name in wanted - {'entity_ruler'}), seen


def test_union_resolver_collapses_shared_and_searches_canon_fork(union_registry, monkeypatch):
    from app.services.folio.resolver import ConceptResolver
    service = union_registry.get_service('both')
    resolver = ConceptResolver(service)
    for oid in ('folio', 'canon'):
        graph = union_registry.get_service(oid)._get_folio()
        monkeypatch.setattr(graph, 'search_by_label', lambda label, graph=graph, **kw: [(c, 100.0) for c in graph.classes if c.label == label])
    assert len(resolver._library_resolve_all('shared', '')) == 1
    consumed = []
    def search(graph, text, **kwargs):
        consumed.append(graph)
        cls = next(c for c in graph.classes if c.label == 'canon') if any(c.label == 'canon' for c in graph.classes) else None
        if cls is None:
            return []
        assert kwargs['get_branch_fn'](graph, 'canon') == ''
        return [{'iri': cls.iri, 'label': 'canon', 'score': 100}]
    monkeypatch.setattr('app.services.folio.search.multi_strategy_search', search)
    results = resolver._fork_resolve_all('canon', '')
    assert len(consumed) == 2
    assert len(results) == 1
    assert results[0][0].iri == 'https://ontology.catholicos.catholic/canon'
    assert results[0][0].region == 'canon_only'


def test_union_property_labels_accept_external_iris(union_registry, monkeypatch):
    from dataclasses import replace
    external = 'http://www.w3.org/2000/01/rdf-schema#locatedIn'
    for oid in ('folio', 'canon'):
        service = union_registry.get_service(oid)
        prop = service.get_property(service.spec.base_iri + 'prop')
        prop = replace(prop, iri=external)
        monkeypatch.setattr(service, 'get_property', lambda iri, prop=prop: prop if iri == external else None)
    assert union_registry.get_service('both').get_property(external).iri == external
