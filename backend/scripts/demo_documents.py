"""Demo documents for FOLIO Enrich "Try an Exemplar" demo mode.

The 22 pre-baked exemplars (7 "Rich Enrichment" + 15 "Quick Start") are sourced from
the frontend's inline ``SAMPLES`` object — the single source of truth for exemplar text
(see ``extract_exemplars.py``). This module exposes:

- ``DEMO_DOCUMENTS`` — ``{slug: {title, description, group}}`` metadata, keyed by the 22
  exemplar slugs. Importing this is cheap (no Node call), so freshness checks and tests
  can read ``DEMO_DOCUMENTS.keys()`` without extracting text.
- ``load_demo_documents()`` — returns the same dict with each entry's ``text`` populated
  from the frontend SAMPLES (requires Node; called only at generation time).
"""

from __future__ import annotations

from scripts.canon_exemplars import CANON_EXEMPLAR_SLUGS, CANON_META, extract_canon_texts
from scripts.extract_exemplars import EXEMPLAR_META, EXEMPLAR_SLUGS, extract_exemplar_texts

# Metadata only (no text) — cheap to import; keys define the expected demo slugs.
DEMO_DOCUMENTS: dict[str, dict] = {slug: dict(EXEMPLAR_META[slug]) for slug in EXEMPLAR_SLUGS}


def load_demo_documents(ontology: str = "folio") -> dict[str, dict]:
    """Return ``{slug: {title, description, group, text}}`` for an ontology's exemplars.

    - ``folio`` (default): the 22 FOLIO exemplars, text extracted from the frontend
      inline SAMPLES object (requires Node).
    - ``canon``: the four Catholic Semantic Canon exemplars, text extracted from
      ``frontend/demos/canon_samples.js`` (requires Node).

    Any other ontology id raises ``ValueError``.
    """
    if ontology == "folio":
        texts = extract_exemplar_texts()
        return {
            slug: {**EXEMPLAR_META[slug], "text": texts[slug]}
            for slug in EXEMPLAR_SLUGS
        }
    if ontology == "canon":
        texts = extract_canon_texts()
        return {
            slug: {**CANON_META[slug], "text": texts[slug]}
            for slug in CANON_EXEMPLAR_SLUGS
        }
    raise ValueError(f"No demo documents defined for ontology '{ontology}'")
