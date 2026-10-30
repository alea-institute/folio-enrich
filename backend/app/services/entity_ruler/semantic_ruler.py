from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.services.entity_ruler.pattern_builder import _STOPWORDS

logger = logging.getLogger(__name__)

# Extended stopwords for semantic matching — superset of pattern_builder._STOPWORDS.
# Includes common function words that are legitimate exact-match patterns (e.g. "will",
# "shall") but should never anchor a semantic embedding search.
_SEMANTIC_STOPWORDS = _STOPWORDS | frozenset({
    # Pronouns / determiners
    "this", "that", "they", "them", "what", "when", "where", "which",
    "whom", "each", "some", "such", "both", "same", "said", "here",
    # Auxiliary / common verbs
    "have", "been", "were", "will", "does", "done", "made", "shall",
    "being",
    # Prepositions / conjunctions / adverbs
    "with", "from", "into", "than", "then", "also", "just", "even",
    "more", "most", "only", "over", "very", "well", "much", "back",
    "like", "upon", "thus", "once",
    "after", "before", "under", "about", "against", "between", "during",
    "within", "without", "through", "among", "until", "since", "while",
    "there", "their", "these", "those", "would", "should", "could", "must",
})

# Characters stripped from the edges of a whitespace token to get its "core".
# A trailing one on any word but the last (or a leading one on any word but the
# first) marks a sentence/clause boundary inside the n-gram, so the n-gram is
# dropped: "in damages. The" and "Corp. in the" must never become candidates.
_LEADING_PUNCT = "\"'([{“‘<"
_TRAILING_PUNCT = ".,;:!?\"')]}”’>"


@lru_cache(maxsize=1)
def _sentence_transformers_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def can_encode(embedding_service) -> bool:
    """Cheap (cached) check that the service's provider can embed new text.

    An index loaded from the on-disk label cache has ``index_size > 0`` even when
    the local provider's ``sentence-transformers`` dependency is missing; every
    query encode then raises ImportError, but only after the costly candidate
    build. Remote providers (Ollama/OpenAI) are assumed able to encode; their
    errors stay per-request.
    """
    if embedding_service is None:
        return False
    try:
        provider = embedding_service._get_provider()
    except Exception:
        return False
    from app.services.embedding.providers.local import LocalEmbeddingProvider

    if isinstance(provider, LocalEmbeddingProvider):
        return _sentence_transformers_available()
    return True


@dataclass
class SemanticMatch:
    text: str
    start: int
    end: int
    matched_label: str
    similarity: float
    iri: str


class SemanticEntityRuler:
    """Embedding-enhanced EntityRuler for near-match discovery."""

    def __init__(self, embedding_service=None, threshold: float = 0.80) -> None:
        self._embedding_service = embedding_service
        self.threshold = threshold

    @staticmethod
    def _word_offsets(text: str) -> list[tuple[int, int]]:
        """(start, end) char offsets of each whitespace-delimited token, one pass.

        Lets us derive n-gram spans in O(1) from word positions instead of an
        O(len(text)) ``str.find`` per candidate — and yields *correct* offsets even
        when words are separated by newlines or runs of spaces (the old ``find``
        on a single-spaced phrase silently dropped those n-grams).
        """
        offsets: list[tuple[int, int]] = []
        i, n = 0, len(text)
        while i < n:
            while i < n and text[i].isspace():
                i += 1
            if i >= n:
                break
            start = i
            while i < n and not text[i].isspace():
                i += 1
            offsets.append((start, i))
        return offsets

    @staticmethod
    def _token_core(text: str, start: int, end: int) -> tuple[int, int, bool, bool]:
        """Strip edge punctuation from a token. Returns (core_start, core_end,
        had_leading, had_trailing). A dotted abbreviation ("U.S.") keeps its final
        period and does not count as a boundary."""
        cs, ce = start, end
        while cs < ce and text[cs] in _LEADING_PUNCT:
            cs += 1
        while ce > cs and text[ce - 1] in _TRAILING_PUNCT:
            ce -= 1
        if ce < end and text[ce] == "." and "." in text[cs:ce]:
            ce += 1
        return cs, ce, cs > start, ce < end

    def _collect_candidates(
        self, text: str, known_spans: set[tuple[int, int]]
    ) -> list[tuple[str, int, int]]:
        """Candidate n-grams (2-4 words) with correct char offsets.

        A candidate never crosses a sentence/clause boundary (interior edge
        punctuation or a blank line), never starts or ends with a stopword, is
        trimmed of edge punctuation, and does not overlap any known span at all
        (including fully containing one). Returns (normalized_phrase, start, end).
        """
        offsets = self._word_offsets(text)
        cores = [self._token_core(text, s, e) for s, e in offsets]
        # Prefix count of characters covered by known spans: an O(1) "does [a, b)
        # overlap any known span?" test instead of scanning every span per candidate.
        diff = np.zeros(len(text) + 1, dtype=np.int32)
        for ks, ke in known_spans:
            ks, ke = max(ks, 0), min(ke, len(text))
            if ke > ks:
                diff[ks] += 1
                diff[ke] -= 1
        covered = np.cumsum(diff[:-1]) > 0
        prefix = np.concatenate(([0], np.cumsum(covered)))

        candidates: list[tuple[str, int, int]] = []
        num_words = len(offsets)
        for n in range(2, 5):
            for i in range(num_words - n + 1):
                last = i + n - 1
                first_core, last_core = cores[i], cores[last]
                if first_core[0] >= first_core[1] or last_core[0] >= last_core[1]:
                    continue  # pure-punctuation edge token
                if first_core[3] or last_core[2]:
                    continue  # boundary after the first word / before the last
                if any(cores[k][2] or cores[k][3] for k in range(i + 1, last)):
                    continue  # boundary inside the n-gram
                # A blank line between words is a paragraph/heading break.
                if any(text.count("\n", offsets[k][1], offsets[k + 1][0]) > 1
                       for k in range(i, last)):
                    continue
                start, end = first_core[0], last_core[1]
                if prefix[end] - prefix[start]:
                    continue  # overlaps (or contains) an exact-match span
                tokens = text[start:end].split()
                if (tokens[0].lower() in _SEMANTIC_STOPWORDS
                        or tokens[-1].lower() in _SEMANTIC_STOPWORDS):
                    continue
                candidates.append((" ".join(tokens), start, end))
        return candidates

    def find_semantic_matches(
        self, text: str, known_spans: set[tuple[int, int]]
    ) -> list[SemanticMatch]:
        """Find concept mentions missed by exact-match ruler using embedding similarity.

        known_spans: set of (start, end) already matched by EntityRuler/Aho-Corasick
        """
        if self._embedding_service is None or self._embedding_service.index_size == 0:
            return []
        if not can_encode(self._embedding_service):
            return []

        # Phase 1: candidate n-grams with correct O(1) offsets.
        candidates = self._collect_candidates(text, known_spans)
        if not candidates:
            return []

        # Phase 2: embed each DISTINCT phrase once, then reuse its result for every
        # occurrence. Legal text repeats phrases heavily ("the Agreement", "the
        # parties", "Confidential Information"), so this shrinks the neural forward
        # pass without changing which spans are considered — same matches, less work.
        unique_phrases = list({phrase for phrase, _, _ in candidates})
        batch_results = self._embedding_service.search_batch(unique_phrases, top_k=1)
        best_by_phrase = {
            phrase: (results[0] if results else None)
            for phrase, results in zip(unique_phrases, batch_results)
        }

        # Phase 3: filter by threshold (unchanged semantics).
        matches = []
        for phrase, start, end in candidates:
            top = best_by_phrase.get(phrase)
            if top and top.score >= self.threshold:
                matches.append(SemanticMatch(
                    text=text[start:end],
                    start=start,
                    end=end,
                    matched_label=top.label,
                    similarity=top.score,
                    iri=top.metadata.get("iri", ""),
                ))

        return matches
