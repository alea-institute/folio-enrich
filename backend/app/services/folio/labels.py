"""Recover label provenance that newer folio-python flattens during parsing."""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_OWL_CLASS = "{http://www.w3.org/2002/07/owl#}Class"
_RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
_SKOS_ALT_LABEL = "{http://www.w3.org/2004/02/skos/core#}altLabel"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def norm_label(s: str) -> str:
    """Normalize a label for comparison only: trim, collapse internal whitespace, casefold."""
    return _WS_RE.sub(" ", (s or "").strip()).casefold()


def untagged_alt_labels(folio) -> dict[str, set[str]] | None:
    """Cache untagged skos:altLabel texts by exact class IRI, or None without a tree.

    Newer folio-python folds tagged altLabels into alternative_labels and keeps
    only the last translation per language. The OWL tags retain the provenance
    that cannot be recovered by subtracting translation text. Cache on the FOLIO
    object so a reload's new object gets its own map.
    """
    tree = getattr(folio, "tree", None)
    if tree is None:
        return None
    cached = getattr(folio, "_untagged_alt_labels_cache", None)
    if cached is not None:
        return cached
    labels: dict[str, set[str]] = {}
    for node in tree.iterchildren(_OWL_CLASS):
        iri = node.get(_RDF_ABOUT)
        if iri is None:
            continue
        texts = labels.setdefault(iri, set())
        for alt in node.iterchildren(_SKOS_ALT_LABEL):
            if alt.get(_XML_LANG) is None and alt.text is not None:
                texts.add(alt.text)
    folio._untagged_alt_labels_cache = labels
    return labels


def true_alternative_labels(folio, owl_class) -> list[str]:
    """Keep untagged aliases and the hidden label in folio-python's original order.

    Newer folio-python appends tagged altLabels too, but translations retains only
    one value per language. Use OWL provenance whenever available; tree-less fakes
    fall back to normalized subtraction of the available translation values.
    """
    alternatives = getattr(owl_class, "alternative_labels", None) or []
    untagged = untagged_alt_labels(folio)
    if untagged is None:
        translated = {
            norm_label(value)
            for value in (getattr(owl_class, "translations", None) or {}).values()
        }
        return [alt for alt in alternatives if norm_label(alt) not in translated]
    texts = untagged.get(owl_class.iri, set())
    hidden_label = getattr(owl_class, "hidden_label", None)
    return [alt for alt in alternatives if alt in texts or alt == hidden_label]
