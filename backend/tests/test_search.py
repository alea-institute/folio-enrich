"""Tests for the multi-strategy search orchestration.

The word-order-invariant scorer, stopwords, tokenizer, and legal expansions were retired from
this module in the folio-resolve migration (SCHEDULE.md row 2) — they now live in, and are
unit-tested by, ``folio_resolve.scoring`` (see the library's ``tests/test_scoring.py``). What
remains here is folio-enrich's own orchestration: the 7-strategy folio-python candidate gathering
in ``multi_strategy_search`` and the deterministic precision gates wired at its boundary.
"""

import pytest

from app.services.folio.search import candidate_vetoed, multi_strategy_search


class FakeOWLClass:
    """Minimal mock of an OWL class from folio-python."""
    def __init__(self, iri, label, definition=None, alt_labels=None, sub_class_of=None, preferred_label=None):
        self.iri = iri
        self.label = label
        self.definition = definition
        self.alternative_labels = alt_labels or []
        self.sub_class_of = sub_class_of or []
        self.preferred_label = preferred_label


class FakeFOLIO:
    """Minimal mock of folio-python's FOLIO class."""
    def __init__(self, concepts: list[FakeOWLClass]):
        self._by_hash = {}
        for c in concepts:
            h = c.iri.rsplit("/", 1)[-1]
            self._by_hash[h] = c

    def __getitem__(self, key):
        return self._by_hash.get(key)

    def search_by_label(self, text, include_alt_labels=True, limit=25):
        text_lower = text.lower()
        results = []
        for c in self._by_hash.values():
            if text_lower in (c.label or "").lower():
                results.append((c, 0.9))
            elif any(text_lower in alt.lower() for alt in c.alternative_labels):
                results.append((c, 0.7))
        return results[:limit]

    def search_by_prefix(self, prefix):
        prefix_lower = prefix.lower()
        return [
            c for c in self._by_hash.values()
            if (c.label or "").lower().startswith(prefix_lower)
        ]

    def search_by_definition(self, text, limit=20):
        text_lower = text.lower()
        results = []
        for c in self._by_hash.values():
            if c.definition and text_lower in c.definition.lower():
                results.append((c, 0.5))
        return results[:limit]


class TestMultiStrategySearch:
    @pytest.fixture
    def mock_folio(self):
        return FakeFOLIO([
            FakeOWLClass(
                iri="https://folio.openlegalstandard.org/HASH001",
                label="Breach of Contract",
                definition="Failure to perform contractual obligations",
                alt_labels=["contract breach"],
            ),
            FakeOWLClass(
                iri="https://folio.openlegalstandard.org/HASH002",
                label="Criminal Law",
                definition="Body of law relating to crime",
                alt_labels=["penal law"],
            ),
            FakeOWLClass(
                iri="https://folio.openlegalstandard.org/HASH003",
                label="Employment Discrimination",
                definition="Discrimination in the workplace based on protected characteristics",
            ),
            FakeOWLClass(
                iri="https://folio.openlegalstandard.org/HASH004",
                label="Litigation Practice",
                definition="Practice of conducting lawsuits",
            ),
        ])

    def test_exact_match_returns_high_score(self, mock_folio):
        results = multi_strategy_search(mock_folio, "Breach of Contract", top_n=5)
        assert len(results) > 0
        assert results[0]["iri_hash"] == "HASH001"
        # Library scorer: whole-string exact match scores 99.0 (was graduated 97 in the fork).
        assert results[0]["score"] == 99.0

    def test_returns_dicts_with_expected_keys(self, mock_folio):
        results = multi_strategy_search(mock_folio, "criminal", top_n=5)
        if results:
            r = results[0]
            for key in ("label", "iri", "iri_hash", "score", "definition", "synonyms", "branch"):
                assert key in r

    def test_no_results_for_unrelated_query(self, mock_folio):
        results = multi_strategy_search(mock_folio, "quantum physics", top_n=5)
        high_scoring = [r for r in results if r["score"] >= 50]
        assert len(high_scoring) == 0

    def test_respects_top_n(self, mock_folio):
        results = multi_strategy_search(mock_folio, "law", top_n=2)
        assert len(results) <= 2

    def test_legal_expansion_finds_practice(self, mock_folio):
        results = multi_strategy_search(mock_folio, "litigation", top_n=5)
        labels = [r["label"] for r in results]
        assert "Litigation Practice" in labels

    def test_place_branch_candidate_is_vetoed(self):
        """A generic query that fuzzy-latches a governmental-body label is dropped by the gate."""
        folio = FakeFOLIO([
            FakeOWLClass(
                iri="https://folio.openlegalstandard.org/PLACE01",
                label="U.S. Dept. of Justice",
                definition="A federal executive department",
                alt_labels=["justice"],
            ),
        ])
        # With a branch resolver marking it a Governmental Body, the surface term "justice"
        # (!= the label) must be vetoed rather than returned as a mis-map.
        results = multi_strategy_search(
            folio, "justice", top_n=5,
            get_branch_fn=lambda _f, _h: "Governmental Body",
        )
        assert all(r["iri_hash"] != "PLACE01" for r in results)


class TestCandidateVetoed:
    def test_exact_place_name_not_vetoed(self):
        # Surface term exactly equal to the place label is a real mention -> allowed.
        assert not candidate_vetoed("Delaware", "Delaware", "Location", "iri", 100.0)

    def test_generic_term_to_place_vetoed(self):
        assert candidate_vetoed("law", "Delaware", "Location", "iri", 90.0)

    def test_non_place_not_vetoed(self):
        assert not candidate_vetoed("arbitration", "Arbitration Practice", "Service", "iri", 92.0)
