"""Tests for EmbeddingService label disk caching."""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.embedding.service import EmbeddingService


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
            loaded = embedding_service._load_label_cache("abc123", labels)

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
            digest = hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest()[:12]
            old_path = tmp_path / f"test-model_labels_abc123_{digest}.pkl"
            new_path = tmp_path / f"different-model_labels_abc123_{digest}.pkl"
            old_path.rename(new_path)

            mock_provider.model_name = "different-model"
            with pytest.raises(ValueError, match="Model mismatch"):
                embedding_service._load_label_cache("abc123", labels)

    def test_missing_cache_raises(self, embedding_service, mock_provider, tmp_path):
        """Loading a nonexistent cache raises FileNotFoundError."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            with pytest.raises(FileNotFoundError):
                embedding_service._load_label_cache("nonexistent", [])


class TestIndexFolioLabelsWithCache:
    def test_second_call_uses_cache(
        self, embedding_service, mock_provider, mock_folio_service, tmp_path,
    ):
        """Second index_folio_labels() with same hash skips encoding."""
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path), \
             patch.object(mock_provider, "encode", wraps=mock_provider.encode) as encode:
            # First call: builds + caches
            embedding_service.index_folio_labels(mock_folio_service, owl_hash="hash1")
            assert embedding_service.index_size == 2
            mock_folio_service.get_all_labels.assert_called_once()

            # Reset state to prove it loads from cache
            embedding_service._labels = []
            embedding_service._metadata = []
            embedding_service._embeddings = None

            # Second call checks labels again but reuses cached vectors.
            embedding_service.index_folio_labels(mock_folio_service, owl_hash="hash1")
            assert embedding_service.index_size == 2
            # Both calls inspect labels; only the first encodes them.
            assert mock_folio_service.get_all_labels.call_count == 2
            assert encode.call_count == 1

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

    def test_changed_labels_rebuild_for_same_owl(
        self, embedding_service, mock_provider, mock_folio_service, tmp_path,
    ):
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path), \
             patch.object(mock_provider, "encode", wraps=mock_provider.encode) as encode:
            embedding_service.index_folio_labels(mock_folio_service, owl_hash="hash1")
            mock_folio_service.get_all_labels.return_value.pop("motion")
            with pytest.raises(FileNotFoundError):
                embedding_service._load_label_cache("hash1", ["court"])
            embedding_service.index_folio_labels(mock_folio_service, owl_hash="hash1")
            assert embedding_service._labels == ["court"]
            assert encode.call_count == 2
            first_path = embedding_service._label_cache_path("hash1", ["court", "motion"])
            second_path = embedding_service._label_cache_path("hash1", ["court"])
            assert first_path != second_path
            assert first_path.exists() and second_path.exists()

    def test_cache_paths_include_label_order(self, embedding_service, mock_provider, tmp_path):
        with patch.object(embedding_service, "_get_provider", return_value=mock_provider), \
             patch("app.services.embedding.service._LABEL_CACHE_DIR", tmp_path):
            assert embedding_service._label_cache_path("hash1", ["court", "motion"]) != (
                embedding_service._label_cache_path("hash1", ["motion", "court"])
            )
