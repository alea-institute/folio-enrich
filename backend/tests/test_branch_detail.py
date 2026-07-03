"""Tests for ontology-native branch detail (WS-2).

FOLIO keeps its own legal taxonomy byte-identically; non-FOLIO ontologies derive
their OWN branches from the OWL (or get a neutral, taxonomy-free scaffold). No
FOLIO branch string may ever leak into another ontology's prompt.
"""

from __future__ import annotations

import pytest

from app.services.concept.branch_judge import BranchJudge
from app.services.llm.base import LLMProvider
from app.services.llm.prompts import templates
from app.services.llm.prompts.concept_identification import build_concept_identification_prompt
from app.services.llm.prompts.templates import (
    _NEUTRAL_BRANCH_SCAFFOLD,
    _build_nonfolio_branch_detail,
    _derive_branch_detail,
    build_branch_detail,
    get_branch_detail,
)
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC

# FOLIO-only branch strings that must NEVER appear in a non-FOLIO prompt.
FOLIO_ONLY_BRANCHES = ("Actor / Player", "Legal Authorities", "Forums and Venues")

OWL_THING = "http://www.w3.org/2002/07/owl#Thing"


class _FakeCls:
    def __init__(self, iri, label, sub_class_of, parent_class_of=(), definition=""):
        self.iri = iri
        self.label = label
        self.sub_class_of = list(sub_class_of)
        self.parent_class_of = list(parent_class_of)
        self.definition = definition


class _FakeFolio:
    """Minimal stand-in for a folio-python FOLIO object (no network)."""

    def __init__(self, classes):
        self.classes = classes
        self._by_iri = {c.iri: c for c in classes}

    def __getitem__(self, iri):
        return self._by_iri.get(iri)


def _canon_like_folio():
    """A tiny Canon-shaped ontology: Event/Actor/Document roots + children + a ZZZ root."""
    base = "https://ontology.catholicos.catholic/"
    sacraments = _FakeCls(base + "Sacraments", "Sacraments", [base + "ReligiousEvents"])
    religious = _FakeCls(
        base + "ReligiousEvents",
        "Religious Events",
        [base + "Event"],
        parent_class_of=[sacraments.iri],
    )
    event = _FakeCls(
        base + "Event",
        "Event",
        [OWL_THING],
        parent_class_of=[religious.iri],
        definition="Something that happens at a given place and time.",
    )
    actor = _FakeCls(base + "Actor", "Actor", [OWL_THING], definition="A participant.")
    document = _FakeCls(base + "Document", "Document", [OWL_THING])
    zzz = _FakeCls(base + "zzz", "ZZZ - Deprecated", [OWL_THING])
    return _FakeFolio([sacraments, religious, event, actor, document, zzz])


def _canon_like_folio_with_implicit_roots():
    """Canon-shaped ontology mixing EXPLICIT ([owl:Thing]) and IMPLICIT (no
    sub_class_of) branch roots, plus editorial ZZZ roots in both forms.

    Mirrors the real Canon, whose top-level branches are declared WITHOUT any
    ``sub_class_of`` (their parenthood to ``owl:Thing`` is left implicit): Actor,
    Document / Artifact and Event are explicit; Authority, Normative Concepts,
    Operational Concepts and Place are implicit. ``ZZZ - Licensing`` /
    ``ZZZZ - Deprecated`` are editorial roots that must drop out. A bare
    ``owl:Thing`` node and a label-less node must also be skipped.
    """
    base = "https://ontology.catholicos.catholic/"
    # Explicit roots (sub_class_of == [owl:Thing])
    actor = _FakeCls(base + "Actor", "Actor", [OWL_THING], definition="A participant.")
    document = _FakeCls(base + "Document", "Document / Artifact", [OWL_THING])
    event = _FakeCls(base + "Event", "Event", [OWL_THING])
    # Implicit roots (NO sub_class_of at all)
    authority = _FakeCls(base + "Authority", "Authority (Source and Scope)", [])
    normative = _FakeCls(base + "Normative", "Normative Concepts (e.g., Ethics, Morals, Laws)", [])
    operational = _FakeCls(base + "Operational", "Operational Concepts", [])
    place = _FakeCls(base + "Place", "Place", [], definition="A location.")
    # Editorial implicit roots — excluded by ZZZ prefix (both single- and quad-Z forms)
    zzz_lic = _FakeCls(base + "zzzLicensing", "ZZZ - Licensing", [])
    zzzz_dep = _FakeCls(base + "zzzzDeprecated", "ZZZZ - Deprecated", [])
    # owl:Thing itself + a label-less node must be skipped
    thing = _FakeCls(OWL_THING, "", [])
    nolabel = _FakeCls(base + "Nolabel", None, [])
    return _FakeFolio([
        actor, document, event, authority, normative, operational, place,
        zzz_lic, zzzz_dep, thing, nolabel,
    ])


# --------------------------------------------------------------------------- #
# FOLIO byte-neutrality
# --------------------------------------------------------------------------- #
class TestFolioByteNeutral:
    def test_folio_detail_contains_folio_branches(self):
        detail = get_branch_detail("folio")
        # FOLIO's own taxonomy must be present (whether OWL-enriched or BRANCH_LIST fallback).
        assert "Actor / Player" in detail
        assert "Legal Authorities" in detail

    def test_folio_detail_matches_folio_helper(self):
        # The public default path must equal FOLIO's dedicated builder verbatim.
        assert build_branch_detail(ontology_id="folio") == templates._build_folio_branch_detail()

    def test_folio_default_argument_uses_folio_path(self):
        assert build_branch_detail() == build_branch_detail(ontology_id="folio")

    def test_folio_detail_deterministic(self):
        assert get_branch_detail("folio") == get_branch_detail("folio")


# --------------------------------------------------------------------------- #
# Canon (non-FOLIO) derivation
# --------------------------------------------------------------------------- #
class TestCanonDerivation:
    def test_derives_canon_roots(self):
        from app.services.folio.concept_detail import _init_branch_roots

        detail = _derive_branch_detail(_canon_like_folio(), CANON_SPEC, _init_branch_roots)
        assert detail is not None
        for root in ("Event", "Actor", "Document"):
            assert root in detail
        # notable child surfaced
        assert "Religious Events" in detail

    def test_excludes_zzz_editorial_root(self):
        from app.services.folio.concept_detail import _init_branch_roots

        detail = _derive_branch_detail(_canon_like_folio(), CANON_SPEC, _init_branch_roots)
        assert "ZZZ" not in detail
        assert "Deprecated" not in detail

    def test_no_folio_taxonomy_leaks(self):
        from app.services.folio.concept_detail import _init_branch_roots

        detail = _derive_branch_detail(_canon_like_folio(), CANON_SPEC, _init_branch_roots)
        for folio_branch in FOLIO_ONLY_BRANCHES:
            assert folio_branch not in detail

    def test_no_roots_returns_none(self):
        from app.services.folio.concept_detail import _init_branch_roots

        base = "https://ontology.catholicos.catholic/"
        # A single non-root class (parented to another class, not owl:Thing).
        orphan = _FakeCls(base + "Leaf", "Leaf", [base + "Missing"])
        detail = _derive_branch_detail(_FakeFolio([orphan]), CANON_SPEC, _init_branch_roots)
        assert detail is None


# --------------------------------------------------------------------------- #
# Neutral scaffold (no derivable branches / failed service)
# --------------------------------------------------------------------------- #
class TestNeutralScaffold:
    def test_scaffold_has_no_folio_taxonomy(self):
        for folio_branch in FOLIO_ONLY_BRANCHES:
            assert folio_branch not in _NEUTRAL_BRANCH_SCAFFOLD

    def test_failed_service_returns_scaffold(self, monkeypatch):
        from app.services.folio.folio_service import FolioService

        def boom(ontology_id=None):
            raise RuntimeError("no network")

        monkeypatch.setattr(FolioService, "get_instance", staticmethod(boom))
        detail = _build_nonfolio_branch_detail("canon")
        assert detail == _NEUTRAL_BRANCH_SCAFFOLD

    def test_no_root_service_returns_scaffold(self, monkeypatch):
        from app.services.folio.folio_service import FolioService

        base = "https://ontology.catholicos.catholic/"

        class _Svc:
            spec = CANON_SPEC

            def _get_folio(self):
                return _FakeFolio([_FakeCls(base + "Leaf", "Leaf", [base + "Missing"])])

        monkeypatch.setattr(FolioService, "get_instance", staticmethod(lambda ontology_id=None: _Svc()))
        assert _build_nonfolio_branch_detail("canon") == _NEUTRAL_BRANCH_SCAFFOLD


# --------------------------------------------------------------------------- #
# End-to-end: prompts present Canon branches, not FOLIO's
# --------------------------------------------------------------------------- #
class _CapturingLLM(LLMProvider):
    def __init__(self):
        self.prompt = ""

    async def complete(self, prompt, **kw):
        return ""

    async def chat(self, messages, **kw):
        return ""

    async def structured(self, prompt, schema, **kw):
        self.prompt = prompt
        return {"branch": "Event", "confidence": 0.9, "reasoning": "t"}

    async def test_connection(self):
        return True

    async def list_models(self):
        return []


@pytest.fixture
def canon_branch_cache():
    """Seed the per-ontology cache with a derived Canon branch string (no network)."""
    from app.services.folio.concept_detail import _init_branch_roots

    derived = _derive_branch_detail(_canon_like_folio(), CANON_SPEC, _init_branch_roots)
    templates._BRANCH_DETAIL_CACHE["canon"] = derived
    yield derived
    templates._BRANCH_DETAIL_CACHE.pop("canon", None)


class TestPromptsAreOntologyNative:
    def test_concept_prompt_uses_canon_branches(self, canon_branch_cache):
        prompt = build_concept_identification_prompt("The Eucharist is central.", "canon")
        assert "Event" in prompt
        assert "Actor" in prompt
        for folio_branch in FOLIO_ONLY_BRANCHES:
            assert folio_branch not in prompt

    @pytest.mark.asyncio
    async def test_branch_judge_prompt_uses_canon_branches(self, canon_branch_cache, monkeypatch):
        from app.services.folio.folio_service import FolioService

        # Keep _build_folio_context off the network.
        monkeypatch.setattr(
            FolioService,
            "get_instance",
            staticmethod(lambda ontology_id=None: (_ for _ in ()).throw(RuntimeError("no net"))),
        )

        llm = _CapturingLLM()
        judge = BranchJudge(llm)
        await judge.judge(
            "Eucharist",
            "The Eucharist is central to the liturgy.",
            ["Event"],
            ontology_id="canon",
        )
        assert "Event" in llm.prompt
        assert "Religious Events" in llm.prompt
        for folio_branch in FOLIO_ONLY_BRANCHES:
            assert folio_branch not in llm.prompt


# --------------------------------------------------------------------------- #
# Implicit-root discovery (WS-A): Canon exposes ALL its roots, FOLIO stays neutral
# --------------------------------------------------------------------------- #
# The 7 substantive Canon roots (3 explicit + 4 implicit), verified against the
# real 14,973-class Canon OWL.
CANON_SEVEN_ROOTS = (
    "Actor",
    "Authority (Source and Scope)",
    "Document / Artifact",
    "Event",
    "Normative Concepts (e.g., Ethics, Morals, Laws)",
    "Operational Concepts",
    "Place",
)


class TestImplicitRootDiscovery:
    def test_init_branch_roots_discovers_all_seven_canon_roots(self):
        from app.services.folio.concept_detail import _init_branch_roots

        folio = _canon_like_folio_with_implicit_roots()
        roots = _init_branch_roots(folio, CANON_SPEC)
        # Only count roots that are real classes in THIS ontology (drop phantom
        # FOLIO type IRIs the helper always seeds).
        names = sorted({name for iri, name in roots.items() if folio[iri] is not None})
        assert names == sorted(CANON_SEVEN_ROOTS)

    def test_init_branch_roots_excludes_zzz_and_thing_and_empty(self):
        from app.services.folio.concept_detail import _init_branch_roots

        folio = _canon_like_folio_with_implicit_roots()
        roots = _init_branch_roots(folio, CANON_SPEC)
        # Editorial ZZZ/ZZZZ roots excluded
        assert not any("ZZZ" in (name or "").upper() for name in roots.values())
        # owl:Thing itself never a root
        assert OWL_THING not in roots
        # label-less node never a root
        assert "https://ontology.catholicos.catholic/Nolabel" not in roots

    def test_derived_branch_detail_presents_implicit_roots(self):
        from app.services.folio.concept_detail import _init_branch_roots

        detail = _derive_branch_detail(
            _canon_like_folio_with_implicit_roots(), CANON_SPEC, _init_branch_roots
        )
        assert detail is not None
        # The four previously-dropped implicit roots now surface...
        assert "Place" in detail
        assert "Authority" in detail
        assert "Normative" in detail
        assert "Operational" in detail
        # ...alongside the explicit ones...
        assert "Actor" in detail
        assert "Event" in detail
        assert "Document / Artifact" in detail
        # ...and ZZZ editorial roots stay out.
        assert "ZZZ" not in detail

    def test_folio_implicit_roots_not_introduced_as_branches(self):
        """FOLIO byte-neutrality: implicit (no-parent) FOLIO classes such as
        "DEPRECATED Activities" or a label-less node must NOT become branch roots.

        FOLIO's editorial config does not drop "DEPRECATED Activities", so
        implicit-root discovery is gated OFF for the default ontology entirely.
        """
        from app.services.folio.concept_detail import _init_branch_roots

        base = "https://folio.openlegalstandard.org/"
        deprecated = _FakeCls(base + "FakeDeprecatedActivities", "DEPRECATED Activities", [])
        nolabel = _FakeCls(base + "FakeNolabel", None, [])
        real_root = _FakeCls(base + "FakeExplicitRoot", "Fake Explicit Root", [OWL_THING])
        folio = _FakeFolio([deprecated, nolabel, real_root])

        roots = _init_branch_roots(folio, FOLIO_SPEC)
        # The implicit no-parent classes are NOT promoted to roots.
        assert base + "FakeDeprecatedActivities" not in roots
        assert base + "FakeNolabel" not in roots
        assert not any("DEPRECATED" in (name or "").upper() for name in roots.values())
        # The genuine explicit [owl:Thing] root is still discovered (unchanged path).
        assert base + "FakeExplicitRoot" in roots

    def test_default_and_none_spec_are_byte_identical_for_folio(self):
        """For the default ontology, passing FOLIO_SPEC vs no spec yields the
        SAME root set — the gate makes implicit discovery a no-op for FOLIO."""
        from app.services.folio.concept_detail import _init_branch_roots

        base = "https://folio.openlegalstandard.org/"
        deprecated = _FakeCls(base + "FakeDeprecatedActivities", "DEPRECATED Activities", [])
        real_root = _FakeCls(base + "FakeExplicitRoot", "Fake Explicit Root", [OWL_THING])
        folio = _FakeFolio([deprecated, real_root])

        assert _init_branch_roots(folio, FOLIO_SPEC) == _init_branch_roots(folio, None)
