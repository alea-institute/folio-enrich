"""U2 regressions for FolioService's folio-python integration.

- FOLIO construction must not log folio-python's "Failed to initialize LLM model"
  traceback (it treats llm=None as "build a default OpenAI client").
- search_by_prefix: folio-python 0.3.6 returns List[OWLClass], not (class, score)
  tuples, so the old ``for c, _ in results`` unpack always fell into the except
  branch and returned [].
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import folio as folio_pkg

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
    monkeypatch.setattr(folio_pkg, "FOLIO", _FakeFOLIO)
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
