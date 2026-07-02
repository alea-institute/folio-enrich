import pytest

from app.services.folio.folio_service import FOLIOConcept, FolioService
from app.services.folio.resolver import ConceptResolver


class FakeFolioService(FolioService):
    """Fake FOLIO service that returns pre-configured results without loading the ontology."""

    def __init__(self):
        super().__init__()
        self._fake_concepts = {
            "breach of contract": FOLIOConcept(
                iri="https://folio.openlegalstandard.org/R001",
                preferred_label="Breach of Contract",
                alternative_labels=["contract breach"],
                definition="Failure to perform contractual obligations",
                branch="Objectives",
                parent_iris=[],
            ),
            "damages": FOLIOConcept(
                iri="https://folio.openlegalstandard.org/R002",
                preferred_label="Damages",
                alternative_labels=["monetary damages"],
                definition="Monetary compensation for loss or injury",
                branch="Objectives",
                parent_iris=[],
            ),
            "court": FOLIOConcept(
                iri="https://folio.openlegalstandard.org/R003",
                preferred_label="Court",
                alternative_labels=["tribunal"],
                definition="A tribunal for the administration of justice",
                branch="Legal Entity",
                parent_iris=[],
            ),
        }
        self._by_iri = {c.iri: c for c in self._fake_concepts.values()}

    def _get_folio(self):
        """Raise so multi_strategy_search falls back to search_by_label."""
        raise RuntimeError("FakeFolioService: no real ontology")

    def search_by_label(self, label: str, top_k: int = 5) -> list[tuple[FOLIOConcept, float]]:
        key = label.lower()
        if key in self._fake_concepts:
            return [(self._fake_concepts[key], 0.95)]
        # Partial match
        for k, v in self._fake_concepts.items():
            if key in k or k in key:
                return [(v, 0.7)]
        return []

    def get_concept(self, iri: str) -> FOLIOConcept | None:
        return self._by_iri.get(iri)


class TestConceptResolver:
    def test_resolve_known_concept(self):
        resolver = ConceptResolver(FakeFolioService())
        result = resolver.resolve("breach of contract", branches=["Objectives"], confidence=0.9)
        assert result is not None
        assert result.folio_concept.iri == "https://folio.openlegalstandard.org/R001"
        assert result.folio_concept.preferred_label == "Breach of Contract"

    def test_resolve_unknown_concept(self):
        resolver = ConceptResolver(FakeFolioService())
        result = resolver.resolve("quantum computing", branches=["Service"])
        assert result is None

    def test_resolve_caches_results(self):
        resolver = ConceptResolver(FakeFolioService())
        result1 = resolver.resolve("damages")
        result2 = resolver.resolve("damages")
        assert result1 is result2
        assert resolver.cache_size == 1

    def test_resolve_batch(self):
        resolver = ConceptResolver(FakeFolioService())
        results = resolver.resolve_batch([
            {"concept_text": "breach of contract", "branches": ["Objectives"], "confidence": 0.9},
            {"concept_text": "damages", "branches": [], "confidence": 0.8},
            {"concept_text": "unknown concept xyz", "branches": [], "confidence": 0.5},
        ])
        assert len(results) == 3
        assert results[0] is not None
        assert results[1] is not None
        assert results[2] is None

    def test_cache_is_case_insensitive(self):
        resolver = ConceptResolver(FakeFolioService())
        r1 = resolver.resolve("Court")
        r2 = resolver.resolve("court")
        assert r1 is r2
        assert resolver.cache_size == 1

    def test_resolve_by_iri(self):
        """When folio_iri is provided, resolver looks up directly instead of searching."""
        resolver = ConceptResolver(FakeFolioService())
        result = resolver.resolve(
            "some text",
            folio_iri="https://folio.openlegalstandard.org/R001",
            confidence=0.80,
        )
        assert result is not None
        assert result.folio_concept.iri == "https://folio.openlegalstandard.org/R001"
        assert result.folio_concept.preferred_label == "Breach of Contract"

    def test_resolve_by_iri_fallback_to_search(self):
        """When IRI lookup fails, falls back to label search."""
        resolver = ConceptResolver(FakeFolioService())
        result = resolver.resolve(
            "court",
            folio_iri="https://folio.openlegalstandard.org/NONEXISTENT",
        )
        # Falls back to search_by_label("court") which finds Court
        assert result is not None
        assert result.folio_concept.preferred_label == "Court"


class TestMultiSearchCache:
    """The cross-request multi_strategy_search cache must return identical results
    and avoid re-running the search for a repeated (text, branch, top_n)."""

    class _MiniFolio(FolioService):
        def __init__(self):
            super().__init__()

        def _get_folio(self):
            return object()  # dummy graph; multi_strategy_search is monkeypatched

        def _get_branch(self, iri, parents):
            return "Objectives"

    def test_repeat_query_is_cache_hit_with_identical_results(self, monkeypatch):
        calls = {"n": 0}

        def fake_search(folio_raw, concept_text, branch=None, top_n=5, get_branch_fn=None):
            calls["n"] += 1
            return [{
                "iri": "https://folio.openlegalstandard.org/R1",
                "label": "Foo", "synonyms": [], "definition": "d",
                "branch": "Objectives", "score": 90,
            }]

        monkeypatch.setattr("app.services.folio.search.multi_strategy_search", fake_search)
        r = ConceptResolver(self._MiniFolio())

        a = r._multi_strategy_resolve_all("foo bar", "", 5)
        b = r._multi_strategy_resolve_all("foo bar", "", 5)

        assert calls["n"] == 1  # second call served from cache
        assert [(c.iri, round(s, 4)) for c, s in a] == [(c.iri, round(s, 4)) for c, s in b]

    def test_cache_returns_copy_safe_against_inplace_sort(self, monkeypatch):
        """_multi_strategy_resolve_all sorts results in place when a branch hint is
        given; the cache must hand out copies so it isn't corrupted."""
        def fake_search(folio_raw, concept_text, branch=None, top_n=5, get_branch_fn=None):
            return [
                {"iri": "iri/A", "label": "A", "synonyms": [], "definition": "",
                 "branch": "Other", "score": 95},
                {"iri": "iri/B", "label": "B", "synonyms": [], "definition": "",
                 "branch": "Objectives", "score": 80},
            ]

        monkeypatch.setattr("app.services.folio.search.multi_strategy_search", fake_search)
        r = ConceptResolver(self._MiniFolio())
        # branch hint triggers in-place sort of the returned list
        first = r._multi_strategy_resolve_all("q", "Objectives", 5)
        second = r._multi_strategy_resolve_all("q", "Objectives", 5)
        assert [c.iri for c, _ in first] == [c.iri for c, _ in second]
