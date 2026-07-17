"""Multi-strategy FOLIO search with word-overlap scoring.

The scorer is now the pinned ``folio_resolve`` library (migration SCHEDULE.md row 2): the
word-order-invariant relevance scorer, stopwords, and legal expansions previously forked here
("ported from folio-mapper") are consumed from ``folio_resolve.scoring`` so folio-enrich,
folio-mapper, and folio-insights all score identically. This module keeps only the
folio-python search orchestration (7-strategy candidate gathering + ancestor surfacing) and
adds the library's deterministic precision gates at the boundary:

* ``PlaceNameGate`` — a generic term that fuzzy-latches a short place / governmental-body label
  (``justice`` -> U.S. Dept. of Justice, ``tax`` -> U.S. Tax Court) is vetoed unless the surface
  term exactly equals the label. Keys on the branch each candidate already carries.
* ``AliasBlocklist`` — recorded homonym pairings with real FOLIO IRIs (``Action`` -> *Auction*)
  are dropped regardless of score.

Score scale: folio-python + ``compute_relevance_score`` are both **0-100**; the gates also expect
0-100, so no rescaling happens inside this module. ``ConceptResolver`` divides by 100 at its own
boundary (unchanged).
"""

from __future__ import annotations

import logging

from folio_resolve import AliasBlocklist, PlaceNameGate, load_seed_blocklist
from folio_resolve.scoring import (
    LEGAL_TERM_EXPANSIONS,
    SEARCH_STOPWORDS,
    compute_relevance_score,
    content_words,
    generate_search_terms,
    tokenize,
)

from app.services.folio.branch_config import (
    EXCLUDED_BRANCHES,
    get_branch_color,
)

logger = logging.getLogger(__name__)

# Re-exported for back-compat: a few call sites / tests import these names from here. They now
# resolve to the pinned library's single source of truth.
__all__ = ["LEGAL_TERM_EXPANSIONS", "SEARCH_STOPWORDS", "candidate_vetoed", "multi_strategy_search"]

# Deterministic precision gates (module singletons; pure/stateless -> safe to share).
_PLACE_GATE = PlaceNameGate(min_signals=2)
_BLOCKLIST: AliasBlocklist | None = None


def _blocklist() -> AliasBlocklist:
    global _BLOCKLIST
    if _BLOCKLIST is None:
        _BLOCKLIST = load_seed_blocklist()
    return _BLOCKLIST


def candidate_vetoed(query: str, label: str, branch: str, iri: str, score: float) -> bool:
    """True if a candidate is a place/agency mis-map or a blocklisted homonym.

    ``multi_strategy_search`` is a single un-corroborated search path, so the place gate sees
    ``corroborating_signals=1`` and vetoes any place/governmental-body candidate whose surface
    term does not exactly equal the resolved label (score is on the library's 0-100 scale).
    """
    if _blocklist().is_blocked(query, iri):
        logger.debug("alias blocklist vetoed %r -> %s", query, iri)
        return True
    decision = _PLACE_GATE.evaluate(
        query=query,
        label=label,
        branch=branch,
        score=score,
        heading_context_match=False,
        corroborating_signals=1,
    )
    if decision.demoted:
        logger.debug("place/agency gate vetoed %r -> %s [%s] (%s)", query, iri, branch, decision.reason)
        return True
    return False


def _extract_iri_hash(iri: str) -> str:
    """Extract the hash portion from a full FOLIO IRI."""
    return iri.rsplit("/", 1)[-1]


def multi_strategy_search(
    folio,
    text: str,
    branch: str | None = None,
    top_n: int = 5,
    threshold: float = 30.0,
    get_branch_fn=None,
) -> list[dict]:
    """Search FOLIO using multi-strategy search with word-overlap scoring.

    Args:
        folio: FOLIO instance from folio-python.
        text: The concept text to search for.
        branch: Optional branch filter (display name).
        top_n: Maximum results to return.
        threshold: Minimum score (0-100) for inclusion.
        get_branch_fn: Optional callable(folio, iri_hash) -> branch_name.

    Returns:
        List of dicts with keys: label, iri, iri_hash, definition, synonyms,
        branch, branch_color, score.
    """
    query_content = content_words(text)
    if not query_content:
        query_content = set(tokenize(text))

    search_terms = generate_search_terms(text)

    # Phase 1: Gather raw candidates from multiple search strategies
    raw: dict[str, object] = {}  # iri_hash -> OWLClass

    for st in search_terms:
        # Label search (fuzzy)
        try:
            for owl_class, _ in folio.search_by_label(st, include_alt_labels=True, limit=25):
                h = _extract_iri_hash(owl_class.iri)
                if h not in raw:
                    raw[h] = owl_class
        except Exception:
            pass

        # Prefix search
        if len(st) >= 3:
            try:
                for owl_class in folio.search_by_prefix(st):
                    h = _extract_iri_hash(owl_class.iri)
                    if h not in raw:
                        raw[h] = owl_class
            except Exception:
                pass

    # Stem prefix search
    for cw in query_content:
        if len(cw) >= 6:
            stem = cw[: len(cw) - 2]
            try:
                for owl_class in folio.search_by_prefix(stem)[:50]:
                    h = _extract_iri_hash(owl_class.iri)
                    if h not in raw:
                        raw[h] = owl_class
            except Exception:
                pass

    # Definition search
    def_terms = [text]
    cw_phrase = " ".join(sorted(query_content))
    if cw_phrase.lower() != text.lower():
        def_terms.append(cw_phrase)
    for st in def_terms:
        if len(st) >= 3:
            try:
                for owl_class, _ in folio.search_by_definition(st, limit=20):
                    h = _extract_iri_hash(owl_class.iri)
                    if h not in raw:
                        raw[h] = owl_class
            except Exception:
                pass

    logger.debug("multi_strategy_search(%r): %d raw candidates", text, len(raw))

    # Phase 2: Re-score all candidates (pinned library scorer)
    min_score = threshold
    scored: list[tuple[str, object, float]] = []

    for iri_hash, owl_class in raw.items():
        score = compute_relevance_score(
            query_content,
            text,
            owl_class.label or iri_hash,
            owl_class.definition,
            owl_class.alternative_labels or [],
            preferred_label=owl_class.preferred_label,
        )
        if score >= min_score:
            scored.append((iri_hash, owl_class, score))

    # Phase 2.1: Expansion re-scoring
    expansion_queries: list[tuple[set[str], str]] = []
    for w in query_content:
        suffixes = LEGAL_TERM_EXPANSIONS.get(w)
        if suffixes:
            for suffix in suffixes:
                eq = f"{w} {suffix}"
                expansion_queries.append((content_words(eq), eq))

    if expansion_queries:
        best_scores: dict[str, float] = {h: s for h, _, s in scored}
        for iri_hash, owl_class in raw.items():
            for eq_content, eq_full in expansion_queries:
                exp_score = compute_relevance_score(
                    eq_content,
                    eq_full,
                    owl_class.label or iri_hash,
                    owl_class.definition,
                    owl_class.alternative_labels or [],
                    preferred_label=owl_class.preferred_label,
                )
                if exp_score >= min_score and exp_score > best_scores.get(iri_hash, 0):
                    best_scores[iri_hash] = exp_score

        scored_map: dict[str, tuple[str, object, float]] = {
            h: (h, c, s) for h, c, s in scored
        }
        for iri_hash, new_score in best_scores.items():
            if iri_hash in scored_map:
                _, owl_class, old_score = scored_map[iri_hash]
                if new_score > old_score:
                    scored_map[iri_hash] = (iri_hash, owl_class, new_score)
            elif new_score >= min_score:
                scored_map[iri_hash] = (iri_hash, raw[iri_hash], new_score)
        scored = list(scored_map.values())

    # Phase 2.5: Surface ancestor concepts
    ancestor_scores: dict[str, float] = {}
    for iri_hash, owl_class, score in scored:
        if score < 50:
            continue
        current = owl_class
        for depth in range(1, 4):
            if not current or not getattr(current, "sub_class_of", None):
                break
            parent_hash = _extract_iri_hash(current.sub_class_of[0])
            if parent_hash not in raw:
                parent_score = score * (0.85 ** depth)
                if parent_score >= min_score:
                    ancestor_scores[parent_hash] = max(
                        ancestor_scores.get(parent_hash, 0), parent_score
                    )
            current = folio[parent_hash]

    for parent_hash, pscore in ancestor_scores.items():
        parent_class = folio[parent_hash]
        if parent_class:
            scored.append((parent_hash, parent_class, round(pscore, 1)))

    # Sort by score descending
    scored.sort(key=lambda x: x[2], reverse=True)

    # Phase 3: Build results with branch filtering + deterministic precision gates
    results: list[dict] = []
    seen_hashes: set[str] = set()

    for iri_hash, owl_class, score in scored:
        if iri_hash in seen_hashes:
            continue
        seen_hashes.add(iri_hash)

        # Determine branch
        branch_name = ""
        if get_branch_fn:
            branch_name = get_branch_fn(folio, iri_hash)
        if branch_name in EXCLUDED_BRANCHES:
            continue

        # Deterministic precision gates (place/agency mis-map + alias blocklist). Both key on the
        # branch the candidate now carries, so a generic term can no longer latch a place label.
        if candidate_vetoed(text, owl_class.label or "", branch_name, owl_class.iri, score):
            continue

        if branch and branch_name and branch.lower() not in branch_name.lower():
            # Branch filter active and doesn't match — still include but lower priority
            pass

        results.append({
            "label": owl_class.label or iri_hash,
            "iri": owl_class.iri,
            "iri_hash": iri_hash,
            "definition": owl_class.definition,
            "synonyms": owl_class.alternative_labels or [],
            "branch": branch_name,
            "branch_color": get_branch_color(branch_name) if branch_name else "",
            "score": score,
        })

        if len(results) >= top_n:
            break

    return results
