"""Machine-readable ontology metadata.

Lets the frontend (and API/agent clients) discover which ontologies are available
and their identity, instead of scraping the single-file UI. The frontend switcher
hydrates from here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.ontology.registry import UnknownOntologyError, get_registry

router = APIRouter(prefix="/ontologies", tags=["ontologies"])


def _spec_payload(ontology_id: str) -> dict:
    reg = get_registry()
    spec = reg.get_spec(ontology_id)
    return {
        "id": spec.id,
        "display_name": spec.display_name,
        "base_iri": spec.base_iri,
        "iri_roots": list(spec.behavior.iri_roots),
        "default": ontology_id == reg.default_id,
        "enabled": True,
    }


@router.get("")
async def list_ontologies() -> dict:
    """List enabled ontologies + which is default, plus a global embeddings flag."""
    reg = get_registry()
    return {
        "default": reg.default_id,
        "embeddings_available": not settings.embedding_disabled,
        "ontologies": [_spec_payload(oid) for oid in reg.enabled_ids()],
    }


@router.get("/{ontology_id}")
async def get_ontology(ontology_id: str) -> dict:
    """Metadata for one enabled ontology."""
    try:
        return _spec_payload(ontology_id)
    except UnknownOntologyError:
        enabled = get_registry().enabled_ids()
        raise HTTPException(
            status_code=404,
            detail=f"Unknown or disabled ontology '{ontology_id}'. Enabled: {enabled}",
        )
