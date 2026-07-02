"""Neutral, ontology-agnostic records passed across the service boundary."""

from __future__ import annotations

from typing import NamedTuple


class ConceptRecord(NamedTuple):
    """Minimal concept data for consumers that only need raw label text
    (e.g. the embedding index builder) — so they never reach through the ontology
    service into the underlying folio-python graph."""

    iri: str
    label: str
    definition: str
    examples: list[str]
