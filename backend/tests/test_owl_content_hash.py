"""Tests for get_owl_content_hash()."""
from __future__ import annotations

from unittest.mock import patch, PropertyMock

import pytest

from app.services.folio.owl_cache import get_owl_content_hash


class TestGetOwlContentHash:
    def test_empty_when_no_file(self, tmp_path):
        """Returns empty string when the OWL cache file doesn't exist."""
        fake_file = tmp_path / "nonexistent.owl"
        with patch("app.services.folio.owl_cache._CACHE_FILE", fake_file):
            assert get_owl_content_hash() == ""

    def test_consistent_hash(self, tmp_path):
        """Same content always produces the same hash."""
        fake_file = tmp_path / "test.owl"
        fake_file.write_bytes(b"<owl>content</owl>")
        with patch("app.services.folio.owl_cache._CACHE_FILE", fake_file):
            h1 = get_owl_content_hash()
            h2 = get_owl_content_hash()
        assert h1 == h2
        assert len(h1) == 16

    def test_different_content_different_hash(self, tmp_path):
        """Different OWL content produces different hashes."""
        fake_file = tmp_path / "test.owl"
        with patch("app.services.folio.owl_cache._CACHE_FILE", fake_file):
            fake_file.write_bytes(b"<owl>version1</owl>")
            h1 = get_owl_content_hash()
            fake_file.write_bytes(b"<owl>version2</owl>")
            h2 = get_owl_content_hash()
        assert h1 != h2
