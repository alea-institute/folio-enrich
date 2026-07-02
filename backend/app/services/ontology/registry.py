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
import time
from typing import TYPE_CHECKING

from app.services.ontology.spec import BUILTIN_SPECS, OntologySpec

if TYPE_CHECKING:
    from app.services.embedding.service import EmbeddingService
    from app.services.folio.folio_service import FolioService

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
        self._services: dict[str, FolioService] = {}
        self._embedding_services: dict[str, EmbeddingService] = {}
        self._global_lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        # Last-access clock (time.monotonic) per ontology, for LRU eviction of
        # resident non-default ontologies. Updated on every service/embedding hit.
        self._last_access: dict[str, float] = {}
        # ONE SentenceTransformer shared by every per-ontology EmbeddingService, so
        # enabling Canon does not load a second copy of the model.
        self._shared_provider = None

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

    def _touch(self, ontology_id: str) -> None:
        """Record an access for LRU bookkeeping (dict write is atomic under GIL)."""
        self._last_access[ontology_id] = time.monotonic()

    def _evict_if_needed(self) -> None:
        """Evict the LRU NON-default ontology while resident non-defaults exceed the
        ceiling. The default is never evicted. Takes only ``_global_lock`` (never a
        per-key lock), so it cannot deadlock against an in-flight build.
        """
        from app.config import settings

        ceiling = max(0, settings.max_resident_ontologies)
        with self._global_lock:
            resident = set(self._services) | set(self._embedding_services)
            non_default = [o for o in resident if o != self._default_id]
            while len(non_default) > ceiling:
                lru = min(non_default, key=lambda o: self._last_access.get(o, 0.0))
                self._services.pop(lru, None)
                self._embedding_services.pop(lru, None)
                self._last_access.pop(lru, None)
                non_default.remove(lru)
                logger.info(
                    "Evicted resident ontology '%s' (LRU; %d non-default > ceiling %d)",
                    lru, len(non_default) + 1, ceiling,
                )

    def get_service(self, ontology_id: str | None = None) -> "FolioService":
        """Return the (lazily built, cached) ontology read service for an id.

        Per-key double-checked locking: the fast path is a lock-free dict read; the
        build runs once under a per-ontology lock.
        """
        oid = ontology_id or self._default_id
        svc = self._services.get(oid)  # fast path, lock-free
        if svc is not None:
            self._touch(oid)
            return svc
        spec = self.get_spec(oid)  # validates id before locking
        built = False
        with self._lock_for(oid):
            svc = self._services.get(oid)  # re-check under lock
            if svc is None:
                from app.services.folio.folio_service import FolioService

                svc = FolioService(spec)
                self._services[oid] = svc
                built = True
                logger.info("Built ontology service '%s' (%s)", oid, spec.display_name)
        self._touch(oid)
        if built:
            self._evict_if_needed()  # bound resident non-defaults (never evicts default)
        return svc

    def _get_shared_provider(self):
        """Lazily create the ONE embedding provider shared across all ontologies."""
        if self._shared_provider is None:
            with self._global_lock:
                if self._shared_provider is None:
                    from app.services.embedding.service import _create_embedding_provider

                    self._shared_provider = _create_embedding_provider()
        return self._shared_provider

    def get_embedding_service(self, ontology_id: str | None = None) -> "EmbeddingService":
        """Return the (lazily built, cached) per-ontology embedding service.

        Each ontology gets its own label-vector index tagged with its id, so a live
        job only ever scores its candidates against its own ontology's vectors. All
        of them share one SentenceTransformer (``_get_shared_provider``). FOLIO is
        built eagerly at startup; other ontologies build lazily on first request.

        Per-key double-checked locking mirrors :meth:`get_service`; the underlying
        ``FolioService`` is fetched BEFORE taking the (non-reentrant) per-key lock so
        the two builds never nest on the same lock.
        """
        oid = ontology_id or self._default_id
        es = self._embedding_services.get(oid)  # fast path, lock-free
        if es is not None:
            self._touch(oid)
            return es
        spec = self.get_spec(oid)  # validates id before locking
        svc = self.get_service(oid)  # build/fetch FolioService (releases its own lock)

        # Cache key: a pinned OWL sha (http ontologies like Canon) → stable disk
        # cache across restarts; FOLIO (default, no pin) → runtime content hash,
        # exactly as before; any other unpinned ontology → build fresh (no cache).
        if spec.coords.owl_sha256:
            owl_hash = spec.coords.owl_sha256[:16]
        elif oid == self._default_id:
            from app.services.folio.owl_cache import get_owl_content_hash

            owl_hash = get_owl_content_hash()
        else:
            owl_hash = ""

        built = False
        with self._lock_for(oid):
            es = self._embedding_services.get(oid)  # re-check under lock
            if es is None:
                from app.services.embedding.service import EmbeddingService

                es = EmbeddingService(provider=self._get_shared_provider())
                try:
                    es.index_folio_labels(svc, owl_hash=owl_hash, ontology_id=oid)
                except Exception:
                    # Graceful degradation: never raise into a request. Consumers
                    # gate on index_size == 0 and skip embeddings for this job.
                    logger.warning(
                        "Embedding index build failed for ontology '%s' — semantic "
                        "features disabled for it", oid, exc_info=True,
                    )
                self._embedding_services[oid] = es
                built = True
                logger.info(
                    "Built embedding service '%s' (%d vectors)", oid, es.index_size,
                )
        self._touch(oid)
        if built:
            self._evict_if_needed()  # bound resident non-defaults (never evicts default)
        return es


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


def get_embedding_service(ontology_id: str | None = None) -> "EmbeddingService":
    """Per-ontology embedding service from the process-global registry."""
    return get_registry().get_embedding_service(ontology_id)


def reset_registry() -> None:
    """Test hook: drop the process-global registry so it rebuilds from settings."""
    global _registry
    with _registry_lock:
        _registry = None


def set_registry(registry: OntologyRegistry | None) -> None:
    """Injection hook: install a pre-built registry as the process-global one.

    Lets tests (and the app lifespan) construct a registry explicitly and make it
    the source of truth that every accessor (``get_registry``, ``FolioService.
    get_instance``, ``get_embedding_service``) returns. Pass ``None`` to clear.
    """
    global _registry
    with _registry_lock:
        _registry = registry
