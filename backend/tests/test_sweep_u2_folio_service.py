"""U2 regressions for FolioService's folio-python integration.

- FOLIO construction must not log folio-python's "Failed to initialize LLM model"
  traceback (it treats llm=None as "build a default OpenAI client").
- search_by_prefix: folio-python 0.3.6 returns List[OWLClass], not (class, score)
  tuples, so the old ``for c, _ in results`` unpack always fell into the except
  branch and returned [].
"""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import pytest

from app.services.folio.folio_service import FolioService


class _FakeFOLIO:
    """Mimics FOLIO.__init__'s LLM-init behavior without loading an ontology."""

    instances: list = []

    def __init__(self, llm=None, **kwargs):
        self.kwargs = kwargs
        self.llm = object() if llm is None else llm  # folio builds a default client
        logging.getLogger("folio.graph").warning(
            "Failed to initialize LLM model: %s", "Traceback ... ValueError: OpenAI API key not found"
        )
        logging.getLogger("folio.graph").warning("unrelated folio warning")
        _FakeFOLIO.instances.append(self)


def test_folio_load_suppresses_llm_init_traceback(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "folio", SimpleNamespace(FOLIO=_FakeFOLIO))
    caplog.set_level(logging.WARNING, logger="folio.graph")

    instance = FolioService()._load_folio()

    assert isinstance(instance, _FakeFOLIO)
    assert instance.llm is None  # no OpenAI client held
    messages = [r.getMessage() for r in caplog.records if r.name == "folio.graph"]
    assert not any("Failed to initialize LLM model" in m for m in messages)
    # Only that one warning is filtered, and the filter is removed afterwards.
    assert "unrelated folio warning" in messages
    assert not logging.getLogger("folio.graph").filters


def _owl_class(iri: str, label: str):
    return SimpleNamespace(
        iri=iri,
        label=label,
        preferred_label=None,
        alternative_labels=[],
        definition=None,
        sub_class_of=[],
        parent_class_of=[],
        see_also=[],
        examples=[],
        translations={},
        is_defined_by=None,
        deprecated=False,
        hidden_label=None,
    )


def test_search_by_prefix_returns_concepts():
    classes = [
        _owl_class("https://folio.openlegalstandard.org/RAAA1", "Contract Law"),
        _owl_class("https://folio.openlegalstandard.org/RAAA2", "Contractor"),
    ]

    class _Folio:
        def search_by_prefix(self, prefix, case_sensitive=False):
            return list(classes)  # folio-python 0.3.6 shape: List[OWLClass]

    svc = FolioService()
    svc._folio = _Folio()
    svc._branch_map = {}

    results = svc.search_by_prefix("contr", top_k=1)
    assert [c.preferred_label for c in results] == ["Contract Law"]
    assert len(svc.search_by_prefix("contr")) == 2


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("multi", [False, True])
def test_translation_alternatives_respect_matching_switch(monkeypatch, enabled, multi):
    from app.config import settings

    concept = _owl_class("https://folio.openlegalstandard.org/SHARES", "Shares")
    concept.alternative_labels = ["Stock", "Actions", "Aktien"]
    concept.translations = {"fr-fr": "Actions", "de-de": "Aktien"}
    svc = FolioService()
    svc._folio = SimpleNamespace(classes=[concept])
    svc._branch_map = {}
    svc._lemma_map = {}  # No NLP models or disk caches needed for label types.
    monkeypatch.setattr(settings, "translation_matching_enabled", enabled)

    labels = svc.get_all_labels_multi() if multi else svc.get_all_labels()
    entries = labels if multi else {key: [info] for key, info in labels.items()}
    assert [(info.concept.iri, info.label_type) for info in entries["stock"]] == [
        (concept.iri, "alternative")
    ]
    for text in ("actions", "aktien"):
        assert [info.label_type for info in entries.get(text, [])] == (
            ["translation"] if enabled else []
        )
    converted = svc._to_folio_concept(concept)
    assert converted.alternative_labels == ["Stock"]
    assert converted.translations == concept.translations


def test_translation_filter_preserves_exact_match_rule_and_order():
    concept = _owl_class("https://folio.openlegalstandard.org/SHARES", "Shares")
    concept.alternative_labels = ["Stock", "Actions", "actions", "Shares", "Equity", "Stock"]
    concept.translations = {"fr-fr": "Actions", "en-gb": "Shares"}
    svc = FolioService()
    svc._branch_map = {}

    converted = svc._to_folio_concept(concept)

    assert converted.alternative_labels == ["Stock", "actions", "Equity", "Stock"]
    assert converted.preferred_label == "Shares"
    assert converted.translations == concept.translations
    assert concept.alternative_labels == ["Stock", "Actions", "actions", "Shares", "Equity", "Stock"]


def test_lemma_cache_tracks_alternative_labels(monkeypatch, tmp_path):
    from app.services.folio import folio_service as module
    from app.services.folio import owl_cache
    from app.services.nlp import spacy_singleton

    monkeypatch.setattr(module, "_LEMMA_CACHE_DIR", tmp_path)
    monkeypatch.setattr(owl_cache, "get_owl_content_hash", lambda: "same-owl")

    class FakeNLP:
        pipe_names = ["tagger", "attribute_ruler"]

        def pipe(self, texts, batch_size):
            for text in texts:
                class Doc(list):
                    pass
                doc = Doc([SimpleNamespace(lemma_=text.removesuffix("s"))])
                doc.text = text
                yield doc

    monkeypatch.setattr(spacy_singleton, "get_spacy_tokenizer", FakeNLP)

    def service(alts):
        concept = _owl_class("https://folio.openlegalstandard.org/SHARES", "Shares")
        concept.alternative_labels = alts
        svc = FolioService()
        svc._folio = SimpleNamespace(classes=[concept])
        svc._branch_map = {}
        return svc

    assert service(["Stocks"])._compute_label_lemmas().get("stocks") == "stock"
    changed = service(["Bonds"])._compute_label_lemmas()
    assert "stocks" not in changed
    assert changed.get("bonds") == "bond"
    assert len(list(tmp_path.glob("*.pkl"))) == 2
