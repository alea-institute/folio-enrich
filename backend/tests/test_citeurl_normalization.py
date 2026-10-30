"""Regression tests for CiteURL citation normalization.

citeurl 12.x imports the undeclared `markdown` package; when it was missing the
extractor silently skipped every statute/regulation citation. These tests guard
the import, the canonical normalized form (Citation.name), span accuracy,
chunked extraction, and the loud degraded-mode path.
"""
from __future__ import annotations

import logging
import sys
import time

import pytest

from app.models.annotation import Individual, IndividualClassLink, Span
from app.services.individual import citation_extractor as ce
from app.services.individual.citation_extractor import (
    CitationExtractor,
    _normalize_with_citeurl,
    citeurl_status,
)

LOGGER_NAME = "app.services.individual.citation_extractor"


def _citeurl_only(individuals: list[Individual]) -> list[Individual]:
    return [i for i in individuals if i.source == "citeurl"]


def _assert_spans_exact(text: str, individuals: list[Individual]) -> None:
    for ind in individuals:
        assert text[ind.span.start:ind.span.end] == ind.span.text
        assert ind.span.text == ind.mention_text


# ── Import / status guard ─────────────────────────────────────────────


def test_citeurl_imports_and_status_ready():
    import citeurl  # noqa: F401 — fails if `markdown` (or citeurl) is missing

    assert citeurl_status()["status"] == "ready"


# ── Normalization ─────────────────────────────────────────────────────


async def test_minn_stat_and_cfr_normalize_with_urls():
    text = "Under Minn. Stat. § 504B.178 and 12 C.F.R. 1026.18, the lender must disclose."
    individuals = await CitationExtractor().extract(text)
    _assert_spans_exact(text, individuals)

    def forms(ind: Individual) -> str:
        return ind.normalized_form or ind.name

    minn = [i for i in individuals if "Minn. Stat. § 504B.178" in forms(i)]
    assert minn, [forms(i) for i in individuals]
    assert any(i.url and "revisor.mn.gov" in i.url for i in minn)

    cfr = [i for i in individuals if "12 C.F.R. § 1026.18" in forms(i)]
    assert cfr, [forms(i) for i in individuals]
    assert any(i.url and "ecfr" in i.url for i in cfr)


async def test_normal_input_does_not_hit_degraded_path(caplog):
    text = "Under Minn. Stat. § 504B.178 and 12 C.F.R. 1026.18, the lender must disclose."
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        await CitationExtractor().extract(text)
    errors = [r for r in caplog.records if r.name == LOGGER_NAME and r.levelno >= logging.ERROR]
    assert errors == []


def test_missing_citeurl_logs_error_and_returns_eyecite_unchanged(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "citeurl", None)  # makes `import citeurl` raise
    ce._reset_citeurl_cache()
    try:
        eyecite_ind = Individual(
            name="410 U.S. 113",
            mention_text="410 U.S. 113",
            individual_type="legal_citation",
            span=Span(start=0, end=12, text="410 U.S. 113"),
            class_links=[IndividualClassLink(folio_label="Caselaw")],
            source="eyecite",
        )
        before = eyecite_ind.model_dump()
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            result = _normalize_with_citeurl("410 U.S. 113 and Minn. Stat. § 504B.178", [eyecite_ind])

        assert result == [eyecite_ind]
        assert result[0].model_dump() == before
        errors = [r for r in caplog.records if r.name == LOGGER_NAME and r.levelno == logging.ERROR]
        assert errors and "DEGRADED" in errors[0].getMessage()
        assert citeurl_status()["status"] == "error"
    finally:
        monkeypatch.delitem(sys.modules, "citeurl", raising=False)
        ce._reset_citeurl_cache()
    assert citeurl_status()["status"] == "ready"


# ── Spans ─────────────────────────────────────────────────────────────


def test_repeated_citation_gets_distinct_spans():
    text = (
        "The claim arises under 42 U.S.C. § 1983 as pleaded.\n\n"
        "Again, 42 U.S.C. § 1983 supplies the cause of action."
    )
    result = _citeurl_only(_normalize_with_citeurl(text, []))
    hits = [i for i in result if "1983" in i.span.text]
    assert len(hits) == 2
    starts = sorted(i.span.start for i in hits)
    first = text.index("42 U.S.C. § 1983")
    second = text.index("42 U.S.C. § 1983", first + 1)
    assert starts == [first, second]
    _assert_spans_exact(text, result)


def test_chunked_extraction_long_document():
    filler = (
        "The parties dispute the meaning of the lease and the obligations it imposes "
        "on each side, including notice, cure periods, and the return of deposits. "
    ) * 10
    paragraphs = [filler for _ in range(60)]
    paragraphs[0] = filler + "See Minn. Stat. § 504B.178 for deposit rules."
    paragraphs[30] = filler + "Disclosure follows 12 C.F.R. 1026.18 here."
    paragraphs[59] = filler + "Relief lies under 42 U.S.C. § 1983 finally."
    text = "\n\n".join(paragraphs)
    assert len(text) > 50_000

    t0 = time.monotonic()
    result = _citeurl_only(_normalize_with_citeurl(text, []))
    elapsed = time.monotonic() - t0
    assert elapsed < 10, f"citeurl extraction took {elapsed:.1f}s"

    _assert_spans_exact(text, result)
    found = {i.span.text for i in result}
    for cite in ("Minn. Stat. § 504B.178", "12 C.F.R. 1026.18", "42 U.S.C. § 1983"):
        assert cite in found, found
        match = next(i for i in result if i.span.text == cite)
        assert match.span.start == text.index(cite)


def test_chunker_covers_text_without_overlap():
    para = ("word " * 2500).strip()  # ~12.5 KB, forces whitespace hard-split
    text = "intro\n\n" + para + "\nline two\n\nend"
    chunks = ce._chunk_text(text)
    assert "".join(c for _, c in chunks) == text
    for offset, chunk in chunks:
        assert text[offset:offset + len(chunk)] == chunk
        assert len(chunk) <= ce._CITEURL_CHUNK_CHARS


# ── Known CiteURL limits (documented, not fixed here) ─────────────────


def test_known_limit_drops_subdivision():
    """Known citeurl limit, not fixed here: 'subd. 3(a)' is dropped from the cite."""
    text = "Minn. Stat. § 504B.178, subd. 3(a)"
    result = _citeurl_only(_normalize_with_citeurl(text, []))
    assert len(result) == 1
    assert result[0].span.text == "Minn. Stat. § 504B.178"
    assert (result[0].normalized_form or result[0].name) == "Minn. Stat. § 504B.178"
    assert "subd" not in (result[0].normalized_form or result[0].name)


def test_known_limit_collapses_section_range():
    """Known citeurl limit, not fixed here: a §§ range collapses to the first section."""
    text = "Minn. Stat. §§ 504B.178-.185"
    result = _citeurl_only(_normalize_with_citeurl(text, []))
    assert len(result) == 1
    assert result[0].span.text == "Minn. Stat. §§ 504B.178"
    assert result[0].normalized_form == "Minn. Stat. § 504B.178"


def test_known_limit_reads_civ_p_rule_as_statute():
    """Known citeurl limit, not fixed here: 'Minn. R. Civ. P. 56.01' after a
    Minn. Stat. cite is read as a short-form 'Minn. Stat. § 56.01'."""
    text = "Minn. Stat. § 504B.178 applies. Then Minn. R. Civ. P. 56.01 governs."
    result = _citeurl_only(_normalize_with_citeurl(text, []))
    _assert_spans_exact(text, result)
    rule = [i for i in result if i.normalized_form == "Minn. Stat. § 56.01"]
    assert len(rule) == 1
    # Leading whitespace in CiteURL's span (" 56.01") is stripped
    assert rule[0].span.text == "56.01"


# ── Health ────────────────────────────────────────────────────────────


async def test_health_detail_reports_citations_ready():
    from app.api.routes.health import health_detail

    result = await health_detail()
    assert result["citations"]["status"] == "ready"
