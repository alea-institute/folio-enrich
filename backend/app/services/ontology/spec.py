"""Per-ontology configuration: coordinates, normalization/exclusion behavior.

Each ontology is described by an :class:`OntologySpec`. FOLIO's spec carries the
exact values that used to live as module-level constants in ``folio_service.py``
and ``branch_config.py`` — so routing FOLIO through the registry is a pure
refactor with no behavior change. The Catholic Semantic Canon is defined here too
(validated loadable via the Phase 0 spike) but is only instantiated when listed in
``settings.enabled_ontologies``.

Fields are added as their consumers land, not speculatively — the frontend brand
label, per-ontology OWL filename/repo coords, etc. arrive with the phases that use
them.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.folio.branch_config import EXCLUDED_BRANCHES


@dataclass(frozen=True)
class OntologyCoords:
    """Where an ontology's OWL comes from.

    ``source_type`` mirrors folio-python: ``"github"`` loads FOLIO from its default
    repo at ``repo_branch``; ``"http"`` fetches ``owl_url`` directly. Phase 0
    confirmed the Canon must load via the ``http`` path.
    """

    source_type: str  # "github" | "http"
    repo_branch: str = "main"
    owl_url: str = ""


@dataclass(frozen=True)
class OntologyBehavior:
    """Per-ontology normalization/exclusion rules.

    FOLIO's rules are legal-domain-specific (prefix list, terms-of-art lemma
    denylist, editorial ``DUPE``/``ZZZ:`` markers, excluded branches) and must NOT
    bleed into another ontology — that is why they live here per-ontology rather
    than as shared module constants. Concept exclusion is checked case-insensitively
    (label uppercased, matching the original logic); property exclusion is checked
    against the raw label (also matching the original). See ``FolioService``.
    """

    prefix_strip: tuple[str, ...] = ()
    lemma_denylist: frozenset[str] = frozenset()
    concept_exclude_substrings: tuple[str, ...] = ()  # matched on UPPERCASED label
    concept_exclude_prefixes: tuple[str, ...] = ()    # matched on UPPERCASED label
    property_exclude_substrings: tuple[str, ...] = ()  # matched on RAW label
    property_exclude_prefixes: tuple[str, ...] = ()    # matched on RAW label
    excluded_branches: frozenset[str] = frozenset()    # branch display names to skip
    # IRI roots this ontology may emit. FOLIO has one; the Canon has two
    # (catholicos.catholic + webprotege.stanford.edu — Phase 0 finding).
    iri_roots: tuple[str, ...] = ()


@dataclass(frozen=True)
class OntologySpec:
    id: str
    display_name: str
    base_iri: str
    coords: OntologyCoords
    behavior: OntologyBehavior


# Legal pluralia-tantum / terms of art whose singular has a *different* meaning.
# Verbatim from the former FolioService._LEMMA_DENYLIST — moved here so it is
# per-ontology (the Canon inherits none of these). Do not edit without bumping
# LEMMA_VERSION in folio_service.py.
_FOLIO_LEMMA_DENYLIST: frozenset[str] = frozenset({
    "damages", "damage", "costs", "cost", "proceedings", "proceeding",
    "goods", "good", "arms", "arm", "premises", "savings", "saving",
    "findings", "finding", "securities", "minutes", "minute",
    "holdings", "holding", "pleadings", "pleading", "articles", "article",
    "data", "datum", "leaves", "leave", "wills", "will", "means",
})


FOLIO_SPEC = OntologySpec(
    id="folio",
    display_name="FOLIO",
    base_iri="https://folio.openlegalstandard.org/",
    coords=OntologyCoords(source_type="github", repo_branch="main"),
    behavior=OntologyBehavior(
        prefix_strip=("folio:", "utbms:", "oasis:"),
        lemma_denylist=_FOLIO_LEMMA_DENYLIST,
        concept_exclude_substrings=("DUPE",),
        concept_exclude_prefixes=("ZZZ:",),
        property_exclude_substrings=("DEPRECATED",),
        property_exclude_prefixes=("ZZZ:",),
        excluded_branches=EXCLUDED_BRANCHES,
        iri_roots=("https://folio.openlegalstandard.org/",),
    ),
)


# Catholic Semantic Canon — validated loadable by the Phase 0 spike
# (backend/scripts/validate_canon_owl.py). DEFINED but not enabled until Phase 2;
# only instantiated when "canon" is in settings.enabled_ontologies. Loads via the
# http path (folio-python's github path is FOLIO-only). NOTE: the http load path is
# deliberately guarded off until Phase 2 lands hardened OWL ingestion.
CANON_SPEC = OntologySpec(
    id="canon",
    display_name="Catholic Semantic Canon",
    base_iri="https://ontology.catholicos.catholic/",
    coords=OntologyCoords(
        source_type="http",
        owl_url=(
            "https://raw.githubusercontent.com/CatholicOS/ontology-semantic-canon/"
            "main/sources/ontology-semantic-canon.owl"
        ),
    ),
    behavior=OntologyBehavior(
        prefix_strip=(),
        lemma_denylist=frozenset(),  # no legal terms-of-art rules
        # Canon reuses FOLIO's ZZZ/deprecated editorial convention (Phase 0 finding).
        concept_exclude_substrings=("DUPE",),
        concept_exclude_prefixes=("ZZZ",),  # roots seen: "ZZZ - Licensing", "ZZZZ - Deprecated"
        property_exclude_substrings=("DEPRECATED",),
        property_exclude_prefixes=("ZZZ",),
        excluded_branches=frozenset(),  # refined once Canon branches are derived (Phase 2)
        # Mixed IRI namespaces (Phase 0 finding).
        iri_roots=(
            "https://ontology.catholicos.catholic/",
            "http://webprotege.stanford.edu/",
        ),
    ),
)


# All ontologies the app knows how to build. Which ones are actually loaded is
# governed by settings.enabled_ontologies.
BUILTIN_SPECS: dict[str, OntologySpec] = {
    FOLIO_SPEC.id: FOLIO_SPEC,
    CANON_SPEC.id: CANON_SPEC,
}
