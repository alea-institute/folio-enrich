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


def test_chunker_owned_regions_tile_text():
    para = ("word " * 2500).strip()  # ~12.5 KB, forces whitespace splits
    text = "intro\n\n" + para + "\nline two\n\nend"
    chunks = ce._chunk_text(text)
    assert chunks[0][0] == 0 and chunks[-1][1] == len(text)
    for (_, prev_end, _), (start, _, _) in zip(chunks, chunks[1:]):
        assert prev_end == start  # owned regions tile with no gap or overlap
    for start, end, scan_end in chunks:
        assert end - start <= ce._CITEURL_CHUNK_CHARS
        assert end <= scan_end <= end + ce._CITEURL_LOOKAHEAD


def test_citation_straddling_forced_split_is_found():
    """A blank-line-free paragraph over the chunk limit is force-split at
    whitespace; a citation crossing the cut must still be found once."""
    cite = "42 U.S.C. § 1983"
    head = "x " * ((ce._CITEURL_CHUNK_CHARS - len("42 U.S.C. §")) // 2)
    text = head + cite + " applies." + " more words" * 50
    start = text.index(cite)
    assert start < ce._CITEURL_CHUNK_CHARS < start + len(cite)

    result = _citeurl_only(_normalize_with_citeurl(text, []))
    hits = [i for i in result if "1983" in i.span.text]
    assert len(hits) == 1
    assert (hits[0].span.start, hits[0].span.text) == (start, cite)
    _assert_spans_exact(text, result)


async def test_statute_hits_survive_deduplication():
    """Eyecite emits a bare "§" for Minn. Stat. cites; the longer CiteURL hit must
    replace it so the deduplicator does not fold every statute into one "§"."""
    from app.services.individual.deduplicator import deduplicate

    text = (
        "Under Minn. Stat. § 504B.178 the landlord must return deposits. Later, "
        "Minn. Stat. § 504B.161 covers habitability, and 12 C.F.R. 1026.18 covers disclosure."
    )
    result = deduplicate(await CitationExtractor().extract(text))
    _assert_spans_exact(text, result)

    assert not [i for i in result if i.span.text.strip() == "§"]
    by_form = {(i.normalized_form or i.name): i for i in result}
    for form, host in (
        ("Minn. Stat. § 504B.178", "revisor.mn.gov"),
        ("Minn. Stat. § 504B.161", "revisor.mn.gov"),
        ("12 C.F.R. § 1026.18", "ecfr"),
    ):
        assert form in by_form, list(by_form)
        assert by_form[form].url and host in by_form[form].url


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


def test_known_limit_short_form_lost_across_chunks():
    """Known limit of chunking, not fixed here: CiteURL resolves "Id." and other
    short forms against the previous citation in the same list_cites call. Each
    chunk is a separate call (whole-document calls are superlinearly slow), so an
    "Id." whose antecedent sits in an earlier chunk is not reported. A whole-text
    call would yield "Id. § 1988" as "42 U.S.C. § 1988"."""
    filler = "The parties dispute the lease terms and notice obligations. " * 80
    text = (
        "Relief lies under 42 U.S.C. § 1983.\n\n" + filler + "\n\n" + filler
        + "\n\nId. § 1988 also allows fees."
    )
    assert len(ce._chunk_text(text)) > 1
    result = _citeurl_only(_normalize_with_citeurl(text, []))
    assert [i.span.text for i in result] == ["42 U.S.C. § 1983"]


# ── Health ────────────────────────────────────────────────────────────


async def test_health_detail_reports_citations_ready():
    from app.api.routes.health import health_detail

    result = await health_detail()
    assert result["citations"]["status"] == "ready"
