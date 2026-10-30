"""U5 sweep: extraction correctness (money regex, spaCy max_length, triple text)."""

from __future__ import annotations

import pytest

from app.services.dependency import parser as parser_mod
from app.services.dependency.parser import DependencyParser, iter_spacy_chunks
from app.services.entity_ruler.ruler import FOLIOEntityRuler
from app.services.folio.folio_service import FOLIOConcept, LabelInfo
from app.services.individual import entity_extractors as ee
from app.services.individual.entity_extractors import (
    MonetaryAmountExtractor,
    SpaCyLocationExtractor,
    SpaCyOrgExtractor,
    SpaCyPersonExtractor,
)


# ── Monetary amounts ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        # Negative: the next word's initial must not become a scale suffix.
        ("Pay $50,000 by Friday.", "$50,000"),
        ("It cost $10 more than planned.", "$10"),
        ("Remit $100 to the clerk.", "$100"),
        ("Fees: $20 Monthly.", "$20"),
        ("A fee of $100 (plus costs).", "$100"),
        ("A fee of $100, plus costs.", "$100"),
        # Positive.
        ("Damages of $5M were sought.", "$5M"),
        ("Damages of $5m were sought.", "$5m"),
        ("A $3bn deal.", "$3bn"),
        ("A $7.5MM reserve.", "$7.5MM"),
        ("Valued at $2.5 billion today.", "$2.5 billion"),
        ("Valued at $2.5 Billion dollars today.", "$2.5 Billion dollars"),
        ("Exactly $1,000,000.00 was paid.", "$1,000,000.00"),
        ("Paid 500 dollars in cash.", "500 dollars"),
        ("Paid twenty-five dollars.", "twenty-five dollars"),
    ],
)
def test_monetary_amount_bounds(text, expected):
    found = MonetaryAmountExtractor().extract_sync(text)
    assert [i.mention_text for i in found] == [expected]
    span = found[0].span
    assert text[span.start:span.end] == expected == span.text


def test_monetary_amount_ignores_usda():
    assert MonetaryAmountExtractor().extract_sync("100 USDA inspectors") == []


# ── Chunking helper ────────────────────────────────────────────────────


def test_iter_spacy_chunks_short_text_is_single_piece():
    text = "Short text."
    assert list(iter_spacy_chunks(text)) == [(0, text)]


def test_iter_spacy_chunks_covers_text_and_respects_limit():
    text = ("Sentence one is here. " * 40 + "\n\n") * 30
    pieces = list(iter_spacy_chunks(text, max_chars=1000))
    assert "".join(c for _, c in pieces) == text
    assert all(len(c) <= 1000 for _, c in pieces)
    for offset, chunk in pieces:
        assert text[offset:offset + len(chunk)] == chunk
    # Paragraph breaks are preferred when available in the back half.
    assert all(c.endswith((" ", "\n")) for _, c in pieces[:-1])


# ── Long texts (spaCy max_length) ──────────────────────────────────────

_FILLER = "The parties met on Monday. " * 30 + "\n\n"
_TAIL = "John Smith filed the motion in Chicago."


def _long_text(n_chars: int) -> str:
    body = _FILLER * (n_chars // len(_FILLER) + 1)
    return body + _TAIL


def test_dependency_parser_long_text_offsets(monkeypatch):
    text = _long_text(6000)
    monkeypatch.setattr(parser_mod, "SPACY_CHUNK_CHARS", 2000)
    nlp = parser_mod.get_spacy_nlp()
    monkeypatch.setattr(nlp, "max_length", 2500)

    triples, pos, ner = DependencyParser().extract_triples_and_pos(text)

    tail = [t for t in triples if t.predicate == "file"]
    assert tail, "triple near the end of a long text must be found"
    t = tail[-1]
    for span in (t.subject_span, t.predicate_span, t.object_span):
        assert text[span.start:span.end] == span.text
    assert t.subject == "John Smith"
    # Sentence indices run continuously across chunks.
    assert [p.sentence_index for p in pos] == list(range(len(pos)))
    assert all(text[p.start:p.end] == p.text for p in pos)
    assert any(e["text"] == "Chicago" and text[e["start"]:e["end"]] == "Chicago" for e in ner)


def test_ner_extractors_long_text_offsets(monkeypatch):
    text = _long_text(6000)
    monkeypatch.setattr(parser_mod, "SPACY_CHUNK_CHARS", 2000)
    nlp = parser_mod.get_spacy_nlp()
    monkeypatch.setattr(nlp, "max_length", 2500)
    monkeypatch.setattr(ee, "_ents_cache", None)

    people = SpaCyPersonExtractor().extract_sync(text)
    places = SpaCyLocationExtractor().extract_sync(text)
    for ind in people + places:
        assert text[ind.span.start:ind.span.end] == ind.span.text
    assert any(i.span.text == "John Smith" for i in people)
    assert any(i.span.text == "Chicago" for i in places)


def test_ner_extractors_share_one_parse(monkeypatch):
    calls = []
    real = parser_mod.get_spacy_nlp()

    def counting(t):
        calls.append(t)
        return real(t)

    monkeypatch.setattr(ee, "_get_spacy_nlp", lambda: counting)
    monkeypatch.setattr(ee, "_ents_cache", None)
    text = "Jane Doe sued Acme Corp in Boston."
    SpaCyPersonExtractor().extract_sync(text)
    SpaCyOrgExtractor().extract_sync(text)
    SpaCyLocationExtractor().extract_sync(text)
    assert len(calls) == 1


def test_entity_ruler_long_text_beyond_max_length():
    ruler = FOLIOEntityRuler()
    ruler.load_patterns({
        "breach of contract": LabelInfo(
            concept=FOLIOConcept(
                iri="iri-boc", preferred_label="Breach of Contract",
                alternative_labels=[], definition="", branch="Objectives",
                parent_iris=[],
            ),
            label_type="preferred", matched_label="Breach of Contract",
        ),
    })
    nlp = ruler._get_nlp()
    nlp.max_length = 5000
    text = _long_text(6000) + " A breach of contract occurred."
    matches = ruler.find_matches(text)
    assert matches, "concept beyond spaCy max_length must still match"
    m = matches[-1]
    assert text[m.start_char:m.end_char].lower() == "breach of contract"


# ── Triple text matches the document ───────────────────────────────────


def test_triple_text_matches_source_text():
    text = "The court granted Defendant's motion under Rule 12(b)(6)."
    triples, _, _ = DependencyParser().extract_triples_and_pos(text)
    assert triples
    for t in triples:
        for value, span in ((t.subject, t.subject_span), (t.object, t.object_span)):
            assert span is not None
            assert value == span.text == text[span.start:span.end]
    joined = " ".join(t.object for t in triples)
    assert " 's" not in joined and "(6 )" not in joined
