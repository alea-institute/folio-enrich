from __future__ import annotations

import logging
from dataclasses import dataclass

import ahocorasick
import spacy
from spacy.language import Language

from app.services.entity_ruler.pattern_builder import build_patterns, decode_pattern_id
from app.services.folio.folio_service import LabelInfo

logger = logging.getLogger(__name__)

# Escape both control characters so encoding is injective and the separator
# occurs only between tokens, even when source text contains control characters.
_TOKEN_SEP = "\x00"
_TOKEN_ESCAPE = "\x01"


def _encode_token(token: str) -> str:
    return token.replace(_TOKEN_ESCAPE, _TOKEN_ESCAPE * 2).replace(
        _TOKEN_SEP, _TOKEN_ESCAPE + "s"
    )


@dataclass
class EntityRulerMatch:
    text: str
    start_char: int
    end_char: int
    label: str
    entity_id: str  # FOLIO IRI (decoded, without label_type suffix)
    match_type: str  # "preferred" or "alternative"


class FOLIOEntityRuler:
    """Token-aligned Aho-Corasick matcher for FOLIO concept patterns."""

    def __init__(self, nlp: Language | None = None) -> None:
        self._nlp = nlp
        self._automaton = ahocorasick.Automaton()
        self._loaded = False

    def _get_nlp(self) -> Language:
        if self._nlp is None:
            self._nlp = spacy.blank("en")
        return self._nlp

    def load_patterns(self, labels: dict[str, LabelInfo]) -> None:
        nlp = self._get_nlp()
        patterns = build_patterns(labels)
        automaton = ahocorasick.Automaton()
        for pattern in patterns:
            spec = pattern["pattern"]
            if isinstance(spec, str):
                words = [token.lower_ for token in nlp.make_doc(spec)]
            else:
                words = [token["LOWER"] for token in spec]
            if not words:
                continue
            key = _TOKEN_SEP.join(_encode_token(word) for word in words)
            # spaCy leaves equal-span ties to set iteration rather than defining
            # a priority. Use first-added order for identical token sequences.
            if key not in automaton:
                iri, match_type = decode_pattern_id(pattern["id"])
                automaton.add_word(key, (len(key), iri, match_type))
        if len(automaton):
            automaton.make_automaton()
        self._automaton = automaton
        self._loaded = True
        logger.info("EntityRuler loaded with %d patterns", len(patterns))

    def find_matches(self, text: str) -> list[EntityRulerMatch]:
        if not self._loaded or not len(self._automaton):
            return []

        nlp = self._get_nlp()
        # Only tokenization runs, so the statistical pipeline's length guard is
        # unnecessary; do not chunk and split a concept across chunks.
        if len(text) >= nlp.max_length:
            nlp.max_length = len(text) + 1
        doc = nlp.make_doc(text)
        starts: dict[int, int] = {}
        ends: dict[int, int] = {}
        encoded_tokens = []
        offset = 0
        for i, token in enumerate(doc):
            encoded = _encode_token(token.lower_)
            starts[offset] = i
            offset += len(encoded)
            ends[offset] = i + 1
            encoded_tokens.append(encoded)
            offset += len(_TOKEN_SEP)

        candidates = []
        for end_offset, (length, iri, match_type) in self._automaton.iter(
            _TOKEN_SEP.join(encoded_tokens)
        ):
            end_offset += 1  # automaton offsets are inclusive
            start = starts.get(end_offset - length)
            end = ends.get(end_offset)
            if start is not None and end is not None:
                candidates.append((start, end, iri, match_type))
        candidates.sort(key=lambda m: (-(m[1] - m[0]), m[0]))
        covered = bytearray(len(doc))
        kept = []
        for start, end, iri, match_type in candidates:
            if any(covered[start:end]):
                continue
            covered[start:end] = b"\x01" * (end - start)
            start_char = doc[start].idx
            end_char = doc[end - 1].idx + len(doc[end - 1])
            kept.append(EntityRulerMatch(
                text=text[start_char:end_char],
                start_char=start_char,
                end_char=end_char,
                label="FOLIO_CONCEPT",
                entity_id=iri,
                match_type=match_type,
            ))
        kept.sort(key=lambda m: m.start_char)
        return kept
