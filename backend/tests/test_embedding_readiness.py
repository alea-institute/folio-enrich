"""Embedding readiness requires a provider that can encode queries.

A label index loaded from the on-disk cache has vectors (index_size > 0) even
when the local provider's sentence-transformers dependency is missing; every
query encode then fails. /health/detail, EmbeddingService.is_ready and the
ontologies ``embeddings_available`` flag must not report such an index ready.
"""
from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.api.routes import ontologies
from app.api.routes.health import _check_embedding
from app.config import settings
from app.services.embedding import service as embedding_service_mod
from app.services.embedding.providers.local import LocalEmbeddingProvider
from app.services.embedding.service import EmbeddingService, can_encode


def _cache_loaded_service(monkeypatch) -> EmbeddingService:
    svc = EmbeddingService(provider=LocalEmbeddingProvider())
    cached = {
        "labels": ["breach of contract", "tort"],
        "metadata": [{"iri": "a"}, {"iri": "b"}],
        "embeddings": np.ones((2, 4), dtype=np.float32),
    }
    monkeypatch.setattr(svc, "_load_label_cache", lambda owl_hash: cached)
    svc.index_folio_labels(folio_service=None, owl_hash="hash")
    assert svc.index_size == 2
    return svc


@pytest.fixture
def singleton(monkeypatch):
    monkeypatch.setattr(settings, "embedding_disabled", False)

    def install(svc):
        monkeypatch.setattr(EmbeddingService, "_instance", svc)
        return svc
    return install


@pytest.mark.skipif(importlib.util.find_spec("sentence_transformers") is not None,
                    reason="exercises the real missing-dependency case")
def test_cache_loaded_index_not_ready_without_sentence_transformers(monkeypatch, singleton):
    embedding_service_mod._sentence_transformers_available.cache_clear()
    svc = singleton(_cache_loaded_service(monkeypatch))
    assert not can_encode(svc)
    assert svc.is_ready is False
    health = _check_embedding()
    assert health["status"] == "unavailable"
    assert health["index_size"] == 2
    assert "sentence-transformers" in health["message"]
    assert ontologies._embeddings_available() is False


def test_cache_loaded_index_unavailable_when_encoder_missing(monkeypatch, singleton):
    monkeypatch.setattr(embedding_service_mod, "_sentence_transformers_available", lambda: False)
    singleton(_cache_loaded_service(monkeypatch))
    assert _check_embedding()["status"] == "unavailable"
    assert ontologies._embeddings_available() is False


def test_cache_loaded_index_ready_when_encoder_present(monkeypatch, singleton):
    monkeypatch.setattr(embedding_service_mod, "_sentence_transformers_available", lambda: True)
    svc = singleton(_cache_loaded_service(monkeypatch))
    assert svc.is_ready is True
    assert _check_embedding() == {"status": "ready", "provider": "LocalEmbeddingProvider", "index_size": 2}
    assert ontologies._embeddings_available() is True


def test_remote_provider_not_prejudged(monkeypatch, singleton):
    monkeypatch.setattr(embedding_service_mod, "_sentence_transformers_available", lambda: False)
    svc = singleton(EmbeddingService(provider=MagicMock()))
    svc._labels, svc._metadata, svc._embeddings = ["x"], [{}], np.ones((1, 4), dtype=np.float32)
    assert svc.is_ready is True
    assert _check_embedding()["status"] == "ready"
