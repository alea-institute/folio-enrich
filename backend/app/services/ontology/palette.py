"""Deterministic branch -> color assignment for auto-derived ontology branches.

FOLIO keeps its hand-curated palette in ``branch_config.py``. Ontologies whose
branches are auto-derived at runtime (e.g. the Catholic Semantic Canon) don't have
a hand-authored color per branch, so we assign one from a fixed ramp by a *stable*
hash of the branch name.

Uses blake2b, NOT the builtin ``hash()`` — Python salts ``hash(str)`` per process
(``PYTHONHASHSEED``), which would give the same branch different colors across
workers/restarts and silently break color stability (plan AC-8).
"""

from __future__ import annotations

import hashlib

# A sacral / illuminated-manuscript ramp (crimson, gold, indigo, sage, umber, …),
# deliberately distinct from FOLIO's cool legal palette. 12 entries; branch counts
# beyond this cycle by modulo (defined overflow behavior).
SACRAL_RAMP: tuple[str, ...] = (
    "#c34455",  # cardinal crimson
    "#c9a227",  # antique gold
    "#4b3f72",  # indigo
    "#6f7f52",  # ordinary-time sage
    "#9c6b3f",  # manuscript umber
    "#7a1f2b",  # oxblood
    "#b08d57",  # brass
    "#3f5a6b",  # slate teal
    "#8f5b8a",  # muted amethyst
    "#a8563e",  # terracotta
    "#5c6f4a",  # olive
    "#b5843a",  # ochre
)


def color_for_branch(branch_name: str, ramp: tuple[str, ...] = SACRAL_RAMP) -> str:
    """Return a stable hex color for a branch name.

    Deterministic across processes and restarts for the same name + ramp.
    """
    if not ramp:
        raise ValueError("ramp must be non-empty")
    digest = hashlib.blake2b(branch_name.encode("utf-8"), digest_size=4).digest()
    return ramp[int.from_bytes(digest, "big") % len(ramp)]
