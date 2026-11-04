"""Lazy overlap of the resident FOLIO and Catholic Semantic Canon graphs.

Local identifiers join only classes under each ontology's base IRI. Labels and
definitions are compared case-sensitively after collapsing whitespace; returned
labels retain their original text.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Literal

from app.services.ontology.registry import OntologyRegistry, get_registry


@dataclass(frozen=True)
class OverlapRecord:
    iri_hash: str
    region: Literal["shared", "canon_only", "folio_only"]
    folio_iri: str | None = None
    canon_iri: str | None = None
    folio_label: str | None = None
    canon_label: str | None = None
    label_drift: bool = False
    definition_drift: bool = False

    @property
    def drifted(self) -> bool:
        return self.label_drift or self.definition_drift


def _concepts(service):
    """Reuse service exclusions, also dropping descendants of editorial roots."""
    graph = service._get_folio()
    classes = {c.iri: c for c in graph.classes}
    children: dict[str, list[str]] = {}
    excluded = set()
    for iri, concept in classes.items():
        if service._is_excluded_concept(service._to_folio_concept(concept)):
            excluded.add(iri)
        for parent in getattr(concept, "sub_class_of", []) or []:
            children.setdefault(parent, []).append(iri)
    pending = list(excluded)
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in excluded:
                excluded.add(child)
                pending.append(child)
    return {iri.rsplit("/", 1)[-1]: c for iri, c in classes.items() if iri not in excluded}


def _normalized(text: str | None) -> str:
    return " ".join((text or "").split())


class OverlapIndex:
    def __init__(self, registry: OntologyRegistry):
        folio_service = registry.get_service("folio")
        canon_service = registry.get_service("canon")
        folio = _concepts(folio_service)
        canon = _concepts(canon_service)
        self.entries: dict[str, OverlapRecord] = {}
        for key in folio.keys() | canon.keys():
            f, c = folio.get(key), canon.get(key)
            shared_in_fork = (f is not None and c is not None
                      and f.iri.startswith(folio_service.spec.base_iri)
                      and c.iri.startswith(canon_service.spec.base_iri))
            region = "shared" if shared_in_fork else "canon_only" if c is not None else "folio_only"
            self.entries[key] = OverlapRecord(
                iri_hash=key, region=region,
                folio_iri=f.iri if f is not None else None,
                canon_iri=c.iri if c is not None else None,
                folio_label=(f.label or "") if f is not None else None,
                canon_label=(c.label or "") if c is not None else None,
                label_drift=bool(shared_in_fork and _normalized(f.label) != _normalized(c.label)),
                definition_drift=bool(shared_in_fork and _normalized(f.definition) != _normalized(c.definition)),
            )

    def lookup(self, iri_hash: str) -> OverlapRecord | None:
        return self.entries.get(iri_hash)

    def summary(self) -> dict[str, int]:
        records = self.entries.values()
        return {
            "shared": sum(r.region == "shared" for r in records),
            "canon_only": sum(r.region == "canon_only" for r in records),
            "folio_only": sum(r.region == "folio_only" for r in records),
            "label_drifted": sum(r.label_drift for r in records),
            "definition_drifted": sum(r.definition_drift for r in records),
        }


_index: OverlapIndex | None = None
_index_registry: OntologyRegistry | None = None
_lock = Lock()


def reset_overlap_index() -> None:
    """Invalidate alongside registry reset/replacement without loading graphs."""
    global _index, _index_registry
    with _lock:
        _index = None
        _index_registry = None


def get_overlap_index() -> OverlapIndex:
    """Build once per installed registry, only when overlap is requested."""
    global _index, _index_registry
    registry = get_registry()
    if _index is not None and _index_registry is registry:
        return _index
    with _lock:
        if _index is None or _index_registry is not registry:
            _index = OverlapIndex(registry)
            _index_registry = registry
        return _index
