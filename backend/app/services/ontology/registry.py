"""Ontology-keyed registry of ontology services.

Replaces the single ``FolioService`` process-global with a registry keyed by
ontology id. FOLIO is built eagerly on first access (the common case); other
ontologies are built lazily on first use behind a per-key lock so concurrent
first-requests can't build the same ontology twice or clobber each other.

The registry currently owns the ``FolioService`` (ontology read service). The
embedding index, OWL updater, and branch/palette hardening move under a per-
ontology aggregate in a later phase — this phase establishes the keyed boundary
without changing FOLIO behavior.
"""

from __future__ import annotations

import logging
import threading

from app.services.ontology.spec import BUILTIN_SPECS, OntologySpec

logger = logging.getLogger(__name__)


class UnknownOntologyError(KeyError):
    """Raised when an ontology id is not enabled/known."""


class OntologyRegistry:
    def __init__(self, specs: dict[str, OntologySpec], default_id: str = "folio") -> None:
        if default_id not in specs:
            # Fall back to the first enabled spec so the registry is always usable.
            default_id = next(iter(specs)) if specs else "folio"
        self._specs = dict(specs)
        self._default_id = default_id
        self._services: dict[str, object] = {}
        self._global_lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}

    @classmethod
    def from_settings(cls) -> OntologyRegistry:
        from app.config import settings

        enabled = list(settings.enabled_ontologies) or ["folio"]
        specs = {oid: BUILTIN_SPECS[oid] for oid in enabled if oid in BUILTIN_SPECS}
        unknown = [oid for oid in enabled if oid not in BUILTIN_SPECS]
        if unknown:
            logger.warning("Ignoring unknown ontologies in enabled_ontologies: %s", unknown)
        if not specs:
            specs = {"folio": BUILTIN_SPECS["folio"]}
        return cls(specs, default_id=settings.default_ontology)

    @property
    def default_id(self) -> str:
        return self._default_id

    def enabled_ids(self) -> list[str]:
        return list(self._specs.keys())

    def has(self, ontology_id: str) -> bool:
        return ontology_id in self._specs

    def get_spec(self, ontology_id: str) -> OntologySpec:
        try:
            return self._specs[ontology_id]
        except KeyError as exc:
            raise UnknownOntologyError(ontology_id) from exc

    def _lock_for(self, ontology_id: str) -> threading.Lock:
        with self._global_lock:
            return self._key_locks.setdefault(ontology_id, threading.Lock())

    def get_service(self, ontology_id: str | None = None):
        """Return the (lazily built, cached) ontology read service for an id.

        Per-key double-checked locking: the fast path is a lock-free dict read; the
        build runs once under a per-ontology lock.
        """
        oid = ontology_id or self._default_id
        svc = self._services.get(oid)  # fast path, lock-free
        if svc is not None:
            return svc
        spec = self.get_spec(oid)  # validates id before locking
        with self._lock_for(oid):
            svc = self._services.get(oid)  # re-check under lock
            if svc is None:
                from app.services.folio.folio_service import FolioService

                svc = FolioService(spec)
                self._services[oid] = svc
                logger.info("Built ontology service '%s' (%s)", oid, spec.display_name)
            return svc


_registry: OntologyRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> OntologyRegistry:
    """Process-global ontology registry, built once from settings."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = OntologyRegistry.from_settings()
    return _registry


def reset_registry() -> None:
    """Test hook: drop the process-global registry so it rebuilds from settings."""
    global _registry
    with _registry_lock:
        _registry = None
