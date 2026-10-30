"""U2 regression: embedding status must reflect whether vectors actually exist.

When the provider cannot encode (sentence-transformers missing), index_labels used
to set _labels/_provider before encode() raised, so /health/detail said "ready",
index_size > 0 let consumers proceed, and /ontologies said embeddings_available.
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from app.api.routes.health import _check_embedding
from app.api.routes.ontologies import list_ontologies
from app.config import settings
from app.services.embedding.service import EmbeddingService


class _BrokenProvider:
    model_name = "broken"

    def encode(self, texts):
        raise ImportError("sentence-transformers is required for local embeddings.")


class _OKProvider:
    model_name = "ok"

    def encode(self, texts):
        vecs = np.ones((len(texts), 4), dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    def encode_single(self, text):
        return self.encode([text])[0]


@pytest.fixture
def seeded_instance(monkeypatch):
    def _seed(svc):
        monkeypatch.setattr(EmbeddingService, "_instance", svc)
        return svc

    return _seed


def _failed_service(provider) -> EmbeddingService:
    svc = EmbeddingService(provider=provider)
    with pytest.raises(ImportError):
        svc.index_labels(["Contract", "Tort"], [{}, {}])
    return svc


def test_failed_encode_leaves_no_half_built_index():
    svc = _failed_service(_BrokenProvider())
    assert svc.is_ready is False
    assert svc.index_size == 0  # consumers gate on index_size == 0
    assert "sentence-transformers" in (svc.last_error or "")
    assert svc.search("contract") == []


def test_health_reports_unavailable_with_reason(seeded_instance):
    seeded_instance(_failed_service(_BrokenProvider()))
    status = _check_embedding()
    assert status["status"] == "unavailable"
    assert "sentence-transformers" in status["message"]
    assert status["index_size"] == 0


def test_health_reports_ready_when_vectors_exist(seeded_instance):
    svc = EmbeddingService(provider=_OKProvider())
    svc.index_labels(["Contract", "Tort"])
    seeded_instance(svc)
    status = _check_embedding()
    assert status["status"] == "ready"
    assert status["index_size"] == 2
    assert svc.last_error is None


async def test_ontologies_embeddings_available_reflects_real_state(seeded_instance, monkeypatch):
    monkeypatch.setattr(settings, "embedding_disabled", False)

    seeded_instance(_failed_service(_BrokenProvider()))
    assert (await list_ontologies())["embeddings_available"] is False

    ok = EmbeddingService(provider=_OKProvider())
    ok.index_labels(["Contract"])
    seeded_instance(ok)
    assert (await list_ontologies())["embeddings_available"] is True

    monkeypatch.setattr(settings, "embedding_disabled", True)
    assert (await list_ontologies())["embeddings_available"] is False


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is not None,
    reason="exercises the real missing-sentence-transformers path",
)
def test_real_local_provider_without_sentence_transformers(seeded_instance):
    from app.services.embedding.providers.local import LocalEmbeddingProvider

    svc = _failed_service(LocalEmbeddingProvider())
    seeded_instance(svc)
    status = _check_embedding()
    assert status["status"] == "unavailable"
    assert "sentence-transformers" in status["message"]
