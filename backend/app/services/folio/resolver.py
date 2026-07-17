from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.folio.branch_config import EXCLUDED_BRANCHES
from app.services.folio.folio_service import FOLIOConcept, FolioService

logger = logging.getLogger(__name__)


@dataclass
class ResolvedConcept:
    concept_text: str
    folio_concept: FOLIOConcept
    confidence: float
    branches: list[str]
    source: str
    branch_color: str = ""
    hierarchy_path: list[str] = field(default_factory=list)
    iri_hash: str = ""


class ConceptResolver:
    """Resolve-Once-Use-Many: caches resolution of concept text to FOLIO IRIs."""

    def __init__(self, folio_service: FolioService | None = None) -> None:
        self.folio = folio_service or FolioService.get_instance()
        self._cache: dict[tuple[str, str], ResolvedConcept | None] = {}

    def _canonicalize_branches(self, branches: list[str]) -> list[str]:
        """Snap LLM-guessed fallback branch labels to canonical root labels.

        Only used for the fallback path (concept resolved with NO ontology-derived
        branch), where ``branches`` carries the LLM's free-text guess. Gated to
        non-default ontologies inside ``canonicalize_branch_label`` (FOLIO no-op);
        multiplicity/order preserved — only the label STRINGS are normalized.
        """
        if not branches:
            return branches
        try:
            spec = getattr(self.folio, "spec", None)
            from app.services.folio.concept_detail import (
                _implicit_root_discovery_enabled,
                canonicalize_branch_label,
            )
            if spec is None or not _implicit_root_discovery_enabled(spec):
                return branches
            folio_raw = self.folio._get_folio()
            return [canonicalize_branch_label(b, folio_raw, spec) for b in branches]
        except Exception:  # pragma: no cover - defensive; never fail resolution
            return branches

    def resolve(
        self,
        concept_text: str,
        branches: list[str] | None = None,
        confidence: float = 0.0,
        source: str = "llm",
        folio_iri: str | None = None,
    ) -> ResolvedConcept | None:
        """Resolve a concept to a FOLIO concept.

        If folio_iri is provided, look up the concept directly by IRI (fast path).
        Otherwise, search by label text (slow path with potential mismatches).
        """
        branch = branches[0] if branches else ""
        cache_key = (concept_text.lower(), branch.lower())
        if cache_key in self._cache:
            return self._cache[cache_key]

        best_concept = None
        score = 0.0

        # Fast path: direct IRI lookup (used by EntityRuler which already knows the IRI)
        if folio_iri:
            direct = self.folio.get_concept(folio_iri)
            if direct:
                best_concept = direct
                score = confidence  # Trust the confidence from the caller
            else:
                logger.warning("IRI lookup failed for %s, falling back to search", folio_iri)

        # Slow path: multi-strategy search
        if best_concept is None:
            best_concept, score = self._multi_strategy_resolve(concept_text, branch)
            if best_concept is None:
                self._cache[cache_key] = None
                return None

        # Extract enriched metadata
        iri_hash = best_concept.iri.rsplit("/", 1)[-1] if best_concept.iri else ""
        branch_color = ""
        hierarchy_path: list[str] = []
        try:
            from app.services.folio.branch_config import get_branch_color
            branch_color = get_branch_color(best_concept.branch) if best_concept.branch else ""
        except Exception:
            pass

        resolved_branches = (
            [best_concept.branch]
            if best_concept.branch
            else self._canonicalize_branches(branches or [])
        )

        # Defense-in-depth: reject concepts from excluded branches
        if any(b in EXCLUDED_BRANCHES for b in resolved_branches):
            self._cache[cache_key] = None
            return None

        # Blend search score with caller confidence when both are available.
        # IRI fast-path: score == confidence (set above), so this is a no-op.
        # Search path: score comes from multi_strategy_search, confidence from
        # the reconciler — blend to preserve upstream calibration work.
        if score > 0 and confidence > 0:
            final_confidence = score * 0.6 + confidence * 0.4
        elif score > 0:
            final_confidence = score
        else:
            final_confidence = confidence
        resolved = ResolvedConcept(
            concept_text=concept_text,
            folio_concept=best_concept,
            confidence=final_confidence,
            branches=resolved_branches,
            source=source,
            branch_color=branch_color,
            hierarchy_path=hierarchy_path,
            iri_hash=iri_hash,
        )
        self._cache[cache_key] = resolved
        return resolved

    def resolve_multi(
        self,
        concept_text: str,
        branches: list[str] | None = None,
        confidence: float = 0.0,
        source: str = "llm",
        max_candidates: int = 5,
    ) -> list[ResolvedConcept]:
        """Resolve a concept to multiple FOLIO candidates (up to max_candidates)."""
        branch = branches[0] if branches else ""
        all_results = self._multi_strategy_resolve_all(concept_text, branch, max_candidates)
        resolved_list: list[ResolvedConcept] = []
        for fc, score in all_results:
            if any(b in EXCLUDED_BRANCHES for b in ([fc.branch] if fc.branch else [])):
                continue
            iri_hash = fc.iri.rsplit("/", 1)[-1] if fc.iri else ""
            branch_color = ""
            try:
                from app.services.folio.branch_config import get_branch_color
                branch_color = get_branch_color(fc.branch) if fc.branch else ""
            except Exception:
                pass
            resolved_branches = (
                [fc.branch] if fc.branch else self._canonicalize_branches(branches or [])
            )
            resolved_list.append(ResolvedConcept(
                concept_text=concept_text,
                folio_concept=fc,
                confidence=score,
                branches=resolved_branches,
                source=source,
                branch_color=branch_color,
                hierarchy_path=[],
                iri_hash=iri_hash,
            ))
        return resolved_list[:max_candidates]

    def _cached_multi_search(self, folio_raw, concept_text, branch, top_n, get_branch_fn):
        """multi_strategy_search with a cross-request result cache on the FolioService
        singleton. Same query + ontology → identical results, so this only removes
        redundant search work (no precision/recall change). Returns a shallow copy so
        callers that sort the list in place can't corrupt the cache."""
        from app.services.folio.search import multi_strategy_search

        cache = getattr(self.folio, "_search_cache", None)
        key = (concept_text.lower(), (branch or "").lower(), top_n)
        if cache is not None and key in cache:
            return list(cache[key])
        results = multi_strategy_search(
            folio_raw, concept_text, branch=branch or None, top_n=top_n,
            get_branch_fn=get_branch_fn,
        )
        if cache is not None:
            if len(cache) >= 20000:  # simple unbounded-growth guard
                cache.clear()
            cache[key] = results
        return list(results)

    def _library_resolve_all(
        self, concept_text: str, branch: str
    ) -> list[tuple[FOLIOConcept, float]]:
        """Primary resolution via the pinned ``folio_matching.LabelResolver``.

        Decompose-first (a compound heading yields one concept per sibling), a calibrated
        whole-string bar on the real 0-100 scale, and branch-carrying results — then the
        deterministic place/agency gate + alias blocklist (``search.candidate_vetoed``). This is
        the migration's precision core (SCHEDULE.md row 2); ``multi_strategy_search`` remains only
        as the recall fallback when nothing here clears the bar. Returns ``[(FOLIOConcept,
        score_0_1)]``, best first, deduped by IRI.
        """
        from folio_matching import LabelResolver

        from app.services.folio.search import candidate_vetoed

        try:
            resolver = LabelResolver(self.folio.search_by_label)
            resolved = resolver.resolve(concept_text)
        except Exception:
            logger.debug("LabelResolver failed for '%s'", concept_text, exc_info=True)
            return []

        out: list[tuple[FOLIOConcept, float]] = []
        seen: set[str] = set()
        for r in resolved:
            if not r.iri or r.iri in seen:
                continue
            # Gates key on the resolved branch (score is on the library's 0-100 scale).
            if candidate_vetoed(r.surface or concept_text, r.label, r.branch, r.iri, r.score):
                continue
            fc = self.folio.get_concept(r.iri)
            if fc is None:
                continue
            if any(b in EXCLUDED_BRANCHES for b in ([fc.branch] if fc.branch else [])):
                continue
            seen.add(r.iri)
            out.append((fc, r.score / 100.0))

        # Branch hint: float a matching-branch result to the front (stable otherwise).
        if branch and out:
            out.sort(key=lambda t: 0 if (t[0].branch and branch.lower() in t[0].branch.lower()) else 1)
        return out

    def _multi_strategy_resolve_all(
        self, concept_text: str, branch: str, top_n: int = 5
    ) -> list[tuple[FOLIOConcept, float]]:
        """Return all scored candidates: library (primary) then search fork (recall fallback)."""
        merged: list[tuple[FOLIOConcept, float]] = []
        seen_iris: set[str] = set()
        for fc, score in self._library_resolve_all(concept_text, branch):
            if fc.iri and fc.iri not in seen_iris:
                seen_iris.add(fc.iri)
                merged.append((fc, score))

        for fc, score in self._fork_resolve_all(concept_text, branch, top_n):
            if fc.iri and fc.iri not in seen_iris:
                seen_iris.add(fc.iri)
                merged.append((fc, score))

        return merged[:top_n]

    def _fork_resolve_all(
        self, concept_text: str, branch: str, top_n: int = 5
    ) -> list[tuple[FOLIOConcept, float]]:
        """Recall-fallback: the folio-python 7-strategy search (multi_strategy_search)."""
        try:
            folio_raw = self.folio._get_folio()

            def _get_branch(folio_inst, iri_hash: str) -> str:
                owl_class = folio_inst[iri_hash]
                if owl_class and hasattr(owl_class, "iri"):
                    return self.folio._get_branch(owl_class.iri, [])
                return ""

            results = self._cached_multi_search(
                folio_raw, concept_text, branch, top_n, _get_branch
            )
            if not results:
                return []

            # If branch hint provided, sort preferred branch matches first
            if branch:
                results.sort(key=lambda r: (
                    0 if r.get("branch") and branch.lower() in r["branch"].lower() else 1,
                    -r["score"],
                ))

            out: list[tuple[FOLIOConcept, float]] = []
            for r in results:
                fc = FOLIOConcept(
                    iri=r["iri"],
                    preferred_label=r["label"],
                    alternative_labels=r.get("synonyms", []),
                    definition=r.get("definition", "") or "",
                    branch=r.get("branch", ""),
                    parent_iris=[],
                )
                out.append((fc, r["score"] / 100.0))
            return out
        except Exception:
            logger.debug(
                "Multi-strategy resolve_all failed for '%s'",
                concept_text,
                exc_info=True,
            )
            return []

    def _multi_strategy_resolve(
        self, concept_text: str, branch: str
    ) -> tuple[FOLIOConcept | None, float]:
        """Resolve to the single best concept: library (primary) then search fork (fallback)."""
        lib = self._library_resolve_all(concept_text, branch)
        if lib:
            best_fc, best_score = lib[0]
            if branch:
                for fc, s in lib:
                    if fc.branch and branch.lower() in fc.branch.lower():
                        best_fc, best_score = fc, s
                        break
            return best_fc, best_score
        return self._fork_resolve(concept_text, branch)

    def _fork_resolve(
        self, concept_text: str, branch: str
    ) -> tuple[FOLIOConcept | None, float]:
        """Recall-fallback single-best: the folio-python 7-strategy search."""
        try:
            folio_raw = self.folio._get_folio()

            def _get_branch(folio_inst, iri_hash: str) -> str:
                """Resolve branch for a concept IRI hash."""
                owl_class = folio_inst[iri_hash]
                if owl_class and hasattr(owl_class, "iri"):
                    return self.folio._get_branch(owl_class.iri, [])
                return ""

            results = self._cached_multi_search(
                folio_raw, concept_text, branch, 5, _get_branch
            )
            if not results:
                return None, 0.0

            # Convert the best result back to FOLIOConcept
            best = results[0]

            # If branch hint provided, prefer matches in that branch
            if branch:
                for r in results:
                    if r.get("branch") and branch.lower() in r["branch"].lower():
                        best = r
                        break

            concept = FOLIOConcept(
                iri=best["iri"],
                preferred_label=best["label"],
                alternative_labels=best.get("synonyms", []),
                definition=best.get("definition", "") or "",
                branch=best.get("branch", ""),
                parent_iris=[],
            )
            # Normalize score: multi-strategy returns 0-100, convert to 0-1
            score = best["score"] / 100.0
            return concept, score
        except Exception:
            logger.debug(
                "Multi-strategy search failed for '%s', falling back to label search",
                concept_text,
                exc_info=True,
            )
            # Fallback to basic label search
            results = self.folio.search_by_label(concept_text, top_k=3)
            if not results:
                return None, 0.0
            best_concept, score = results[0]
            if branch:
                for concept, s in results:
                    if branch.lower() in concept.branch.lower():
                        best_concept, score = concept, s
                        break
            return best_concept, score

    def resolve_batch(
        self,
        concepts: list[dict],
    ) -> list[ResolvedConcept | None]:
        return [
            self.resolve(
                c.get("concept_text", ""),
                branches=c.get("branches", []),
                confidence=c.get("confidence", 0.0),
                source=c.get("source", "llm"),
                folio_iri=c.get("folio_iri"),
            )
            for c in concepts
        ]

    @property
    def cache_size(self) -> int:
        return len(self._cache)
