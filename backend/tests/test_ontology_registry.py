"""Tests for the ontology registry foundation (multi-ontology Phase 1).

These are offline: they never load an OWL — constructing a FolioService is lazy,
so we can assert registry/spec/palette behavior without network.
"""

from __future__ import annotations

import pytest

from app.services.folio.folio_service import ConceptRecord, FolioService
from app.services.ontology.registry import (
    OntologyRegistry,
    UnknownOntologyError,
    get_registry,
)
from app.services.ontology.spec import BUILTIN_SPECS, CANON_SPEC, FOLIO_SPEC


class TestOntologyRegistry:
    def test_default_registry_enables_only_folio(self):
        reg = get_registry()
        assert reg.enabled_ids() == ["folio"]
        assert reg.default_id == "folio"
        assert reg.has("folio")
        assert not reg.has("canon")

    def test_get_service_is_cached_per_ontology(self):
        reg = OntologyRegistry({"folio": FOLIO_SPEC})
        svc = reg.get_service("folio")
        assert svc is reg.get_service("folio")  # cached, singleton per ontology
        assert svc is reg.get_service(None)     # None -> default id
        assert isinstance(svc, FolioService)
        assert svc.ontology_id == "folio"
        assert svc.spec is FOLIO_SPEC

    def test_get_instance_delegates_to_registry(self):
        assert FolioService.get_instance() is get_registry().get_service("folio")

    def test_unknown_ontology_raises(self):
        reg = OntologyRegistry({"folio": FOLIO_SPEC})
        with pytest.raises(UnknownOntologyError):
            reg.get_spec("canon")
        with pytest.raises(UnknownOntologyError):
            reg.get_service("canon")

    def test_two_ontologies_get_distinct_services(self):
        reg = OntologyRegistry({"folio": FOLIO_SPEC, "canon": CANON_SPEC})
        folio_svc = reg.get_service("folio")
        canon_svc = reg.get_service("canon")
        assert folio_svc is not canon_svc
        assert folio_svc.spec is FOLIO_SPEC
        assert canon_svc.spec is CANON_SPEC

    def test_from_settings_ignores_unknown_ids(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "enabled_ontologies", ["folio", "bogus"])
        reg = OntologyRegistry.from_settings()
        assert reg.enabled_ids() == ["folio"]

    def test_from_settings_empty_falls_back_to_folio(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "enabled_ontologies", [])
        reg = OntologyRegistry.from_settings()
        assert reg.enabled_ids() == ["folio"]


class TestOntologySpec:
    def test_folio_spec_behavior_matches_legacy_constants(self):
        b = FOLIO_SPEC.behavior
        assert b.prefix_strip == ("folio:", "utbms:", "oasis:")
        assert b.concept_exclude_substrings == ("DUPE",)
        assert b.concept_exclude_prefixes == ("ZZZ:",)
        assert b.property_exclude_substrings == ("DEPRECATED",)
        assert b.property_exclude_prefixes == ("ZZZ:",)
        assert "damages" in b.lemma_denylist and "pleadings" in b.lemma_denylist
        # excluded_branches moved onto behavior (was a shared branch_config constant)
        from app.services.folio.branch_config import EXCLUDED_BRANCHES
        assert b.excluded_branches == EXCLUDED_BRANCHES

    def test_canon_spec_defined_but_distinct(self):
        assert "canon" in BUILTIN_SPECS
        assert CANON_SPEC.coords.source_type == "http"  # github path hardcodes FOLIO.owl
        assert CANON_SPEC.base_iri == "https://ontology.catholicos.catholic/"
        # Canon inherits none of FOLIO's legal terms-of-art rules
        assert CANON_SPEC.behavior.lemma_denylist == frozenset()
        assert CANON_SPEC.behavior.prefix_strip == ()
        # Mixed IRI namespaces (Phase 0 finding)
        assert "http://webprotege.stanford.edu/" in CANON_SPEC.behavior.iri_roots


class TestFolioServiceSpecParameterization:
    def test_strip_prefix_uses_spec(self):
        svc = FolioService(FOLIO_SPEC)
        assert svc._strip_prefix("folio:Foo") == "Foo"
        assert svc._strip_prefix("utbms:Bar") == "Bar"
        assert svc._strip_prefix("plain") == "plain"

    def test_bare_construction_defaults_to_folio(self):
        # FakeFolioService(super().__init__()) relies on this
        assert FolioService().spec is FOLIO_SPEC

    def test_http_source_construction_is_lazy(self):
        # Constructing a source_type="http" ontology does not fetch anything.
        svc = FolioService(CANON_SPEC)
        assert svc.spec is CANON_SPEC
        assert svc._folio is None  # not loaded

    def test_http_source_without_checksum_refuses(self):
        # Integrity is mandatory for http sources — no pin => refuse to load
        # (raises before any network I/O).
        from app.services.ontology.ingestion import OWLIngestionError
        from app.services.ontology.spec import (
            OntologyBehavior,
            OntologyCoords,
            OntologySpec,
        )

        spec = OntologySpec(
            id="unpinned",
            display_name="Unpinned",
            base_iri="https://x/",
            coords=OntologyCoords(
                source_type="http",
                owl_url="https://raw.githubusercontent.com/a/b/main/c.owl",
                owl_sha256="",  # no pin
            ),
            behavior=OntologyBehavior(),
        )
        with pytest.raises(OWLIngestionError, match="pin"):
            FolioService(spec)._get_folio()

    @pytest.mark.slow
    def test_http_source_loads_via_hardened_ingestion(self):
        # Loading an http ontology goes through the app's hardened ingestion
        # (download + size cap + DOCTYPE reject + checksum) then reads the local
        # cache — folio-python never does its own unguarded fetch.
        svc = FolioService(CANON_SPEC)
        folio = svc._get_folio()
        assert len(folio.classes) > 14000
        assert len(svc.get_all_labels()) > 10000


class TestConceptRecord:
    def test_shape(self):
        rec = ConceptRecord(iri="x", label="L", definition="d", examples=["e"])
        assert (rec.iri, rec.label, rec.definition, rec.examples) == ("x", "L", "d", ["e"])
