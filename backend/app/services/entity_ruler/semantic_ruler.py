from __future__ import annotations

import logging
from dataclasses import dataclass

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
})


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

    def _collect_candidates(
        self, text: str, known_spans: set[tuple[int, int]]
    ) -> list[tuple[str, int, int]]:
        """Candidate n-grams (2-4 words) with correct char offsets, minus known
        spans and all-stopword phrases. Returns (normalized_phrase, start, end)."""
        offsets = self._word_offsets(text)
        words = [text[s:e] for s, e in offsets]
        candidates: list[tuple[str, int, int]] = []
        num_words = len(words)
        for n in range(2, 5):
            for i in range(num_words - n + 1):
                start = offsets[i][0]
                end = offsets[i + n - 1][1]
                # Overlaps an exact-match span? (same test as before)
                if any(s <= start < e or s < end <= e for s, e in known_spans):
                    continue
                tokens = words[i : i + n]
                if all(t.lower() in _SEMANTIC_STOPWORDS for t in tokens):
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
