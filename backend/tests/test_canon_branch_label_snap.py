"""WS-E: canonicalize LLM-emitted branch labels to canonical root labels.

LLM-extracted concepts that do NOT resolve to an ontology IRI carry the LLM's
free-text branch guess, which is often a stripped form of the canonical root label
(e.g. ``"Normative Concepts"`` instead of the full ``"Normative Concepts (e.g.,
Ethics, Morals, Laws)"``). That gives one root two stable colors in the UI. These
tests cover the snapping helper plus the resolver-fallback chokepoint, and assert
FOLIO stays byte-neutral (gated off for the default ontology).
"""

from __future__ import annotations

import pytest

from app.services.folio.concept_detail import (
    _CANON_ROOT_LABELS_CACHE,
    canonicalize_branch_label,
)
from app.services.folio.resolver import ConceptResolver
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC

OWL_THING = "http://www.w3.org/2002/07/owl#Thing"

NORMATIVE_FULL = "Normative Concepts (e.g., Ethics, Morals, Laws)"
AUTHORITY_FULL = "Authority (Source and Scope)"


class _FakeCls:
    def __init__(self, iri, label, sub_class_of, parent_class_of=(), definition=""):
        self.iri = iri
        self.label = label
        self.sub_class_of = list(sub_class_of)
        self.parent_class_of = list(parent_class_of)
        self.definition = definition


class _FakeFolio:
    def __init__(self, classes):
        self.classes = classes
        self._by_iri = {c.iri: c for c in classes}

    def __getitem__(self, iri):
        return self._by_iri.get(iri)


def _canon_folio():
    """Canon-shaped ontology whose top-level branches are IMPLICIT roots (no
    ``sub_class_of``), matching the real Canon."""
    base = "https://ontology.catholicos.catholic/"
    return _FakeFolio([
        _FakeCls(base + "Actor", "Actor", [OWL_THING]),
        _FakeCls(base + "Authority", AUTHORITY_FULL, []),
        _FakeCls(base + "Normative", NORMATIVE_FULL, []),
        _FakeCls(base + "Operational", "Operational Concepts", []),
        _FakeCls(base + "Place", "Place", []),
    ])


def _ambiguous_folio():
    """Two roots that share a common prefix word — snapping must NOT guess."""
    base = "https://ontology.catholicos.catholic/"
    return _FakeFolio([
        _FakeCls(base + "AA", "Sacred Order Aleph", []),
        _FakeCls(base + "BB", "Sacred Order Bravo", []),
    ])


class _FakeService:
    """Minimal FolioService stand-in exposing ``.spec`` and ``._get_folio()``."""

    def __init__(self, folio, spec):
        self._folio = folio
        self.spec = spec

    def _get_folio(self):
        return self._folio


@pytest.fixture(autouse=True)
def _clear_root_cache():
    """Keep the per-ontology root-label cache hermetic across tests."""
    _CANON_ROOT_LABELS_CACHE.clear()
    yield
    _CANON_ROOT_LABELS_CACHE.clear()


# --------------------------------------------------------------------------- #
# canonicalize_branch_label — unit
# --------------------------------------------------------------------------- #
class TestCanonicalizeBranchLabel:
    def test_prefix_snaps_to_full_normative(self):
        folio = _canon_folio()
        assert (
            canonicalize_branch_label("Normative Concepts", folio, CANON_SPEC)
            == NORMATIVE_FULL
        )

    def test_prefix_snaps_to_full_authority(self):
        folio = _canon_folio()
        assert (
            canonicalize_branch_label("Authority", folio, CANON_SPEC) == AUTHORITY_FULL
        )

    def test_exact_match_fixes_casing(self):
        folio = _canon_folio()
        assert (
            canonicalize_branch_label("operational concepts", folio, CANON_SPEC)
            == "Operational Concepts"
        )

    def test_exact_full_label_returned_unchanged(self):
        folio = _canon_folio()
        assert (
            canonicalize_branch_label(NORMATIVE_FULL, folio, CANON_SPEC)
            == NORMATIVE_FULL
        )

    def test_no_match_passthrough(self):
        folio = _canon_folio()
        # An LLM-invented branch absent from the ontology is returned unchanged.
        assert (
            canonicalize_branch_label("Ecclesiastical Widgets", folio, CANON_SPEC)
            == "Ecclesiastical Widgets"
        )

    def test_midword_prefix_does_not_snap(self):
        folio = _canon_folio()
        # "Norm" is a raw string prefix of "Normative ..." but not a word boundary.
        assert canonicalize_branch_label("Norm", folio, CANON_SPEC) == "Norm"

    def test_ambiguous_prefix_passthrough(self):
        folio = _ambiguous_folio()
        # "Sacred Order" is a boundary prefix of TWO roots of equal length → no guess.
        assert (
            canonicalize_branch_label("Sacred Order", folio, CANON_SPEC)
            == "Sacred Order"
        )

    def test_empty_passthrough(self):
        folio = _canon_folio()
        assert canonicalize_branch_label("", folio, CANON_SPEC) == ""

    def test_folio_default_is_noop(self):
        # Byte-neutrality: for the registry default (FOLIO) the helper never snaps,
        # even when the label would otherwise match a canonical root.
        folio = _canon_folio()
        assert (
            canonicalize_branch_label("Normative Concepts", folio, FOLIO_SPEC)
            == "Normative Concepts"
        )


# --------------------------------------------------------------------------- #
# Resolver fallback chokepoint (source='llm', no ontology branch)
# --------------------------------------------------------------------------- #
class TestResolverFallback:
    def _resolver(self, spec):
        service = _FakeService(_canon_folio(), spec)
        return ConceptResolver(folio_service=service)

    def test_canon_fallback_snaps_stripped_label(self, monkeypatch):
        from app.services.folio import folio_service as fs_mod

        resolver = self._resolver(CANON_SPEC)

        # Force the fallback path: best concept resolves with an EMPTY branch, so
        # resolve() falls back to the (LLM-guessed) input branches.
        branchless = fs_mod.FOLIOConcept(
            iri="https://ontology.catholicos.catholic/X",
            preferred_label="Some Concept",
            alternative_labels=[],
            definition="",
            branch="",
            parent_iris=[],
        )
        monkeypatch.setattr(
            resolver, "_multi_strategy_resolve", lambda text, branch: (branchless, 0.9)
        )

        resolved = resolver.resolve(
            "some concept", branches=["Normative Concepts"], source="llm"
        )
        assert resolved is not None
        assert resolved.branches == [NORMATIVE_FULL]

    def test_canon_fallback_preserves_multiplicity(self, monkeypatch):
        from app.services.folio import folio_service as fs_mod

        resolver = self._resolver(CANON_SPEC)
        branchless = fs_mod.FOLIOConcept(
            iri="https://ontology.catholicos.catholic/X",
            preferred_label="Some Concept",
            alternative_labels=[],
            definition="",
            branch="",
            parent_iris=[],
        )
        monkeypatch.setattr(
            resolver, "_multi_strategy_resolve", lambda text, branch: (branchless, 0.9)
        )
        # Two branches in, two branches out — only strings normalized.
        resolved = resolver.resolve(
            "some concept",
            branches=["Normative Concepts", "Made Up Branch"],
            source="llm",
        )
        assert resolved is not None
        assert resolved.branches == [NORMATIVE_FULL, "Made Up Branch"]

    def test_folio_fallback_is_byte_neutral(self, monkeypatch):
        from app.services.folio import folio_service as fs_mod

        resolver = self._resolver(FOLIO_SPEC)
        branchless = fs_mod.FOLIOConcept(
            iri="https://folio.openlegalstandard.org/X",
            preferred_label="Some Concept",
            alternative_labels=[],
            definition="",
            branch="",
            parent_iris=[],
        )
        monkeypatch.setattr(
            resolver, "_multi_strategy_resolve", lambda text, branch: (branchless, 0.9)
        )
        resolved = resolver.resolve(
            "some concept", branches=["Normative Concepts"], source="llm"
        )
        assert resolved is not None
        # FOLIO gated off → input branch string passes through unchanged.
        assert resolved.branches == ["Normative Concepts"]
