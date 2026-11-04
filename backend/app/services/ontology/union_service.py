"""Virtual union borrowing the registry's current resident ontology services."""
from __future__ import annotations

from copy import copy
from dataclasses import replace
from typing import TYPE_CHECKING
from weakref import ref

if TYPE_CHECKING:
    from app.services.ontology.registry import OntologyRegistry


class UnionService:
    ontology_id = 'both'

    def __init__(self, registry: OntologyRegistry):
        # Cache records may outlive eviction; service identities must be weak references.
        self._registry = registry
        self._label_cache = {}

    @property
    def spec(self):
        """Primary identity; branch decisions must use service_for_iri instead."""
        return self._registry.get_spec('folio')

    def service_for_iri(self, iri: str):
        for oid in ('folio', 'canon'):
            spec = self._registry.get_spec(oid)
            if iri.startswith((spec.base_iri, *spec.behavior.iri_roots)):
                return self._registry.get_service(oid)
        raise ValueError(f'No union ontology owns IRI {iri!r}')

    def graph_for_iri(self, iri: str):
        return self.service_for_iri(iri)._get_folio()

    def _cached_labels(self, name):
        cached = self._label_cache.get(name)
        if cached is not None:
            identities, labels = cached
            if all(identity() is self._registry._services.get(oid) and identity() is not None
                   for oid, identity in zip(('folio', 'canon'), identities)):
                return labels
        return None

    def _cache_labels(self, name, labels):
        services = [self._registry._services.get(oid) for oid in ('folio', 'canon')]
        if all(service is not None for service in services):
            self._label_cache[name] = (tuple(ref(service) for service in services), labels)
        return labels

    def _decorate(self, concept, record):
        concept = copy(concept)
        if record:
            concept.region = record.region
            concept.drifted = record.drifted
            concept.peer_iri = record.canon_iri if record.region == 'shared' else None
            concept.peer_label = record.canon_label if record.region == 'shared' else None
        return concept

    def get_concept(self, iri: str):
        from app.services.ontology.overlap import get_overlap_index

        key = iri.rsplit('/', 1)[-1]
        record = get_overlap_index().lookup(key)
        if record:
            primary = record.folio_iri if record.region != 'canon_only' else record.canon_iri
            service = self.service_for_iri(primary)
            concept = service.get_concept(primary)
        elif '://' in iri:
            concept = self.service_for_iri(iri).get_concept(iri)
        else:
            concept = None
        return self._decorate(concept, record) if concept is not None else None

    def get_all_labels_multi(self):
        cached = self._cached_labels("multi")
        if cached is not None:
            return cached
        labels = {}
        for oid in ('folio', 'canon'):
            for label, entries in self._registry.get_service(oid).get_all_labels_multi().items():
                bucket = labels.setdefault(label, [])
                for entry in entries:
                    concept = self.get_concept(entry.concept.iri)
                    if concept is not None and all(e.concept.iri != concept.iri for e in bucket):
                        bucket.append(replace(entry, concept=concept))
        return self._cache_labels("multi", labels)

    def get_all_labels(self):
        cached = self._cached_labels("single")
        if cached is not None:
            return cached
        labels = {label: entries[0] for label, entries in self.get_all_labels_multi().items() if entries}
        return self._cache_labels("single", labels)

    def search_by_label(self, label: str, top_k: int = 5):
        matches = {}
        for oid in ('folio', 'canon'):
            for concept, score in self._registry.get_service(oid).search_by_label(label, top_k):
                primary = self.get_concept(concept.iri)
                if primary is not None and (primary.iri not in matches or score > matches[primary.iri][1]):
                    matches[primary.iri] = (primary, score)
        return sorted(matches.values(), key=lambda pair: pair[1], reverse=True)[:top_k]

    def get_property(self, iri: str):
        key = iri.rsplit('/', 1)[-1]
        for oid in ('folio', 'canon'):
            service = self._registry.get_service(oid)
            prop = service.get_property(service.spec.base_iri + key)
            if prop is not None:
                return prop
        if '://' in iri:
            for oid in ('folio', 'canon'):
                prop = self._registry.get_service(oid).get_property(iri)
                if prop is not None:
                    return prop
        return None

    def get_all_property_labels(self):
        cached = self._cached_labels("property")
        if cached is not None:
            return cached
        labels = {}
        for oid in ('folio', 'canon'):
            for label, entry in self._registry.get_service(oid).get_all_property_labels().items():
                labels.setdefault(label, replace(entry, prop=self.get_property(entry.prop.iri)))
        return self._cache_labels("property", labels)
