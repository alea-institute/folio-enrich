"""Candidate reconciliation — thin adapter over the pinned ``folio_matching.Reconciler``.

Migration SCHEDULE.md row 2: the reconciler logic was *lifted into* folio-matching from this
very module, so folio-enrich now consumes it back instead of maintaining a fork. This adapter
keeps folio-enrich's public surface intact — ``Reconciler(embedding_service=...)`` with
``reconcile`` / ``reconcile_with_embedding_triage`` returning ``ReconciliationResult`` objects
whose ``.concept`` is a folio-enrich :class:`~app.models.annotation.ConceptMatch` — while the
merge policy (diminishing-boost agreement, 0.60 ruler-only floor, embedding-triage conflict
resolution) lives in the library.

Branch preservation (seam bug watch): folio-enrich's ``ConceptMatch`` carries a ``branches``
list and rich FOLIO metadata; the library's dataclass carries a single ``branch``. The adapter
maps each enrich concept to a library concept **by identity**, runs the library merge, then
copies the library's recomputed ``confidence`` / ``source`` back onto the *original* enrich
object — so ``branches`` and every other field survive the round trip untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from folio_matching import ConceptMatch as _LibConceptMatch
from folio_matching import Reconciler as _LibReconciler
from folio_matching.reconciler import (  # re-exported for back-compat with existing importers
    EMBEDDING_AUTO_RESOLVE_THRESHOLD,
    RULER_ONLY_MIN_CONFIDENCE,
    _definition_overlap_score,
    _diminishing_boost,
)

from app.models.annotation import ConceptMatch

logger = logging.getLogger(__name__)

__all__ = [
    "EMBEDDING_AUTO_RESOLVE_THRESHOLD",
    "RULER_ONLY_MIN_CONFIDENCE",
    "ReconciliationResult",
    "Reconciler",
    "_definition_overlap_score",
    "_diminishing_boost",
]


@dataclass
class ReconciliationResult:
    concept: ConceptMatch
    category: str  # "both_agree", "ruler_only", "llm_only", "conflict_resolved"


def _to_lib(concept: ConceptMatch) -> _LibConceptMatch:
    """Project an enrich ConceptMatch onto the library's dataclass (the fields the merge reads)."""
    return _LibConceptMatch(
        concept_text=concept.concept_text,
        folio_iri=concept.folio_iri or "",
        folio_label=concept.folio_label or "",
        folio_definition=concept.folio_definition or "",
        confidence=concept.confidence,
        branch=(concept.branches[0] if concept.branches else ""),
        source=concept.source,
    )


class Reconciler:
    """Merge EntityRuler and LLM concept identification results (delegates to folio-matching)."""

    def __init__(self, embedding_service=None) -> None:
        self._embedding_service = embedding_service

    def _lib_reconciler(self) -> _LibReconciler:
        emb = self._embedding_service
        sim = getattr(emb, "similarity_batch", None) if emb is not None else None
        index_size = int(getattr(emb, "index_size", 0) or 0) if emb is not None else 0
        return _LibReconciler(
            similarity_batch=sim if callable(sim) else None,
            index_size=index_size,
        )

    def reconcile(
        self,
        ruler_concepts: list[ConceptMatch],
        llm_concepts: list[ConceptMatch],
    ) -> list[ReconciliationResult]:
        return self._run(ruler_concepts, llm_concepts, triage=False)

    def reconcile_with_embedding_triage(
        self,
        ruler_concepts: list[ConceptMatch],
        llm_concepts: list[ConceptMatch],
    ) -> list[ReconciliationResult]:
        return self._run(ruler_concepts, llm_concepts, triage=True)

    def _run(
        self,
        ruler_concepts: list[ConceptMatch],
        llm_concepts: list[ConceptMatch],
        *,
        triage: bool,
    ) -> list[ReconciliationResult]:
        # Build library concepts, keeping an identity map back to the enrich originals so all
        # enrich-only fields (branches, match_type, folio_* metadata) survive the merge.
        back: dict[int, ConceptMatch] = {}
        lib_ruler: list[_LibConceptMatch] = []
        for c in ruler_concepts:
            lc = _to_lib(c)
            back[id(lc)] = c
            lib_ruler.append(lc)
        lib_llm: list[_LibConceptMatch] = []
        for c in llm_concepts:
            lc = _to_lib(c)
            back[id(lc)] = c
            lib_llm.append(lc)

        reconciler = self._lib_reconciler()
        if triage:
            lib_results = reconciler.reconcile_with_embedding_triage(lib_ruler, lib_llm)
        else:
            lib_results = reconciler.reconcile(lib_ruler, lib_llm)

        results: list[ReconciliationResult] = []
        for lr in lib_results:
            original = back.get(id(lr.concept))
            if original is None:  # pragma: no cover - defensive; every lib obj is mapped
                logger.warning("reconciler: unmapped library concept %r", lr.concept)
                continue
            # Copy the library's recomputed merge outputs back onto the enrich object.
            original.confidence = lr.concept.confidence
            original.source = lr.concept.source
            results.append(ReconciliationResult(concept=original, category=lr.category))
        return results
