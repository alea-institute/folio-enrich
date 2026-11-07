"""Token-aligned ruler regressions using synthetic concepts only."""
import random

import pytest
import spacy

from app.pipeline.stages.entity_ruler_stage import _build_fast_ruler
from app.services.entity_ruler.pattern_builder import build_patterns, decode_pattern_id
from app.services.entity_ruler.ruler import EntityRulerMatch, FOLIOEntityRuler
from app.services.folio.folio_service import FOLIOConcept, FolioService, LabelInfo


@pytest.fixture(autouse=True)
def no_ontology(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("These tests must not load an ontology")
    monkeypatch.setattr(FolioService, "get_instance", forbidden)


def labels(*names):
    return {
        name: LabelInfo(
            concept=FOLIOConcept(f"iri/{i}", name, [], "", "", []),
            label_type="alternative" if i % 2 else "preferred",
            matched_label=name,
        )
        for i, name in enumerate(names)
    }


def legacy_ruler(entries):
    """The former production builder, independent of FOLIOEntityRuler."""
    nlp = spacy.blank("en")
    pipe = nlp.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER"})
    patterns = []
    for pattern in build_patterns(entries):
        spec = pattern["pattern"]
        if isinstance(spec, list) and all(set(token) == {"LOWER"} for token in spec):
            words = [token["LOWER"] for token in spec]
            phrase = " ".join(words)
            if [t.lower_ for t in nlp.make_doc(phrase)] == words:
                pattern = {**pattern, "pattern": phrase}
        patterns.append(pattern)
    pipe.add_patterns(patterns)
    return nlp


def legacy_matches(nlp, text):
    return [EntityRulerMatch(
        ent.text, ent.start_char, ent.end_char, ent.label_,
        *decode_pattern_id(ent.ent_id_),
    ) for ent in nlp(text).ents]


@pytest.mark.parametrize("text,expected", [
    ("Breach of Contract", True),
    ("breach of  contract", False),
    ("breach of\ncontract", False),
    ("Café — breach of contract", True),
])
def test_phrase_spacing_and_offsets(text, expected):
    ruler = _build_fast_ruler(labels("breach of contract"))
    matches = ruler.find_matches(text)
    if expected:
        start = text.lower().index("breach")
        assert matches == [EntityRulerMatch(text[start:], start, len(text),
                                           "FOLIO_CONCEPT", "iri/0", "preferred")]
    else:
        assert matches == []


@pytest.mark.parametrize("text", ["non-compete", "Non-Compete"])
def test_hyphenated_phrase(text):
    assert _build_fast_ruler(labels("non-compete")).find_matches(text) == [
        EntityRulerMatch(text, 0, len(text), "FOLIO_CONCEPT", "iri/0", "preferred")
    ]


def test_attached_punctuation_token_pattern():
    assert _build_fast_ruler(labels("license (agreement)")).find_matches("license (agreement)") == []


@pytest.mark.parametrize("names,text,expected", [
    (("contract", "breach of contract"), "breach of contract", "breach of contract"),
    (("alpha beta", "beta gamma"), "alpha beta gamma", "alpha beta"),
    (("alpha beta gamma", "beta", "gamma delta"), "alpha beta gamma delta", "alpha beta gamma"),
])
def test_overlap_resolution(names, text, expected):
    matches = _build_fast_ruler(labels(*names)).find_matches(text)
    assert [m.text for m in matches] == [expected]


def test_equal_span_keeps_first_added_pattern():
    entries = labels("CONTRACT", "contract")
    ruler = _build_fast_ruler(entries)
    assert ruler.find_matches("Contract")[0].entity_id == "iri/0"


def test_unloaded_empty_and_reload():
    ruler = FOLIOEntityRuler()
    assert ruler.find_matches("contract") == []
    ruler.load_patterns({})
    assert ruler._loaded
    assert ruler.find_matches("contract") == []
    ruler.load_patterns(labels("contract", "the", "ab"))
    assert len(ruler.find_matches("contract the ab")) == 1
    ruler.load_patterns(labels("lease"))
    assert [m.text for m in ruler.find_matches("contract lease")] == ["lease"]


def test_tokenizer_only_and_long_input():
    nlp = spacy.blank("en")
    ruler = FOLIOEntityRuler(nlp)
    ruler.load_patterns(labels("contract"))
    assert nlp.pipe_names == []
    nlp.max_length = 10
    text = "padding " * 100 + "contract"
    assert ruler.find_matches(text)[0].start_char == len(text) - 8


@pytest.mark.parametrize("label,text", [
    ("contract", "subcontract contractually contract"),
    ("café", "İ Café CAFÉ"),
    ("foo\x00bar", "foo\x00bar foo\x01sbar foo bar"),
    ("foo\x01sbar", "foo\x00bar foo\x01sbar foo bar"),
])
def test_boundaries_and_encoding(label, text):
    entries = labels(label)
    assert _build_fast_ruler(entries).find_matches(text) == legacy_matches(legacy_ruler(entries), text)


def test_synthetic_equivalence():
    names = ["contract", "breach of contract", "non-compete", "license (agreement)",
             "alpha beta", "beta gamma", "the", "ab", "u.s. district court", "attorney's fees"]
    for i in range(120):
        names.extend((f"concept{i}", f"legal concept{i}", f"non-compete{i}"))
    entries = labels(*names)
    old, new = legacy_ruler(entries), _build_fast_ruler(entries)
    rng = random.Random(31)
    texts = ["Café — breach of contract; Non-Compete; license (agreement).",
             "alpha beta gamma", "breach of  contract; breach of\ncontract", ""]
    for _ in range(300):
        pieces = rng.choices(names, k=8)
        texts.append(rng.choice(["; ", " ", "\n", "  "]).join(
            p.upper() if rng.randrange(2) else p for p in pieces))
    for text in texts:
        assert new.find_matches(text) == legacy_matches(old, text), repr(text)
