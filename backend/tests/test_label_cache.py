"""Tests for EmbeddingService label disk caching."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.embedding.service import EmbeddingService, _LABEL_CACHE_DIR


@pytest.fixture
def embedding_service():
    """Fresh EmbeddingService instance (not the global singleton)."""
    return EmbeddingService()


@pytest.fixture
def mock_provider():
    """Mock embedding provider with deterministic encode."""
    provider = MagicMock()
    provider.model_name = "test-model"

    def _encode(texts):
        vecs = np.random.default_rng(42).random((len(texts), 8)).astype(np.float32)
        # L2 normalize
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    provider.encode = _encode
    provider.encode_single = lambda t: _encode([t])[0]
    return provider


@pytest.fixture
def mock_folio_service():
    """Minimal mock FolioService with get_all_labels."""
    from app.services.folio.folio_service import FOLIOConcept, LabelInfo

    mock = MagicMock()
    mock.get_all_labels.return_value = {
        "court": LabelInfo(
            concept=FOLIOConcept(
                iri="iri1", preferred_label="Court",
                alternative_labels=[], definition="", branch="", parent_iris=[],
            ),
            label_type="preferred",
            matched_label="Court",
        ),
        "motion": LabelInfo(
            concept=FOLIOConcept(
                iri="iri2", preferred_label="Motion",
                alternative_labels=[], definition="", branch="", parent_iris=[],
            ),
            label_type="preferred",
            matched_label="Motion",
        ),
    }
    return mock


class TestLabelCacheRoundTrip:
    def test_save_and_load(self, embedding_service, mock_provider, tmp_path):
        """Save + load preserves labels, metadata, and embeddings."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            labels = ["court", "motion"]
            metadata = [{"iri": "iri1"}, {"iri": "iri2"}]
            embeddings = mock_provider.encode(labels)

            embedding_service._save_label_cache("abc123", labels, metadata, embeddings)
            loaded = embedding_service._load_label_cache("abc123")

        assert loaded["labels"] == labels
        assert loaded["metadata"] == metadata
        np.testing.assert_array_equal(loaded["embeddings"], embeddings)
        assert loaded["model"] == "test-model"

    def test_model_mismatch_raises(self, embedding_service, mock_provider, tmp_path):
        """Loading a cache created with a different model raises ValueError."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            labels = ["court"]
            metadata = [{"iri": "iri1"}]
            embeddings = mock_provider.encode(labels)
            embedding_service._save_label_cache("abc123", labels, metadata, embeddings)

            # Rename the cache file to match a "different-model" slug so
            # _load_label_cache finds it, then change the provider model name
            old_path = tmp_path / "test-model_labels_abc123.pkl"
            new_path = tmp_path / "different-model_labels_abc123.pkl"
            old_path.rename(new_path)

            mock_provider.model_name = "different-model"
            with pytest.raises(ValueError, match="Model mismatch"):
                embedding_service._load_label_cache("abc123")

    def test_missing_cache_raises(self, embedding_service, mock_provider, tmp_path):
        """Loading a nonexistent cache raises FileNotFoundError."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            with pytest.raises(FileNotFoundError):
                embedding_service._load_label_cache("nonexistent")


class TestIndexFolioLabelsWithCache:
    def test_second_call_uses_cache(
        self, embedding_service, mock_provider, mock_folio_service, tmp_path,
    ):
        """Second index_folio_labels() with same hash skips encoding."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            # First call: builds + caches
            embedding_service.index_folio_labels(mock_folio_service, owl_hash="hash1")
            assert embedding_service.index_size == 2
            mock_folio_service.get_all_labels.assert_called_once()

            # Reset state to prove it loads from cache
            embedding_service._labels = []
            embedding_service._metadata = []
            embedding_service._embeddings = None

            # Second call: should load from cache, not call get_all_labels again
            embedding_service.index_folio_labels(mock_folio_service, owl_hash="hash1")
            assert embedding_service.index_size == 2
            # get_all_labels still called only once (from first call)
            mock_folio_service.get_all_labels.assert_called_once()

    def test_no_hash_skips_caching(
        self, embedding_service, mock_provider, mock_folio_service, tmp_path,
    ):
        """Without owl_hash, no cache files are created."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            embedding_service.index_folio_labels(mock_folio_service)
            assert embedding_service.index_size == 2
            # No cache files written
            assert list(tmp_path.glob("*.pkl")) == []
