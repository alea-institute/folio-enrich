"""Regression coverage for union labels, lifetime, export, and NER routing."""
from io import BytesIO
from types import SimpleNamespace

import pytest

from tests.test_union_service import union_registry
from app.models.annotation import Annotation, ConceptMatch, Span, stamp_union_concept
from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job


@pytest.fixture
def excluded_canon(union_registry):
    service = union_registry.get_service('canon')
    root = SimpleNamespace(iri=service.spec.base_iri + 'hidden', label='ZZZ editorial',
                           definition='', sub_class_of=[])
    child = SimpleNamespace(iri=service.spec.base_iri + 'rosary', label='Marian Rosary',
                            definition='', sub_class_of=[root.iri])
    service._get_folio().classes.extend([root, child])
    return child.iri


def test_union_labels_exclude_editorial_descendants(union_registry, excluded_canon):
    from app.services.ontology.overlap import get_overlap_index
    assert 'marian rosary' in union_registry.get_service('canon').get_all_labels_multi()
    assert get_overlap_index().lookup('rosary') is None
    labels = union_registry.get_service('both').get_all_labels_multi()
    assert 'marian rosary' not in labels
    assert all(entry.concept.region for entries in labels.values() for entry in entries)


def test_unindexed_concept_has_explicit_union_defaults(union_registry, excluded_canon):
    concept = union_registry.get_service('both').get_concept(excluded_canon)
    assert (concept.region, concept.peer_iri, concept.peer_label, concept.drifted) == (None,) * 4


def test_stamping_accepts_undecorated_concept(union_registry):
    raw = union_registry.get_service('canon').get_concept('https://ontology.catholicos.catholic/canon')
    service = SimpleNamespace(ontology_id='both', get_concept=lambda iri: raw)
    stamped = stamp_union_concept(ConceptMatch(concept_text='canon', folio_iri=raw.iri), service)
    assert (stamped.region, stamped.peer_iri, stamped.peer_label, stamped.drifted) == (None,) * 4


async def test_entity_ruler_keeps_valid_tags_with_excluded_label(union_registry, excluded_canon):
    from app.pipeline.stages.entity_ruler_stage import EntityRulerStage
    job = Job(input=DocumentInput(content='Marian Rosary shared', ontology='both'))
    job.result.canonical_text = CanonicalText(full_text=job.input.content, chunks=[])
    await EntityRulerStage().execute(job)
    concepts = [c for a in job.result.annotations for c in a.concepts]
    assert concepts
    assert {c.folio_iri for c in concepts} == {'https://folio.openlegalstandard.org/shared'}


def test_registry_reuses_union_label_cache(union_registry, monkeypatch):
    first = union_registry.get_service('both')
    labels = first.get_all_labels_multi()
    second = union_registry.get_service('both')
    assert first is second
    def unexpected_rebuild(*args):
        pytest.fail('resident union labels rebuilt')
    monkeypatch.setattr(second, 'get_concept', unexpected_rebuild)
    assert second.get_all_labels_multi() is labels


def test_registry_reinstallation_resets_union(union_registry):
    from app.services.ontology.registry import set_registry
    first = union_registry.get_service('both')
    first.get_all_labels_multi()
    set_registry(union_registry)
    assert union_registry.get_service('both') is not first


@pytest.mark.parametrize('iri', [None, '', 'https://unknown.example/concept'])
def test_union_ner_skips_unroutable_concepts(union_registry, monkeypatch, iri):
    from app.config import settings
    from app.pipeline.stages.reconciliation_stage import ReconciliationStage
    monkeypatch.setattr(settings, 'ner_cross_validation_enabled', True)
    job = Job(input=DocumentInput(content='Thomas', ontology='both'))
    ann = Annotation(span=Span(start=0, end=6, text='Thomas'), concepts=[
        ConceptMatch(concept_text='Thomas', folio_iri=iri, branches=['Actor / Player'], confidence=0.5)])
    job.result.annotations = [ann]
    job.result.metadata['spacy_ner_entities'] = [{'start': 0, 'end': 6, 'label': 'PERSON'}]
    assert ReconciliationStage._apply_ner_adjustments(job) == (0, 0)
    assert ann.concepts[0].confidence == 0.5
    assert not ann.lineage


def test_empty_union_parquet_export():
    import pyarrow.parquet as pq
    from app.services.export.parquet_exporter import ParquetExporter
    job = Job(input=DocumentInput(content='', ontology='both'))
    job.result.ontology_id = 'both'
    table = pq.read_table(BytesIO(ParquetExporter().export(job)))
    assert table.schema.metadata[b'bridges'] == b'[]'
    assert not any(row.get('folio_iri') for row in table.to_pylist())
