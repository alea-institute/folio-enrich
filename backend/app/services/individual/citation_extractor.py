"""Pass 1 — Library-based legal citation extraction using Eyecite + CiteURL."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from uuid import uuid4

from app.models.annotation import Individual, IndividualClassLink, Span, StageEvent

logger = logging.getLogger(__name__)

# Citation type → FOLIO class label mapping
_CITATION_TYPE_MAP: dict[str, str] = {
    "FullCaseCitation": "Caselaw",
    "ShortCaseCitation": "Caselaw",
    "FullLawCitation": "Statute",
    "FullJournalCitation": "Legal Scholarship",
    "SupraCitation": "Caselaw",
    "IdCitation": "Caselaw",
    "UnknownCitation": "Legal Citation",
}


def _eyecite_type_name(citation) -> str:
    """Get the class name of an eyecite citation object."""
    return type(citation).__name__


def _extract_with_eyecite(text: str) -> list[Individual]:
    """Run eyecite extraction synchronously. Returns Individual objects."""
    try:
        from eyecite import get_citations
    except ImportError:
        logger.warning("eyecite not installed — skipping citation extraction")
        return []

    try:
        citations = get_citations(text)
    except Exception:
        logger.exception("eyecite extraction failed")
        return []

    individuals: list[Individual] = []
    for cite in citations:
        cite_type = _eyecite_type_name(cite)

        # Get matched text and span
        matched_text = cite.matched_text()
        if not matched_text:
            continue

        # Find span in original text
        token = cite.token
        start = token.start if hasattr(token, "start") else text.find(matched_text)
        end = token.end if hasattr(token, "end") else start + len(matched_text)

        if start < 0:
            continue

        # Determine FOLIO class label from citation type
        folio_label = _CITATION_TYPE_MAP.get(cite_type, "Legal Citation")

        # Build normalized form using eyecite's clean output methods
        if hasattr(cite, "corrected_citation_full"):
            full = cite.corrected_citation_full()
            normalized = full if full and full != matched_text else None
        elif hasattr(cite, "corrected_citation"):
            corr = cite.corrected_citation()
            normalized = corr if corr and corr != matched_text else None
        else:
            normalized = None

        individual = Individual(
            id=str(uuid4()),
            name=matched_text.strip(),
            mention_text=matched_text,
            individual_type="legal_citation",
            span=Span(start=start, end=end, text=matched_text),
            class_links=[
                IndividualClassLink(
                    folio_label=folio_label,
                    relationship="instance_of",
                    confidence=0.92,
                )
            ],
            confidence=0.92,
            source="eyecite",
            normalized_form=normalized,
            lineage=[
                StageEvent(
                    stage="individual_extraction",
                    action="created",
                    detail=f"eyecite: {cite_type}",
                    confidence=0.92,
                )
            ],
        )
        individuals.append(individual)

    return individuals


# CiteURL's list_cites cost grows superlinearly with input length (~16 s for a
# single 222 KB call vs <1 s as section-sized calls), so extraction runs per chunk.
_CITEURL_CHUNK_CHARS = 8000

# Cached CiteURL state: the Citator is slow to build, so construct it once.
# _citeurl_state is None until the first attempt; afterwards it holds the status
# dict reported by citeurl_status() (and _citator holds the instance when ready).
_citator = None
_citeurl_state: dict | None = None


def _get_citator():
    """Return the shared CiteURL Citator, or None if citeurl is unavailable."""
    global _citator, _citeurl_state
    if _citeurl_state is None:
        try:
            from citeurl import Citator

            _citator = Citator()
            _citeurl_state = {"status": "ready"}
        except Exception as e:  # ImportError (e.g. missing 'markdown') or init failure
            _citator = None
            _citeurl_state = {
                "status": "error",
                "message": f"{type(e).__name__}: {e}",
            }
    return _citator


def citeurl_status() -> dict:
    """Report whether CiteURL imports and builds a Citator (for /health/detail)."""
    _get_citator()
    assert _citeurl_state is not None
    return dict(_citeurl_state)


def _reset_citeurl_cache() -> None:
    """Forget the cached Citator/status (used by tests)."""
    global _citator, _citeurl_state
    _citator = None
    _citeurl_state = None


def _split_long(text: str, offset: int, limit: int) -> list[tuple[int, str]]:
    """Split an over-long paragraph at newlines, then at whitespace near the limit."""
    pieces: list[tuple[int, str]] = []
    pos = 0
    n = len(text)
    while n - pos > limit:
        window = text[pos:pos + limit]
        # Prefer the last single newline, then the last whitespace, in the window
        cut = window.rfind("\n")
        if cut <= 0:
            cut = max(window.rfind(" "), window.rfind("\t"))
        if cut <= 0:
            cut = limit  # no whitespace at all — hard split
        pieces.append((offset + pos, text[pos:pos + cut]))
        pos += cut
    if pos < n:
        pieces.append((offset + pos, text[pos:]))
    return pieces


def _chunk_text(text: str, limit: int = _CITEURL_CHUNK_CHARS) -> list[tuple[int, str]]:
    """Split text into (offset, chunk) pairs at paragraph boundaries.

    Paragraphs (separated by blank lines) are grouped up to ``limit`` chars;
    a single paragraph over the limit is split further by ``_split_long``.
    Chunks never overlap, so offsets map chunk spans back to ``text`` exactly.
    """
    # Paragraph boundaries: positions right after each "\n\n" run
    paragraphs: list[tuple[int, str]] = []
    pos = 0
    while pos < len(text):
        idx = text.find("\n\n", pos)
        if idx < 0:
            paragraphs.append((pos, text[pos:]))
            break
        # Swallow the full run of newlines into the current paragraph
        stop = idx
        while stop < len(text) and text[stop] == "\n":
            stop += 1
        paragraphs.append((pos, text[pos:stop]))
        pos = stop

    chunks: list[tuple[int, str]] = []
    cur_start: int | None = None
    cur_len = 0
    for p_start, para in paragraphs:
        if len(para) > limit:
            if cur_start is not None:
                chunks.append((cur_start, text[cur_start:cur_start + cur_len]))
                cur_start, cur_len = None, 0
            chunks.extend(_split_long(para, p_start, limit))
            continue
        if cur_start is not None and cur_len + len(para) > limit:
            chunks.append((cur_start, text[cur_start:cur_start + cur_len]))
            cur_start, cur_len = None, 0
        if cur_start is None:
            cur_start = p_start
        cur_len += len(para)
    if cur_start is not None:
        chunks.append((cur_start, text[cur_start:cur_start + cur_len]))
    return chunks


def _normalize_with_citeurl(text: str, individuals: list[Individual]) -> list[Individual]:
    """Run CiteURL normalization on existing individuals + find additional citations."""
    citator = _get_citator()
    if citator is None:
        # Loud failure: without CiteURL, statute/regulation citations (Minn. Stat.,
        # C.F.R., U.S.C.) are never extracted. Eyecite results still flow through.
        logger.error(
            "CiteURL unavailable (%s) — statute/regulation citation extraction is "
            "DEGRADED; returning eyecite citations only",
            (_citeurl_state or {}).get("message", "unknown error"),
        )
        return individuals

    # Try to normalize existing eyecite individuals
    for ind in individuals:
        try:
            cite = citator.cite(ind.mention_text)
            if cite:
                if cite.URL:
                    ind.url = cite.URL
                # Citation.name is CiteURL's canonical form; str(cite) is the matched text
                normalized = cite.name
                if normalized and normalized != ind.mention_text:
                    ind.normalized_form = normalized
        except Exception:
            pass  # CiteURL couldn't parse this particular citation

    # Also run CiteURL's own extraction for anything eyecite missed, per chunk
    existing_spans = [(ind.span.start, ind.span.end) for ind in individuals]

    def _covered(start: int, end: int) -> bool:
        # Skip only when an existing span contains this one and is at least as long.
        # Eyecite's FullLawCitation often matches just "§"; CiteURL's fuller span wins.
        return any(s <= start and end <= e for s, e in existing_spans)

    extra: list[Individual] = []
    for offset, chunk in _chunk_text(text):
        if not chunk.strip():
            continue
        try:
            citeurl_citations = citator.list_cites(chunk)
        except Exception:
            logger.debug("CiteURL list_cites failed on chunk at %d", offset, exc_info=True)
            continue

        for cite in citeurl_citations:
            try:
                start = offset + cite.span[0]
                end = offset + cite.span[1]
                # CiteURL sometimes includes surrounding whitespace (e.g. " 56.01")
                while start < end and text[start].isspace():
                    start += 1
                while end > start and text[end - 1].isspace():
                    end -= 1
                if start >= end or _covered(start, end):
                    continue

                matched = text[start:end]
                url = cite.URL
                normalized = cite.name if cite.name and cite.name != matched else None

                individual = Individual(
                    id=str(uuid4()),
                    name=matched,
                    mention_text=matched,
                    individual_type="legal_citation",
                    span=Span(start=start, end=end, text=matched),
                    class_links=[
                        IndividualClassLink(
                            folio_label="Legal Citation",
                            relationship="instance_of",
                            confidence=0.90,
                        )
                    ],
                    confidence=0.90,
                    source="citeurl",
                    normalized_form=normalized,
                    url=url,
                    lineage=[
                        StageEvent(
                            stage="individual_extraction",
                            action="created",
                            detail="citeurl: additional citation",
                            confidence=0.90,
                        )
                    ],
                )
                extra.append(individual)
                existing_spans.append((start, end))
            except Exception:
                logger.debug("Skipping unparseable CiteURL citation", exc_info=True)
                continue

    return individuals + extra


class CitationExtractor:
    """Extracts legal citations using Eyecite + CiteURL."""

    async def extract(self, text: str) -> list[Individual]:
        """Extract citations from text. Runs sync libraries in executor."""
        loop = asyncio.get_event_loop()

        # Run eyecite in executor (sync library)
        individuals = await loop.run_in_executor(
            None, partial(_extract_with_eyecite, text)
        )

        # Run citeurl normalization + additional extraction in executor
        individuals = await loop.run_in_executor(
            None, partial(_normalize_with_citeurl, text, individuals)
        )

        logger.info("Citation extraction found %d citations", len(individuals))
        return individuals
