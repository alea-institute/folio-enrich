"""Rich concept detail and entity graph building for FOLIO concepts.

Provides lookup_concept_detail() for full concept info (children, siblings,
translations, hierarchy path, examples) and build_entity_graph() for BFS
graph exploration.
"""

from __future__ import annotations

import logging
import re

from app.models.graph_models import (
    ConceptDetail,
    EntityGraphResponse,
    GraphEdge,
    GraphNode,
    HierarchyPathEntry,
)
from app.services.folio.branch_config import get_branch_color

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")


def _norm_label(s: str) -> str:
    """Normalize a label for comparison only: trim, collapse internal whitespace, casefold."""
    return _WS_RE.sub(" ", (s or "").strip()).casefold()


def _true_synonyms(
    alternative_labels: list[str],
    translations: dict[str, str],
    hidden_label: str,
    label: str,
) -> list[str]:
    """Return true synonyms from a concept's ``alternative_labels``.

    folio-python folds every ``skos:altLabel`` into one ``alternative_labels`` list,
    including ``xml:lang``-tagged translations, plus the ``skos:hiddenLabel`` code.
    True synonyms are what remains after removing the translation values, the hidden
    code, and the concept's own label. Comparison is normalized (case/whitespace
    insensitive); the original text and order of surviving synonyms are preserved,
    and normalized-duplicate entries are dropped.
    """
    excluded = {_norm_label(v) for v in (translations or {}).values()}
    if hidden_label:
        excluded.add(_norm_label(hidden_label))
    if label:
        excluded.add(_norm_label(label))
    out: list[str] = []
    seen: set[str] = set()
    for alt in alternative_labels or []:
        key = _norm_label(alt)
        if not key or key in excluded or key in seen:
            continue
        seen.add(key)
        out.append(alt)
    return out


def _extract_iri_hash(iri: str) -> str:
    """Extract the hash portion from a full FOLIO IRI."""
    return iri.rsplit("/", 1)[-1]


def _get_branch_for_class(folio, iri: str, branch_root_iris: dict[str, str], cache: dict[str, str]) -> str:
    """Walk parent chain to find which branch a class belongs to. Cached.

    ``iri`` and the keys of ``branch_root_iris`` are FULL IRIs, so lookups work
    for any ontology (folio-python's ``folio[bare_hash]`` only resolves FOLIO).
    """
    if iri in cache:
        return cache[iri]

    if iri in branch_root_iris:
        cache[iri] = branch_root_iris[iri]
        return branch_root_iris[iri]

    owl_class = folio[iri]
    if not owl_class or not owl_class.sub_class_of:
        cache[iri] = "Unknown"
        return "Unknown"

    visited: set[str] = {iri}
    current_parents = owl_class.sub_class_of

    for _ in range(20):
        if not current_parents:
            break
        next_parents: list[str] = []
        for parent_iri in current_parents:
            if parent_iri in visited:
                continue
            visited.add(parent_iri)
            if parent_iri in branch_root_iris:
                branch_name = branch_root_iris[parent_iri]
                cache[iri] = branch_name
                return branch_name
            parent_class = folio[parent_iri]
            if parent_class and parent_class.sub_class_of:
                next_parents.extend(parent_class.sub_class_of)
        current_parents = next_parents

    cache[iri] = "Unknown"
    return "Unknown"


def _init_branch_roots(folio) -> dict[str, str]:
    """Build mapping of branch root FULL IRIs to display names.

    FOLIO's ``FOLIO_TYPE_IRIS`` provides bare hashes; those are wrapped to full
    FOLIO IRIs. Additional roots (any ontology) are discovered via
    ``sub_class_of == [owl#Thing]`` and keyed by their full ``owl_class.iri``.
    """
    from folio import FOLIO_TYPE_IRIS
    from app.services.folio.branch_config import get_branch_display_name

    roots: dict[str, str] = {}
    for ft, iri_hash in FOLIO_TYPE_IRIS.items():
        display_name = get_branch_display_name(ft.name)
        roots[f"https://folio.openlegalstandard.org/{iri_hash}"] = display_name

    # Discover additional root classes (keyed by full IRI)
    owl_thing = "http://www.w3.org/2002/07/owl#Thing"
    for owl_class in folio.classes:
        if owl_class.iri in roots:
            continue
        if owl_class.sub_class_of and owl_class.sub_class_of == [owl_thing]:
            label = owl_class.label or _extract_iri_hash(owl_class.iri)
            roots[owl_class.iri] = label

    return roots


def _build_hierarchy_path(folio, iri: str, branch_root_iris: dict[str, str]) -> list[HierarchyPathEntry]:
    """Build hierarchy path from root branch down to this class. ``iri`` is a full IRI."""
    path: list[HierarchyPathEntry] = []
    owl_class = folio[iri]
    if not owl_class:
        return path

    current = owl_class
    visited: set[str] = set()
    while current and len(path) < 10:
        if current.iri in visited:
            break
        visited.add(current.iri)
        path.append(HierarchyPathEntry(
            label=current.label or _extract_iri_hash(current.iri),
            iri_hash=_extract_iri_hash(current.iri),
            iri=current.iri,
        ))
        if current.iri in branch_root_iris:
            break
        if current.sub_class_of:
            current = folio[current.sub_class_of[0]]
        else:
            break

    path.reverse()
    return path


def _build_all_hierarchy_paths(
    folio, iri: str, branch_root_iris: dict[str, str]
) -> list[list[HierarchyPathEntry]]:
    """Build all hierarchy paths for a polyhierarchy concept.

    Returns one root→target path per immediate parent. If the concept has
    ≤1 parent, returns the single path from ``_build_hierarchy_path``.
    ``iri`` is a full IRI.
    """
    owl_class = folio[iri]
    if not owl_class:
        return []

    parents = owl_class.sub_class_of or []
    owl_thing = "http://www.w3.org/2002/07/owl#Thing"
    real_parents = [p for p in parents if p != owl_thing]

    if len(real_parents) <= 1:
        single = _build_hierarchy_path(folio, iri, branch_root_iris)
        return [single] if single else []

    target_entry = HierarchyPathEntry(
        label=owl_class.label or _extract_iri_hash(owl_class.iri),
        iri_hash=_extract_iri_hash(owl_class.iri),
        iri=owl_class.iri,
    )

    paths: list[list[HierarchyPathEntry]] = []
    for parent_iri in real_parents:
        parent_path = _build_hierarchy_path(folio, parent_iri, branch_root_iris)
        if parent_path:
            paths.append(parent_path + [target_entry])

    # Deduplicate identical paths (same sequence of iri_hashes)
    seen: set[tuple[str, ...]] = set()
    unique: list[list[HierarchyPathEntry]] = []
    for p in paths:
        key = tuple(e.iri_hash for e in p)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return unique or [_build_hierarchy_path(folio, iri, branch_root_iris)]


def _get_all_parents(folio, iri: str) -> list[HierarchyPathEntry]:
    """Return all immediate parents of a class (for polyhierarchy DAG display). ``iri`` is a full IRI."""
    owl_class = folio[iri]
    if not owl_class or not owl_class.sub_class_of:
        return []

    owl_thing = "http://www.w3.org/2002/07/owl#Thing"
    parents: list[HierarchyPathEntry] = []
    for parent_iri in owl_class.sub_class_of:
        if parent_iri == owl_thing:
            continue
        parent_class = folio[parent_iri]
        if parent_class:
            parents.append(HierarchyPathEntry(
                label=parent_class.label or _extract_iri_hash(parent_iri),
                iri_hash=_extract_iri_hash(parent_iri),
                iri=parent_class.iri,
            ))
    parents.sort(key=lambda e: e.label)
    return parents


def lookup_concept_detail(folio, identifier: str) -> ConceptDetail | None:
    """Look up a concept with extended detail.

    ``identifier`` may be a full IRI (any ontology) or a bare FOLIO hash —
    folio-python resolves both via ``folio[...]``. All internal traversal uses
    the canonical full IRI (``owl_class.iri``) so non-FOLIO ontologies resolve.
    """
    owl_class = folio[identifier]
    if not owl_class:
        return None

    iri = owl_class.iri  # canonical full IRI
    iri_hash = _extract_iri_hash(iri)  # true bare hash for display

    branch_root_iris = _init_branch_roots(folio)
    branch_cache: dict[str, str] = {}
    branch_name = _get_branch_for_class(folio, iri, branch_root_iris, branch_cache)

    # Children
    children: list[HierarchyPathEntry] = []
    if owl_class.parent_class_of:
        for child_iri in owl_class.parent_class_of:
            child_class = folio[child_iri]
            if child_class:
                children.append(HierarchyPathEntry(
                    label=child_class.label or _extract_iri_hash(child_iri),
                    iri_hash=_extract_iri_hash(child_iri),
                    iri=child_class.iri,
                ))
    children.sort(key=lambda e: e.label)

    # Siblings
    siblings: list[HierarchyPathEntry] = []
    if owl_class.sub_class_of:
        parent_class = folio[owl_class.sub_class_of[0]]
        if parent_class and parent_class.parent_class_of:
            for sibling_iri in parent_class.parent_class_of:
                if sibling_iri == iri:
                    continue
                sibling_class = folio[sibling_iri]
                if sibling_class:
                    siblings.append(HierarchyPathEntry(
                        label=sibling_class.label or _extract_iri_hash(sibling_iri),
                        iri_hash=_extract_iri_hash(sibling_iri),
                        iri=sibling_class.iri,
                    ))
    siblings.sort(key=lambda e: e.label)

    # Related (see_also)
    related: list[HierarchyPathEntry] = []
    if hasattr(owl_class, "see_also") and owl_class.see_also:
        for related_iri in owl_class.see_also:
            related_class = folio[related_iri]
            if related_class:
                related.append(HierarchyPathEntry(
                    label=related_class.label or _extract_iri_hash(related_iri),
                    iri_hash=_extract_iri_hash(related_iri),
                    iri=related_class.iri,
                ))
    related.sort(key=lambda e: e.label)

    # Examples and translations
    examples = list(owl_class.examples) if hasattr(owl_class, "examples") and owl_class.examples else []
    translations = dict(owl_class.translations) if hasattr(owl_class, "translations") and owl_class.translations else {}

    hierarchy_paths = _build_all_hierarchy_paths(folio, iri, branch_root_iris)

    # FOLIO skos:prefLabel — include when it differs from rdfs:label
    folio_pref = getattr(owl_class, "preferred_label", "") or ""
    pref_label_val = folio_pref if folio_pref and folio_pref.lower() != (owl_class.label or "").lower() else None

    # OWL metadata fields
    deprecated = bool(getattr(owl_class, "deprecated", False))
    notes = list(owl_class.notes) if hasattr(owl_class, "notes") and owl_class.notes else []
    editorial_note = getattr(owl_class, "editorial_note", "") or None
    comment = getattr(owl_class, "comment", "") or None
    description_val = getattr(owl_class, "description", "") or None
    source = getattr(owl_class, "source", "") or None
    history_note = getattr(owl_class, "history_note", "") or None
    country = getattr(owl_class, "country", "") or None

    return ConceptDetail(
        label=owl_class.label or iri_hash,
        iri=iri,
        iri_hash=iri_hash,
        definition=owl_class.definition,
        preferred_label=pref_label_val,
        synonyms=_true_synonyms(
            owl_class.alternative_labels or [],
            translations,
            getattr(owl_class, "hidden_label", "") or "",
            owl_class.label or "",
        ),
        branch=branch_name,
        branch_color=get_branch_color(branch_name),
        hierarchy_path=hierarchy_paths[0] if hierarchy_paths else [],
        hierarchy_paths=hierarchy_paths,
        all_parents=_get_all_parents(folio, iri),
        children=children,
        siblings=siblings,
        related=related,
        examples=examples,
        translations=translations,
        deprecated=deprecated,
        notes=notes,
        editorial_note=editorial_note,
        comment=comment,
        description=description_val,
        source=source,
        history_note=history_note,
        country=country,
    )


def build_entity_graph(
    folio,
    identifier: str,
    ancestors_depth: int = 2,
    descendants_depth: int = 2,
    max_nodes: int = 200,
    include_see_also: bool = True,
    max_see_also_per_node: int = 5,
) -> EntityGraphResponse | None:
    """Build a multi-hop graph around a concept via BFS.

    ``identifier`` may be a full IRI (any ontology) or a bare FOLIO hash.
    Node ids and edges use bare hashes; all ``folio[...]`` lookups use full IRIs
    (tracked in ``hash_to_iri``) so non-FOLIO ontologies resolve.
    """
    owl_class = folio[identifier]
    if not owl_class:
        return None

    iri_hash = _extract_iri_hash(owl_class.iri)  # true bare hash of the focus

    branch_root_iris = _init_branch_roots(folio)
    branch_cache: dict[str, str] = {}
    owl_thing = "http://www.w3.org/2002/07/owl#Thing"
    visited: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    edge_ids: set[str] = set()
    total_discovered_ref = [0]
    # Map bare hash -> full IRI so lookups resolve for any ontology.
    hash_to_iri: dict[str, str] = {iri_hash: owl_class.iri}

    def _full(h: str) -> str:
        return hash_to_iri.get(h, h)

    def _make_node(h: str, depth: int) -> GraphNode | None:
        if h in visited:
            return visited[h]
        oc = folio[_full(h)]
        if not oc:
            return None
        hash_to_iri[h] = oc.iri
        total_discovered_ref[0] += 1
        if len(visited) >= max_nodes:
            return None
        branch_name = _get_branch_for_class(folio, oc.iri, branch_root_iris, branch_cache)
        node = GraphNode(
            id=h,
            label=oc.label or h,
            iri=oc.iri,
            definition=oc.definition,
            branch=branch_name,
            branch_color=get_branch_color(branch_name),
            is_focus=(h == iri_hash),
            is_branch_root=(oc.iri in branch_root_iris),
            child_count=len(oc.parent_class_of or []),
            depth=depth,
        )
        visited[h] = node
        return node

    def _add_edge(source: str, target: str, edge_type: str, label: str | None = None) -> None:
        eid = f"{source}->{target}:{edge_type}"
        if eid in edge_ids:
            return
        edge_ids.add(eid)
        edges.append(GraphEdge(id=eid, source=source, target=target, edge_type=edge_type, label=label))

    # Create focus node
    focus_node = _make_node(iri_hash, 0)
    if not focus_node:
        return None

    # BFS upward (ancestors) — always reach branch roots
    ancestor_max_depth = max(ancestors_depth, 50)
    ancestor_queue: list[tuple[str, int]] = [(iri_hash, 0)]
    ancestor_visited: set[str] = {iri_hash}
    while ancestor_queue:
        current_hash, current_depth = ancestor_queue.pop(0)
        if current_depth >= ancestor_max_depth:
            continue
        current_oc = folio[_full(current_hash)]
        if not current_oc or not current_oc.sub_class_of:
            continue
        for parent_iri in current_oc.sub_class_of:
            if parent_iri == owl_thing:
                continue
            parent_hash = _extract_iri_hash(parent_iri)
            hash_to_iri[parent_hash] = parent_iri
            parent_node = _make_node(parent_hash, -(current_depth + 1))
            if parent_node is None:
                continue
            _add_edge(parent_hash, current_hash, "subClassOf")
            if parent_hash not in ancestor_visited:
                ancestor_visited.add(parent_hash)
                ancestor_queue.append((parent_hash, current_depth + 1))

    # BFS downward (descendants)
    descendant_queue: list[tuple[str, int]] = [(iri_hash, 0)]
    descendant_visited: set[str] = {iri_hash}
    while descendant_queue:
        current_hash, current_depth = descendant_queue.pop(0)
        if current_depth >= descendants_depth:
            continue
        current_oc = folio[_full(current_hash)]
        if not current_oc or not current_oc.parent_class_of:
            continue
        for child_iri in current_oc.parent_class_of:
            child_hash = _extract_iri_hash(child_iri)
            hash_to_iri[child_hash] = child_iri
            child_node = _make_node(child_hash, current_depth + 1)
            if child_node is None:
                continue
            _add_edge(current_hash, child_hash, "subClassOf")
            if child_hash not in descendant_visited:
                descendant_visited.add(child_hash)
                descendant_queue.append((child_hash, current_depth + 1))

    # Collect seeAlso cross-links
    see_also_nodes: list[str] = []
    if include_see_also:
        for node_hash in list(visited.keys()):
            oc = folio[_full(node_hash)]
            if not oc or not hasattr(oc, "see_also") or not oc.see_also:
                continue
            sa_count = 0
            for related_iri in oc.see_also:
                if sa_count >= max_see_also_per_node:
                    break
                related_hash = _extract_iri_hash(related_iri)
                hash_to_iri[related_hash] = related_iri
                was_new = related_hash not in visited
                if was_new:
                    related_node = _make_node(related_hash, 0)
                    if related_node is None:
                        continue
                    see_also_nodes.append(related_hash)
                if node_hash < related_hash:
                    _add_edge(node_hash, related_hash, "seeAlso", "rdfs:seeAlso")
                else:
                    _add_edge(related_hash, node_hash, "seeAlso", "rdfs:seeAlso")
                sa_count += 1

    # BFS upward from seeAlso nodes to their branch roots (unbounded depth)
    if see_also_nodes:
        sa_max_depth = 50  # effectively unbounded — always reach branch roots
        sa_ancestor_queue: list[tuple[str, int]] = [(h, 0) for h in see_also_nodes]
        sa_ancestor_visited: set[str] = set(see_also_nodes) | ancestor_visited
        while sa_ancestor_queue:
            current_hash, current_depth = sa_ancestor_queue.pop(0)
            if current_depth >= sa_max_depth:
                continue
            current_oc = folio[_full(current_hash)]
            if not current_oc or not current_oc.sub_class_of:
                continue
            for parent_iri in current_oc.sub_class_of:
                if parent_iri == owl_thing:
                    continue
                parent_hash = _extract_iri_hash(parent_iri)
                hash_to_iri[parent_hash] = parent_iri
                parent_node = _make_node(parent_hash, -(current_depth + 1))
                if parent_node is None:
                    continue
                _add_edge(parent_hash, current_hash, "subClassOf")
                if parent_hash not in sa_ancestor_visited:
                    sa_ancestor_visited.add(parent_hash)
                    sa_ancestor_queue.append((parent_hash, current_depth + 1))

    # Post-pass: classify branch root types
    for h, node in visited.items():
        if not node.is_branch_root:
            continue
        if h in ancestor_visited:
            node.branch_root_type = "ultimate"
        else:
            node.branch_root_type = "ancillary"

    truncated = total_discovered_ref[0] > len(visited)

    return EntityGraphResponse(
        focus_iri_hash=iri_hash,
        focus_label=owl_class.label or iri_hash,
        focus_branch=_get_branch_for_class(folio, owl_class.iri, branch_root_iris, branch_cache),
        nodes=list(visited.values()),
        edges=edges,
        truncated=truncated,
        total_concept_count=total_discovered_ref[0],
    )
