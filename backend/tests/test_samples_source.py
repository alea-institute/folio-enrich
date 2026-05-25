"""Guard the single source of truth for exemplar text.

The frontend inline ``SAMPLES`` object is canonical. These tests ensure the 22 demo
exemplars stay in sync with it: every demo slug must (a) have a ``loadSample('<slug>')``
button in index.html and (b) extract a non-empty text from SAMPLES.
"""

from __future__ import annotations

import shutil

import pytest

from scripts.extract_exemplars import (
    EXEMPLAR_META,
    EXEMPLAR_SLUGS,
    INDEX_HTML,
    extract_exemplar_texts,
)

_NODE = shutil.which("node")


def test_meta_covers_all_slugs() -> None:
    assert set(EXEMPLAR_META) == set(EXEMPLAR_SLUGS)
    assert len(EXEMPLAR_SLUGS) == 22, "Expected 22 exemplars (7 Rich + 15 Quick Start)"


def test_every_exemplar_has_a_button() -> None:
    """Each demo slug must be wired to a loadSample() button in the frontend."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    missing = [s for s in EXEMPLAR_SLUGS if f"loadSample('{s}')" not in html]
    assert not missing, f"Exemplar slugs with no loadSample() button: {missing}"


@pytest.mark.skipif(_NODE is None, reason="Node.js required to evaluate SAMPLES template literals")
def test_all_exemplar_texts_extractable() -> None:
    """Every demo slug must resolve to non-empty text in the SAMPLES object."""
    texts = extract_exemplar_texts()
    assert set(texts) == set(EXEMPLAR_SLUGS)
    for slug in EXEMPLAR_SLUGS:
        assert texts[slug].strip(), f"Empty exemplar text for {slug}"
