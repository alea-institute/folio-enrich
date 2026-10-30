from __future__ import annotations

import logging
from dataclasses import dataclass

import spacy
from spacy.language import Language

from app.services.dependency.parser import iter_spacy_chunks
from app.services.entity_ruler.pattern_builder import build_patterns, decode_pattern_id
from app.services.folio.folio_service import LabelInfo

logger = logging.getLogger(__name__)

# Components that only tokenize and pattern-match; their memory grows linearly
# with text length, so spaCy's max_length guard (meant for parser/NER) can be
# lifted instead of chunking, which could split a multi-word concept.
_RULE_ONLY_PIPES = {"entity_ruler"}


@dataclass
class EntityRulerMatch:
    text: str
    start_char: int
    end_char: int
    label: str
    entity_id: str  # FOLIO IRI (decoded, without label_type suffix)
    match_type: str  # "preferred" or "alternative"


class FOLIOEntityRuler:
    """spaCy EntityRuler loaded with FOLIO concept patterns."""

    def __init__(self, nlp: Language | None = None) -> None:
        self._nlp = nlp
        self._loaded = False

    def _get_nlp(self) -> Language:
        if self._nlp is None:
            self._nlp = spacy.blank("en")
        return self._nlp

    def load_patterns(self, labels: dict[str, LabelInfo]) -> None:
        nlp = self._get_nlp()
        patterns = build_patterns(labels)

        if "entity_ruler" in nlp.pipe_names:
            nlp.remove_pipe("entity_ruler")

        ruler = nlp.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER"})
        ruler.add_patterns(patterns)
        self._loaded = True
        logger.info("EntityRuler loaded with %d patterns", len(patterns))

    def find_matches(self, text: str) -> list[EntityRulerMatch]:
        if not self._loaded:
            return []

        nlp = self._get_nlp()
        if set(nlp.pipe_names) <= _RULE_ONLY_PIPES:
            if len(text) >= nlp.max_length:
                nlp.max_length = len(text) + 1
            pieces = [(0, text)]
        else:
            # An injected statistical pipeline keeps spaCy's memory guard.
            pieces = iter_spacy_chunks(text)

        matches = []
        for offset, chunk in pieces:
            doc = nlp(chunk)
            for ent in doc.ents:
                if ent.label_ == "FOLIO_CONCEPT":
                    iri, match_type = decode_pattern_id(ent.ent_id_)
                    matches.append(
                        EntityRulerMatch(
                            text=ent.text,
                            start_char=ent.start_char + offset,
                            end_char=ent.end_char + offset,
                            label=ent.label_,
                            entity_id=iri,
                            match_type=match_type,
                        )
                    )
        return matches
