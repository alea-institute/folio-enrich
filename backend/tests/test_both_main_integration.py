"""Regression checks for union integration with main's ruler and LLM refactors."""
import threading
from types import SimpleNamespace

import pytest

from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job
from tests.test_union_service import union_registry


async def test_union_ruler_borrows_cached_folio_without_changing_it(union_registry, monkeypatch):
    from app.pipeline.stages import entity_ruler_stage as module

    monkeypatch.setattr(module, '_RULER_CACHE', {})
    monkeypatch.setattr(module, '_UNION_RULER_CACHE', {})
    threads = []
    build_threads = []
    build_ruler = module._build_fast_ruler

    def observed_build(labels):
        build_threads.append(threading.current_thread())
        return build_ruler(labels)

    monkeypatch.setattr(module, '_build_fast_ruler', observed_build)
    service = union_registry.get_service('both')
    labels = service.get_all_labels

    def observed_labels():
        threads.append(threading.current_thread())
        return labels()

    monkeypatch.setattr(service, 'get_all_labels', observed_labels)

    async def run(oid):
        stage = module.EntityRulerStage()
        job = Job(input=DocumentInput(content='shared canon folio', ontology=oid))
        job.result.canonical_text = CanonicalText(full_text=job.input.content, chunks=[])
        await stage.execute(job)
        return stage, job

    first, _ = await run('folio')
    original_folio_matches = first.ruler.find_matches('shared canon folio')
    union, job = await run('both')
    second, folio_job = await run('folio')
    another_union, _ = await run('both')
    assert first.ruler is second.ruler
    assert union.ruler is not first.ruler
    assert another_union._bundle is union._bundle
    assert union._bundle.folio_bundle is first._bundle
    delta_labels = {k: v for k, v in labels().items() if k not in first._bundle.labels}
    assert first.ruler.find_matches('shared canon folio') == original_folio_matches
    assert len(delta_labels) < len(first._bundle.labels)
    assert union.ruler.find_matches('shared folio') == []
    assert [m.text for m in union.ruler.find_matches('canon')] == ['canon']
    assert set(module._RULER_CACHE) == {'folio'}
    assert 'both' not in module._RULER_CACHE
    assert threads and all(t is not threading.main_thread() for t in threads)
    assert len(build_threads) == 2  # one FOLIO build and one delta build
    assert all(t is not threading.main_thread() for t in build_threads)
    assert {c.region for a in job.result.annotations for c in a.concepts} == {
        'shared', 'canon_only', 'folio_only',
    }
    assert all(not c.folio_iri.startswith('https://ontology.catholicos.catholic/')
               for a in folio_job.result.annotations for c in a.concepts)


def test_composite_embeddings_pass_main_capability_gate():
    from app.services.embedding.service import CompositeEmbeddingService, can_encode

    provider = object()
    side = SimpleNamespace(_get_provider=lambda: provider)
    registry = SimpleNamespace(get_embedding_service=lambda oid: side)
    assert can_encode(CompositeEmbeddingService(registry))


async def test_codex_structured_uses_main_fenced_json_parser(monkeypatch):
    from unittest.mock import AsyncMock
    from app.services.llm.codex_cli_provider import CodexCLIProvider

    provider = CodexCLIProvider()
    monkeypatch.setattr(provider, '_run', AsyncMock(return_value='```json\n{"ok": true}\n```'))
    assert await provider.structured('extract', {'type': 'object'}) == {'ok': True}


@pytest.mark.parametrize('source', ['folio', 'labels', 'labels_multi'])
def test_union_bundle_cache_invalidates_on_identity_change(union_registry, monkeypatch, source):
    from app.pipeline.stages import entity_ruler_stage as module

    monkeypatch.setattr(module, '_RULER_CACHE', {})
    monkeypatch.setattr(module, '_UNION_RULER_CACHE', {})
    first = module._get_union_ruler_bundle()
    assert module._get_union_ruler_bundle() is first
    if source == 'folio':
        module._RULER_CACHE.clear()
    else:
        service = union_registry.get_service('both')
        method = 'get_all_labels' if source == 'labels' else 'get_all_labels_multi'
        replacement = dict(getattr(service, method)())
        monkeypatch.setattr(service, method, lambda: replacement)
    assert module._get_union_ruler_bundle() is not first
    assert set(module._RULER_CACHE) == {'folio'}


def test_union_shared_label_matches_once(union_registry, monkeypatch):
    from app.pipeline.stages import entity_ruler_stage as module

    monkeypatch.setattr(module, '_RULER_CACHE', {})
    monkeypatch.setattr(module, '_UNION_RULER_CACHE', {})
    bundle = module._get_union_ruler_bundle()
    matches = bundle.find_matches('shared')
    assert len(matches) == 1
    assert matches[0].entity_id == 'https://folio.openlegalstandard.org/shared'
    assert 'shared' not in bundle.delta_bundle.labels


@pytest.mark.parametrize(('folio_spans', 'delta_spans', 'expected'), [
    ([(0, 5)], [(3, 10)], [(3, 10)]),  # longer delta partial overlap
    ([(3, 5)], [(0, 10)], [(0, 10)]),  # delta contains FOLIO
    ([(0, 10)], [(3, 5)], [(0, 10)]),  # FOLIO contains delta
    ([(3, 8)], [(0, 5)], [(0, 5)]),  # equal length: earliest wins
    ([(0, 5)], [(5, 10)], [(0, 5), (5, 10)]),  # adjacent
    ([(0, 5)], [(0, 5)], [(0, 5)]),  # identical
])
def test_union_merge_drops_all_overlaps(monkeypatch, folio_spans, delta_spans, expected):
    from app.pipeline.stages import entity_ruler_stage as module
    from app.services.entity_ruler.ruler import EntityRulerMatch
    from app.services.ontology import overlap

    monkeypatch.setattr(overlap, 'get_overlap_index', lambda: SimpleNamespace(lookup=lambda key: object()))
    text = 'abcdefghij'

    def side(spans):
        return SimpleNamespace(find_matches=lambda text: [
            EntityRulerMatch(text[start:end], start, end, 'FOLIO_CONCEPT', 'iri/known', 'preferred')
            for start, end in spans
        ])

    bundle = module._UnionRulerBundle(side(folio_spans), side(delta_spans), {}, {}, {}, {}, {})
    assert [(m.start_char, m.end_char) for m in bundle.find_matches(text)] == expected


def test_union_drops_folio_matches_absent_from_overlap(monkeypatch):
    from app.pipeline.stages import entity_ruler_stage as module
    from app.services.entity_ruler.ruler import EntityRulerMatch
    from app.services.ontology import overlap

    looked_up = []

    def lookup(key):
        looked_up.append(key)
        return None

    monkeypatch.setattr(overlap, 'get_overlap_index', lambda: SimpleNamespace(lookup=lookup))
    folio = SimpleNamespace(find_matches=lambda text: [
        EntityRulerMatch(text, 0, len(text), 'FOLIO_CONCEPT', 'iri/excluded', 'preferred')
    ])
    delta = SimpleNamespace(find_matches=lambda text: [])
    bundle = module._UnionRulerBundle(folio, delta, {}, {}, {}, {}, {})
    assert bundle.find_matches('excluded') == []
    assert looked_up == ['excluded']


def test_union_windowed_matches_preserve_offsets(union_registry, monkeypatch):
    from app.pipeline.stages import entity_ruler_stage as module

    monkeypatch.setattr(module, '_RULER_CACHE', {})
    monkeypatch.setattr(module, '_UNION_RULER_CACHE', {})
    bundle = module._get_union_ruler_bundle()
    text = 'shared canon folio ' * 20
    expected = bundle.find_matches(text)
    monkeypatch.setattr(module, '_WINDOW_CHARS', 10)
    monkeypatch.setattr(module, '_WINDOW_MARGIN_SLACK', 1)
    assert bundle.find_matches(text) == expected
    assert all(text[m.start_char:m.end_char] == m.text for m in expected)
