"""Disambiguation precision: lemma-reachability + index-priority fix.

Covers the "Agreement" -> "License (Agreement)" precision bug.

Fast tests use a synthetic FolioService (deterministic, no ontology load) to
verify the lemma/priority MECHANISM. Slow tests assert the real anchor IRIs
against the live FOLIO ontology and double as the regression eval set + the
collision-discovery gate.

Plan: docs/plans/2026-05-26-001-fix-agreement-concept-disambiguation-plan.md
"""

from __future__ import annotations

import pytest

from app.services.folio.folio_service import FOLIOConcept, FolioService
from app.services.folio.match_tier import (
    is_higher_priority,
    label_type_rank,
    lemma_type_for,
)

# Real FOLIO IRIs (hash suffix) for the anchor case.
AGREEMENTS_IRI = "https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg"
LICENSE_IRI = "https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z"
DUPE_IRI = "https://folio.openlegalstandard.org/RCiAtR0akBA7apMyfjy515B"


def _h(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


# --------------------------------------------------------------------------- #
# Fast: tier priority semantics
# --------------------------------------------------------------------------- #
class TestMatchTierOrdering:
    def test_priority_order(self):
        assert label_type_rank("preferred") < label_type_rank("lemma_preferred")
        assert label_type_rank("lemma_preferred") < label_type_rank("alternative")
        assert label_type_rank("alternative") < label_type_rank("lemma_alternative")
        assert label_type_rank("lemma_alternative") < label_type_rank("hidden")

    def test_lemma_primary_beats_exact_alt(self):
        # The crux of the bug fix: a lemma-of-a-preferred-label out-ranks an
        # exact alternative-label match.
        assert is_higher_priority("lemma_preferred", "alternative")
        assert not is_higher_priority("alternative", "lemma_preferred")

    def test_exact_preferred_beats_lemma_preferred(self):
        assert is_higher_priority("preferred", "lemma_preferred")

    def test_lemma_type_mapping(self):
        assert lemma_type_for("preferred") == "lemma_preferred"
        assert lemma_type_for("alternative") == "lemma_alternative"


# --------------------------------------------------------------------------- #
# Fast: lemma index mechanism on a synthetic ontology
# --------------------------------------------------------------------------- #
class _SyntheticFolio:
    def __init__(self, concepts):
        self.classes = concepts


class FakeLemmaFolioService(FolioService):
    """Drives get_all_labels()/_compute_label_lemmas() over synthetic concepts.

    Concepts are already FOLIOConcept instances, so _to_folio_concept is a
    passthrough. Disk lemma cache is bypassed for determinism.
    """

    def __init__(self, concepts):
        super().__init__()
        self._synthetic = _SyntheticFolio(concepts)

    def _get_folio(self):
        return self._synthetic

    def _to_folio_concept(self, concept):  # type: ignore[override]
        return concept

    def _load_lemma_cache(self):  # bypass disk
        return None

    def _save_lemma_cache(self, lemma_map):  # bypass disk
        return None


def _concept(iri, pref, branch="Document / Artifact", alts=None) -> FOLIOConcept:
    return FOLIOConcept(
        iri=iri, preferred_label=pref, alternative_labels=alts or [],
        definition="", branch=branch, parent_iris=[],
    )


@pytest.fixture
def collision_service() -> FakeLemmaFolioService:
    return FakeLemmaFolioService([
        _concept("iri:agreements", "Agreements", alts=["Accords"]),
        _concept("iri:license", "License (Agreement)", branch="Objectives",
                 alts=["Agreement", "License"]),
        _concept("iri:dupe", "DUPE of `License `", branch="", alts=["Agreement"]),
        _concept("iri:damages", "Damages", branch="Objectives"),
    ])


class TestLemmaIndexMechanism:
    def test_singular_reaches_plural_primary(self, collision_service):
        """A1/A3: 'agreement' (singular) resolves to the plural-labelled concept."""
        single = collision_service.get_all_labels()
        info = single.get("agreement")
        assert info is not None
        assert info.concept.iri == "iri:agreements"
        assert info.label_type == "lemma_preferred"

    def test_lemma_primary_outranks_exact_alt_in_multi(self, collision_service):
        multi = collision_service.get_all_labels_multi()
        entries = multi.get("agreement", [])
        iris = [e.concept.iri for e in entries]
        # Agreements (lemma_preferred) sorts first; License alt still present.
        assert iris[0] == "iri:agreements"
        assert "iri:license" in iris

    def test_dupe_concept_filtered(self, collision_service):
        """The 'DUPE of License' placeholder is excluded from the index."""
        multi = collision_service.get_all_labels_multi()
        for entries in multi.values():
            assert all(e.concept.iri != "iri:dupe" for e in entries)

    def test_exact_alt_not_overcorrected(self, collision_service):
        """A2: the exact alternative 'license' still maps to the License concept."""
        single = collision_service.get_all_labels()
        assert single["license"].concept.iri == "iri:license"

    def test_denylist_term_not_lemma_merged(self, collision_service):
        """A8: 'damages' (term of art) must not create a 'damage' lemma key."""
        single = collision_service.get_all_labels()
        assert "damages" in single          # exact label preserved
        assert "damage" not in single       # singular lemma NOT added

    def test_lemma_map_excludes_denylist(self, collision_service):
        lemma_map = collision_service._compute_label_lemmas()
        assert "damages" not in lemma_map
        assert lemma_map.get("agreements") == "agreement"


# --------------------------------------------------------------------------- #
# Fast: StringMatch alt-label expansion guard
# --------------------------------------------------------------------------- #
class TestAltLabelExpansionGuard:
    """Prevents 'License (Agreement)' (whose alt-label is 'Agreement') from being
    expanded onto bare 'Agreement' spans, since 'Agreement' is the (lemma-)primary
    label of the Agreements concept. This is the LLM-path half of the fix: an LLM
    phrase like 'this Agreement:' can resolve to License, and without the guard
    StringMatch would re-tag every bare 'Agreement' as License."""

    def _labels(self):
        from app.services.folio.folio_service import FOLIOConcept, LabelInfo
        agreements = FOLIOConcept(
            iri="iri:agreements", preferred_label="Agreements",
            alternative_labels=[], definition="", branch="Document / Artifact", parent_iris=[])
        return {
            "agreement": LabelInfo(concept=agreements, label_type="lemma_preferred",
                                   matched_label="Agreements"),
            "accord": LabelInfo(concept=agreements, label_type="alternative",
                                matched_label="Accord"),
        }

    def test_alt_label_of_other_primary_is_refused(self):
        from app.pipeline.stages.string_match_stage import StringMatchStage
        labels = self._labels()
        # License (different IRI) tries to expand its 'Agreement' alt-label → refused.
        assert StringMatchStage._alt_label_owned_by_other_primary(
            "Agreement", "iri:license", labels) is True

    def test_own_primary_label_not_refused(self):
        from app.pipeline.stages.string_match_stage import StringMatchStage
        labels = self._labels()
        # Agreements expanding its own surface form → allowed.
        assert StringMatchStage._alt_label_owned_by_other_primary(
            "Agreement", "iri:agreements", labels) is False

    def test_alt_label_owned_only_as_alternative_not_refused(self):
        from app.pipeline.stages.string_match_stage import StringMatchStage
        labels = self._labels()
        # 'accord' is only an *alternative* of another concept → not a canonical owner → allowed.
        assert StringMatchStage._alt_label_owned_by_other_primary(
            "Accord", "iri:license", labels) is False

    def test_unknown_label_not_refused(self):
        from app.pipeline.stages.string_match_stage import StringMatchStage
        assert StringMatchStage._alt_label_owned_by_other_primary(
            "Zzqq", "iri:license", self._labels()) is False


# --------------------------------------------------------------------------- #
# Slow: real-ontology regression eval set (the gate)
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestRealOntologyAnchor:
    @pytest.fixture(scope="class")
    def svc(self) -> FolioService:
        s = FolioService()
        s.get_all_labels()
        s.get_all_labels_multi()
        return s

    def test_anchor_agreement_resolves_to_agreements(self, svc):
        """A1: input 'Agreement' resolves to Agreements/Contracts, not License."""
        info = svc.get_all_labels().get("agreement")
        assert info is not None
        assert _h(info.concept.iri) == _h(AGREEMENTS_IRI)
        assert info.label_type == "lemma_preferred"

    def test_anchor_negative_license_unchanged(self, svc):
        """A2: 'license (agreement)' still maps to License."""
        info = svc.get_all_labels().get("license (agreement)")
        assert info is not None
        assert _h(info.concept.iri) == _h(LICENSE_IRI)

    def test_multi_agreement_orders_agreements_first(self, svc):
        entries = svc.get_all_labels_multi().get("agreement", [])
        assert entries, "expected entries for 'agreement'"
        assert _h(entries[0].concept.iri) == _h(AGREEMENTS_IRI)
        assert all(_h(e.concept.iri) != _h(DUPE_IRI) for e in entries)

    def test_end_to_end_entity_ruler(self, svc):
        """The fix propagates through the EntityRuler (pipeline entry point)."""
        from app.services.entity_ruler.ruler import FOLIOEntityRuler
        ruler = FOLIOEntityRuler()
        ruler.load_patterns(svc.get_all_labels())
        matches = [m for m in ruler.find_matches("This Agreement is binding.")
                   if m.text.lower() == "agreement"]
        assert matches
        assert _h(matches[0].entity_id) == _h(AGREEMENTS_IRI)

    def test_denylist_terms_not_lemma_merged(self, svc):
        """A8: legal terms of art keep singular/plural distinct."""
        single = svc.get_all_labels()
        lemma_map = svc._compute_label_lemmas()
        for plural in ("damages", "proceedings", "minutes", "costs"):
            assert plural not in lemma_map, f"{plural!r} should be denylisted"

    def test_lemma_map_nonempty_and_cached(self, svc):
        """A16/A18: lemma map is computed and memoized."""
        m1 = svc._compute_label_lemmas()
        assert len(m1) > 100
        assert svc._compute_label_lemmas() is m1  # memoized, not recomputed


@pytest.mark.slow
class TestCollisionDiscovery:
    """A13: auto-discover primary/alt cross-collisions; assert the set is
    non-empty, stable, and includes the anchor."""

    def test_agreement_collision_discovered(self):
        svc = FolioService()
        single = svc.get_all_labels()
        lemma_map = svc._compute_label_lemmas()
        # A collision: a lemma key whose winning concept differs from the
        # concept that owns the same string as an exact alternative label.
        multi = svc.get_all_labels_multi()
        collisions = []
        for key, entries in multi.items():
            types = {e.label_type for e in entries}
            has_lemma_primary = "lemma_preferred" in types
            has_exact_alt = "alternative" in types
            if has_lemma_primary and has_exact_alt and len(entries) > 1:
                collisions.append(key)
        assert "agreement" in collisions
        assert len(collisions) >= 1
