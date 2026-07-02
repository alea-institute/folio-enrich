"""Multi-ontology support.

Turns the ontology from a hardcoded FOLIO global into a request-scoped, registry-
backed dimension. FOLIO is the reference implementation and default; a second
ontology (the Catholic Semantic Canon) is added as another registry entry.

See docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md.
"""

from app.services.ontology.registry import OntologyRegistry, get_registry
from app.services.ontology.spec import (
    BUILTIN_SPECS,
    CANON_SPEC,
    FOLIO_SPEC,
    OntologyBehavior,
    OntologyCoords,
    OntologySpec,
)

__all__ = [
    "BUILTIN_SPECS",
    "CANON_SPEC",
    "FOLIO_SPEC",
    "OntologyBehavior",
    "OntologyCoords",
    "OntologyRegistry",
    "OntologySpec",
    "get_registry",
]
