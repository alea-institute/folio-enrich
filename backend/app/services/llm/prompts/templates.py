from __future__ import annotations

import logging

from app.services.folio.branch_config import get_llm_branch_names

logger = logging.getLogger(__name__)

FOLIO_BRANCHES: list[str] = get_llm_branch_names()

BRANCH_EXAMPLES: dict[str, str] = {
    "Actor / Player": (
        "e.g., plaintiffs, defendants, judges, counterparties, Agent, Assignor, "
        "Bail Bondsman, Bank, Common Carrier, Court Reporter, Debtor, Deponent, "
        "Employer, Expert, Franchisor, Garnishee, Guardian Ad Litem, Insurer, "
        "Landlord, Law Enforcement, Licensee, Liquidator"
    ),
    "Asset Type": "e.g., real property, intellectual property, securities, chattel",
    "Communication Modality": "e.g., email, telephone, in-person, video conference, written notice",
    "Currency": "e.g., USD, EUR, GBP, JPY, cryptocurrency",
    "Data Format": "e.g., PDF, DOCX, XML, JSON, EDI",
    "Document / Artifact": "e.g., contract, brief, memorandum, deposition transcript, exhibit",
    "Document Metadata": "e.g., author, recipient, editor, filed date, amendment",
    "Engagement Terms": "e.g., fee arrangement, retainer, billing rate, scope of work, hourly rate",
    "Event": "e.g., filing, hearing, trial, deposition, mediation, closing",
    "Financial Concepts and Metrics": "e.g., revenue, liability, damages amount, settlement value, interest rate",
    "Forums and Venues": "e.g., district court, arbitration panel, appellate court, tribunal",
    "Governmental Body": "e.g., SEC, EPA, FTC, Congress, state legislature",
    "Industry": "e.g., healthcare, finance, technology, energy, real estate",
    "Language": "e.g., English, Spanish, French, Mandarin",
    "Legal Authorities": "e.g., statutes, regulations, case law, constitutional provisions, treaties",
    "Legal Entity": "e.g., corporation, LLC, partnership, trust, nonprofit",
    "Legal Use Cases": "e.g., compliance review, due diligence, litigation hold, contract negotiation",
    "Location": "e.g., New York, Delaware, London, jurisdiction-specific places",
    "Matter Narrative": "e.g., case summary, matter description, procedural history",
    "Matter Narrative Format": "e.g., chronological, thematic, issue-based narrative structure",
    "Objectives": "e.g., breach of contract, damages, injunctive relief, specific performance",
    "Service": "e.g., legal research, document review, e-discovery, mediation services",
    "Status": "e.g., pending, active, closed, stayed, dismissed, settled",
    "System Identifiers": "e.g., docket number, case ID, matter number, PACER ID",
}

BRANCH_LIST = "\n".join(
    f"- {b} ({BRANCH_EXAMPLES[b]})" if b in BRANCH_EXAMPLES else f"- {b}"
    for b in FOLIO_BRANCHES
)


# Neutral, ontology-agnostic scaffold used when a non-FOLIO ontology exposes no
# derivable top-level branches (or its service fails to load). It deliberately
# names NO branches — a prompt must never be handed another ontology's taxonomy,
# so we fall back to generic "classify into this ontology's own top categories"
# guidance rather than FOLIO's legal BRANCH_LIST.
_NEUTRAL_BRANCH_SCAFFOLD: str = (
    "This ontology's top-level categories are not enumerated here. "
    "Classify each concept into the single most appropriate top-level category "
    "of this ontology, judging by the concept's meaning."
)


def build_branch_detail(
    max_concepts_per_branch: int = 8,
    max_total_chars: int = 8000,
    ontology_id: str = "folio",
) -> str:
    """Build enriched branch descriptions for an ontology's concept/branch prompts.

    Branch categories are ontology-specific and must not leak across ontologies:

    * **FOLIO** (the registry default) uses its own legal taxonomy verbatim —
      ``FOLIO_BRANCHES`` / ``BRANCH_LIST`` / ``BRANCH_EXAMPLES`` enriched with real
      concept definitions and examples. This path is byte-identical to the original.
    * **Any other ontology** (e.g. the Catholic Semantic Canon) derives its OWN
      top-level branches from its OWL (roots under ``owl:Thing`` + a few notable
      children), so a Canon prompt presents Event / Actor / Document — never FOLIO's
      legal branches.
    * **Non-FOLIO ontologies with no derivable branches** (or a failed/absent
      service) get a neutral, taxonomy-free scaffold — never FOLIO's ``BRANCH_LIST``.

    Derivation is lazy and failure-tolerant: any error yields the neutral scaffold
    rather than crashing a prompt build.
    """
    ontology_id = ontology_id or "folio"
    if ontology_id == "folio":
        return _build_folio_branch_detail(max_concepts_per_branch, max_total_chars)
    return _build_nonfolio_branch_detail(ontology_id, max_concepts_per_branch, max_total_chars)


def _build_folio_branch_detail(
    max_concepts_per_branch: int = 8,
    max_total_chars: int = 8000,
) -> str:
    """FOLIO branch detail — byte-identical to the original build_branch_detail.

    Uses FOLIO's legal taxonomy (FOLIO_BRANCHES / BRANCH_EXAMPLES) enriched with
    real concept definitions/examples, falling back to BRANCH_LIST if the FOLIO
    service is unavailable.
    """
    try:
        from app.services.folio.folio_service import FolioService
        from app.services.folio.branch_config import EXCLUDED_BRANCHES
        folio = FolioService.get_instance("folio")
        folio_obj = folio._get_folio()
        branches_dict = folio_obj.get_folio_branches(max_depth=16)
    except Exception:
        logger.debug("FOLIO service unavailable for branch detail; using hardcoded examples")
        return BRANCH_LIST

    from app.services.folio.branch_config import get_branch_display_name

    lines: list[str] = []
    total_chars = 0

    for branch_name in FOLIO_BRANCHES:
        # Find this branch's concepts in the folio branches dict
        branch_concepts = []
        for ft_key, classes in branches_dict.items():
            key = ft_key.name if hasattr(ft_key, "name") else str(ft_key).split(".")[-1]
            display = get_branch_display_name(key)
            if display == branch_name:
                branch_concepts = classes
                break

        # Select concepts that have definitions, up to max_concepts_per_branch
        concept_entries: list[str] = []
        for cls in branch_concepts:
            if len(concept_entries) >= max_concepts_per_branch:
                break
            defn = getattr(cls, "definition", "") or ""
            if not defn:
                continue
            label = getattr(cls, "preferred_label", None) or getattr(cls, "label", "") or ""
            if not label:
                continue
            entry = f"  * {label} — {defn[:120]}"
            # Add examples if available
            examples = getattr(cls, "examples", []) or []
            if examples:
                entry += f" (e.g., {', '.join(examples[:3])})"
            # Add alt labels if available
            alt_labels = getattr(cls, "alternative_labels", []) or []
            if alt_labels:
                entry += f"\n    Also known as: {', '.join(alt_labels[:4])}"
            concept_entries.append(entry)

        if concept_entries:
            branch_line = f"- {branch_name}:\n" + "\n".join(concept_entries)
        elif branch_name in BRANCH_EXAMPLES:
            branch_line = f"- {branch_name} ({BRANCH_EXAMPLES[branch_name]})"
        else:
            branch_line = f"- {branch_name}"

        if total_chars + len(branch_line) > max_total_chars:
            # Fall back to compact format for remaining branches
            if branch_name in BRANCH_EXAMPLES:
                branch_line = f"- {branch_name} ({BRANCH_EXAMPLES[branch_name]})"
            else:
                branch_line = f"- {branch_name}"

        lines.append(branch_line)
        total_chars += len(branch_line)

    return "\n".join(lines)


def _branch_label_excluded(label: str, spec) -> bool:
    """Apply an ontology's editorial exclusion rules to a candidate branch label.

    Mirrors FolioService concept exclusion: matched on the UPPERCASED label. Lets
    Canon's ``ZZZ``-prefixed / ``DUPE`` editorial roots drop out of the branch list.
    """
    upper = (label or "").upper()
    behavior = getattr(spec, "behavior", None)
    if behavior is None:
        return False
    if any(upper.startswith(p.upper()) for p in behavior.concept_exclude_prefixes):
        return True
    if any(s.upper() in upper for s in behavior.concept_exclude_substrings):
        return True
    return False


def _derive_branch_detail(
    folio_obj,
    spec,
    init_branch_roots,
    max_children: int = 8,
    max_total_chars: int = 8000,
) -> str | None:
    """Derive an ontology-native branch list from its OWL top-level roots.

    Reuses ``_init_branch_roots`` (concept_detail.py) to find roots under
    ``owl:Thing``. That helper always injects FOLIO's own type IRIs; those are NOT
    classes in a non-FOLIO ontology, so ``folio_obj[iri]`` resolves to ``None`` and
    they are filtered out — only THIS ontology's real roots survive. Each surviving
    root is presented with its definition and a few notable child labels as examples.

    Returns ``None`` when the ontology exposes no derivable roots (caller then uses
    the neutral scaffold).
    """
    roots = init_branch_roots(folio_obj)  # {full_iri: display_name}

    real_roots: list[tuple[object, str]] = []
    for iri, name in roots.items():
        cls = folio_obj[iri]
        if cls is None:
            # Phantom root (e.g. an injected FOLIO type IRI not present here).
            continue
        display = getattr(cls, "label", "") or name or ""
        if not display or _branch_label_excluded(display, spec):
            continue
        real_roots.append((cls, display))

    if not real_roots:
        return None

    real_roots.sort(key=lambda t: (t[1] or "").casefold())

    lines: list[str] = []
    total_chars = 0
    for cls, name in real_roots:
        defn = (getattr(cls, "definition", "") or "").strip()
        header = f"- {name}"
        if defn:
            header += f": {defn[:160]}"

        child_labels: list[str] = []
        for child_iri in (getattr(cls, "parent_class_of", None) or []):
            child = folio_obj[child_iri]
            if child is None:
                continue
            clabel = getattr(child, "label", "") or ""
            if not clabel or _branch_label_excluded(clabel, spec):
                continue
            child_labels.append(clabel)
            if len(child_labels) >= max_children:
                break

        block = header
        if child_labels:
            block += f"\n  Examples: {', '.join(child_labels)}"

        if total_chars + len(block) > max_total_chars:
            break
        lines.append(block)
        total_chars += len(block)

    return "\n".join(lines) if lines else None


def _build_nonfolio_branch_detail(
    ontology_id: str,
    max_concepts_per_branch: int = 8,
    max_total_chars: int = 8000,
) -> str:
    """Derive a non-FOLIO ontology's own branches; neutral scaffold on any failure."""
    try:
        from app.services.folio.concept_detail import _init_branch_roots
        from app.services.folio.folio_service import FolioService

        service = FolioService.get_instance(ontology_id)
        folio_obj = service._get_folio()
        detail = _derive_branch_detail(
            folio_obj,
            service.spec,
            _init_branch_roots,
            max_children=max_concepts_per_branch,
            max_total_chars=max_total_chars,
        )
    except Exception:
        logger.debug(
            "Branch derivation failed for ontology '%s'; using neutral scaffold",
            ontology_id,
            exc_info=True,
        )
        return _NEUTRAL_BRANCH_SCAFFOLD
    return detail or _NEUTRAL_BRANCH_SCAFFOLD


def get_branch_detail(ontology_id: str = "folio") -> str:
    """Get branch detail for an ontology, building lazily and caching per ontology."""
    ontology_id = ontology_id or "folio"
    cached = _BRANCH_DETAIL_CACHE.get(ontology_id)
    if cached is None:
        cached = build_branch_detail(ontology_id=ontology_id)
        _BRANCH_DETAIL_CACHE[ontology_id] = cached
    return cached


_BRANCH_DETAIL_CACHE: dict[str, str] = {}
