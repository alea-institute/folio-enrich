"""Committed, model-reviewed Canon-to-FOLIO concept bridges."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.folio.folio_service import FolioService
    from app.services.ontology.overlap import OverlapIndex


_BRIDGE_FILE = Path(__file__).resolve().parents[3] / "data/bridges/canon_folio_bridges.json"


@lru_cache(maxsize=1)
def load_bridges() -> dict:
    """Read the bridge document once; callers must treat it as read-only."""
    return json.loads(_BRIDGE_FILE.read_text(encoding="utf-8"))


def validate(bridges: list[dict], overlap_index: OverlapIndex,
             services: dict[str, FolioService]) -> list[str]:
    """Report invalid endpoints or metadata against the supplied resident graphs.

    Services are keyed by ``canon`` and ``folio``. Resolve endpoint IRIs from the
    overlap index where possible (Canon includes external IRIs); use the base IRI
    when an endpoint has been removed from that filtered index.
    """
    problems = []
    for bridge in bridges:
        name = f"Bridge {bridge['canon_hash']} -> {bridge['folio_hash']}"
        for ontology in ("canon", "folio"):
            key = bridge[f"{ontology}_hash"]
            record = overlap_index.lookup(key)
            iri = getattr(record, f"{ontology}_iri", None)
            service = services[ontology]
            concept = service.get_concept(iri or service.spec.base_iri + key)
            if concept is None:
                problems.append(f"{name}: {ontology} endpoint {key} is missing")
            elif concept.deprecated:
                problems.append(f"{name}: {ontology} endpoint {key} is deprecated")
            if ontology == "canon" and (record is None or record.region != "canon_only"):
                problems.append(f"{name}: Canon endpoint {key} is no longer canon_only")
        if bridge.get("match_type") not in {"close", "related"}:
            problems.append(f"{name}: invalid match_type {bridge.get('match_type')!r}")
        if bridge.get("review_status") not in {"model", "damien"}:
            problems.append(f"{name}: invalid review_status {bridge.get('review_status')!r}")
    return problems
