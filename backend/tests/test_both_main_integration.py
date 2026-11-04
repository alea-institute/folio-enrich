"""Regression checks for union integration with main's ruler and LLM refactors."""
import threading
from types import SimpleNamespace

from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job
from tests.test_union_service import union_registry


async def test_union_ruler_is_private_and_cannot_change_cached_folio(union_registry, monkeypatch):
    from app.pipeline.stages import entity_ruler_stage as module

    monkeypatch.setattr(module, '_RULER_CACHE', {})
    threads = []
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
    union, job = await run('both')
    second, folio_job = await run('folio')
    another_union, _ = await run('both')
    assert first.ruler is second.ruler
    assert union.ruler is not first.ruler
    assert another_union.ruler is not union.ruler
    assert 'both' not in module._RULER_CACHE
    assert threads and all(t is not threading.main_thread() for t in threads)
    assert {c.region for a in job.result.annotations for c in a.concepts} == {
        'shared', 'canon_only', 'folio_only',
    }
    assert all(c.folio_iri != 'https://ontology.catholicos.catholic/canon'
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
