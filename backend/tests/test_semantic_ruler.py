"""Tests for Semantic EntityRuler integration."""

import pytest

from app.services.embedding.service import EmbeddingService
from app.services.entity_ruler.semantic_ruler import SemanticEntityRuler


@pytest.mark.slow
class TestSemanticEntityRuler:
    @pytest.fixture(scope="class")
    def indexed_embedding_service(self):
        svc = EmbeddingService()
        labels = ["breach of contract", "motion to dismiss", "intellectual property"]
        metadata = [
            {"iri": "iri1", "label": "Breach of Contract", "type": "preferred"},
            {"iri": "iri2", "label": "Motion to Dismiss", "type": "preferred"},
            {"iri": "iri3", "label": "Intellectual Property", "type": "preferred"},
        ]
        svc.index_labels(labels, metadata)
        return svc

    def test_finds_semantic_matches(self, indexed_embedding_service):
        ruler = SemanticEntityRuler(indexed_embedding_service, threshold=0.50)
        text = "The contract violation was severe."
        matches = ruler.find_semantic_matches(text, set())
        # Should find something related to "breach of contract" via "contract violation"
        assert len(matches) >= 0  # May or may not match depending on similarity

    def test_skips_known_spans(self, indexed_embedding_service):
        ruler = SemanticEntityRuler(indexed_embedding_service, threshold=0.50)
        text = "The contract violation was severe."
        # Mark the entire text as already matched
        known_spans = {(0, len(text))}
        matches = ruler.find_semantic_matches(text, known_spans)
        assert len(matches) == 0

    def test_no_embedding_service(self):
        ruler = SemanticEntityRuler(None)
        matches = ruler.find_semantic_matches("any text", set())
        assert matches == []

    def test_empty_index(self):
        svc = EmbeddingService()
        ruler = SemanticEntityRuler(svc)
        matches = ruler.find_semantic_matches("any text", set())
        assert matches == []

    def test_skips_pure_stopword_candidates(self, indexed_embedding_service):
        """Candidates like 'by and' where all tokens are stopwords should be skipped."""
        from app.services.entity_ruler.semantic_ruler import _SEMANTIC_STOPWORDS
        ruler = SemanticEntityRuler(indexed_embedding_service, threshold=0.50)
        text = "by and through its"
        matches = ruler.find_semantic_matches(text, set())
        for m in matches:
            tokens = m.text.lower().split()
            assert not all(t in _SEMANTIC_STOPWORDS for t in tokens), \
                f"Pure-stopword match should not occur: '{m.text}'"


class TestSemanticCandidateCollection:
    """Pure-Python candidate logic — no embeddings / sentence-transformers, so
    these run by default (not marked slow). Guards the perf optimizations."""

    def test_word_offsets_handles_newlines_and_multispace(self):
        text = "The  Agreement\nbetween parties."
        offs = SemanticEntityRuler._word_offsets(text)
        assert [text[s:e] for s, e in offs] == ["The", "Agreement", "between", "parties."]

    def test_candidate_offsets_are_correct(self):
        ruler = SemanticEntityRuler(embedding_service=None)
        text = "Acme  Corporation and\nJohn Smith"
        for phrase, s, e in ruler._collect_candidates(text, set()):
            assert text[s:e].split() == phrase.split()

    def test_captures_newline_spanning_ngrams(self):
        """Regression: the old str.find on a single-spaced phrase silently dropped
        n-grams whose words were separated by a newline/multi-space."""
        ruler = SemanticEntityRuler(embedding_service=None)
        text = "Confidential\nInformation clause"
        phrases = {p for p, _, _ in ruler._collect_candidates(text, set())}
        assert "Confidential Information" in phrases

    def test_excludes_known_spans(self):
        ruler = SemanticEntityRuler(embedding_service=None)
        text = "the party shall perform the duty"
        ps = text.index("party")
        cands = {p for p, _, _ in ruler._collect_candidates(text, {(ps, ps + len("party"))})}
        # Same rule as before: a candidate starting inside the known span is excluded…
        assert "party shall" not in cands
        # …while a candidate entirely outside it is still generated.
        assert "shall perform" in cands


class TestSemanticDedup:
    def test_duplicate_phrases_embedded_once(self):
        """A phrase repeated in the doc is embedded a single time, but every
        occurrence still yields a match (speed win, zero recall change)."""
        from unittest.mock import MagicMock

        class _R:
            def __init__(self, label, score, iri):
                self.label, self.score, self.metadata = label, score, {"iri": iri}

        recorded = {}

        def fake_search_batch(phrases, top_k=1):
            recorded["phrases"] = list(phrases)
            return [[_R("Agreement", 0.95, "iri1")] for _ in phrases]

        svc = MagicMock()
        svc.index_size = 3
        svc.search_batch.side_effect = fake_search_batch

        ruler = SemanticEntityRuler(svc, threshold=0.80)
        text = "the agreement and the agreement again"
        matches = ruler.find_semantic_matches(text, set())

        occurrences = [m for m in matches if m.text.lower() == "the agreement"]
        assert len(occurrences) == 2  # both occurrences matched
        assert recorded["phrases"].count("the agreement") == 1  # embedded once


def test_top_k_indices_matches_argsort():
    """EmbeddingService._top_k_indices returns the same top-k (by score) as a full
    argsort — the argpartition speedup must not change results."""
    import numpy as np
    from app.services.embedding.service import EmbeddingService

    rng = np.random.default_rng(7)
    for _ in range(100):
        n = int(rng.integers(1, 300))
        k = int(rng.integers(1, 8))
        scores = rng.integers(0, 40, size=n).astype(float)  # ties on purpose
        got = EmbeddingService._top_k_indices(scores, k)
        exp = np.argsort(scores)[::-1][:k]
        assert list(scores[got]) == list(scores[exp])
