"""Single source of truth for label-match tier semantics.

Both the FOLIO label index (``folio_service``) and any downstream
disambiguation ranking import their priority ordering from here so the
index and the ranker can never disagree on what "lemma-primary beats
exact-alt" means.

Ordering (lower rank = higher priority, wins the single-winner index):

    preferred  >  lemma_preferred  >  alternative  >  lemma_alternative  >  hidden  >  translation
"""

from __future__ import annotations

# label_type string -> priority rank. Lower wins. Unknown types sort last.
LABEL_TYPE_ORDER: dict[str, int] = {
    "preferred": 0,
    "lemma_preferred": 1,
    "alternative": 2,
    "lemma_alternative": 3,
    "hidden": 4,
    "translation": 5,
}

# label_types produced by lemma normalization.
LEMMA_LABEL_TYPES: frozenset[str] = frozenset({"lemma_preferred", "lemma_alternative"})

# label_types considered canonical/primary (vs. alternative/synonym).
PRIMARY_LABEL_TYPES: frozenset[str] = frozenset({"preferred", "lemma_preferred"})


def label_type_rank(label_type: str) -> int:
    """Return the priority rank for a label_type (lower = higher priority)."""
    return LABEL_TYPE_ORDER.get(label_type, 99)


def is_higher_priority(new_type: str, existing_type: str) -> bool:
    """True if ``new_type`` should overwrite ``existing_type`` in a single-winner map."""
    return label_type_rank(new_type) < label_type_rank(existing_type)


def lemma_type_for(base_label_type: str) -> str:
    """Map a base label_type to its lemma-derived counterpart."""
    return "lemma_preferred" if base_label_type in PRIMARY_LABEL_TYPES else "lemma_alternative"
