"""Source URIs and content IRIs for proposition cross-document identity.

``proposition_id`` (see :mod:`app.services.proposition.identity`) is the
job-scoped legacy id. ``content_iri`` is the cross-document identity shared
with folio-insights: it is computed from ``(source URI, span text)`` with the
frozen recipe in :mod:`folio_propositions.identity`, so the same span of the
same source carries the same IRI in every job and in folio-insights shards.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from folio_propositions import (
    Proposition,
    content_iri,
    document_source_uri,
    normalize_source_uri,
)

if TYPE_CHECKING:
    from app.models.job import Job

logger = logging.getLogger(__name__)

SOURCE_URI_METADATA_KEY = "proposition_source_uri"
SOURCE_URI_MAX_LENGTH = 2048

_GOLD_MANIFEST = (
    Path(__file__).resolve().parents[3] / "eval" / "gold" / "propositions" / "manifest.json"
)


def validate_source_uri(value: str | None) -> str | None:
    """Validate a caller-supplied source URI (request boundary only)."""

    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source_uri must be a non-empty string")
    if len(value) > SOURCE_URI_MAX_LENGTH:
        raise ValueError(f"source_uri must be at most {SOURCE_URI_MAX_LENGTH} characters")
    if ":" not in value:
        raise ValueError("source_uri must be an absolute URI with a scheme (e.g. https:, urn:)")
    # Reject URIs the shared identity recipe cannot normalize (e.g. an
    # unterminated IPv6 host "http://[::1") here, at the request boundary,
    # instead of failing later inside content-IRI minting.
    try:
        normalize_source_uri(value)
    except ValueError as exc:
        raise ValueError(f"source_uri is not a valid URI: {exc}") from None
    return value


def _job_text(job: Job) -> str | None:
    canonical = job.result.canonical_text
    if canonical is not None and canonical.full_text:
        return canonical.full_text
    if job.input is not None and job.input.content:
        return job.input.content
    return None


def job_source_uri(job: Job) -> str:
    """Return the source URI that content IRIs for ``job`` are minted from.

    Precedence: the caller-supplied ``job.input.source_uri``; the URI the
    proposition stage recorded in ``job.result.metadata`` (so a job keeps the
    identity its propositions were stamped with); the deterministic
    ``document_source_uri`` of the canonical text; and, for a job with no text
    at all, ``urn:uuid:<job id>``.
    """

    supplied = job.input.source_uri if job.input is not None else None
    if supplied and supplied.strip():
        return supplied
    recorded = (job.result.metadata or {}).get(SOURCE_URI_METADATA_KEY)
    if isinstance(recorded, str) and recorded.strip():
        return recorded
    text = _job_text(job)
    if text:
        try:
            return document_source_uri(text)
        except ValueError:
            pass
    return f"urn:uuid:{job.id}"


def proposition_content_iri(source_uri: str, text: str | None) -> str | None:
    """Return the content IRI for ``text``, or ``None`` when it has no content."""

    if text is None:
        return None
    try:
        return content_iri(source_uri, text)
    except ValueError:
        return None


def stamped_propositions(job: Job, source_uri: str | None = None) -> list[Proposition]:
    """Return copies of the job's propositions with ``content_iri`` computed.

    Used on read (export, lookup) so older persisted jobs whose propositions
    predate content IRIs gain them lazily; the stored job is not rewritten.
    The IRI is always recomputed from the job's source URI so the result
    satisfies the ``PropositionDocumentRecord`` cross-check.
    """

    uri = source_uri or job_source_uri(job)
    stamped: list[Proposition] = []
    for proposition in job.result.propositions:
        iri = proposition_content_iri(uri, proposition.text)
        stamped.append(proposition.model_copy(update={"content_iri": iri}))
    return stamped


def job_document_id(job: Job) -> str:
    """Return the gold ``document_id`` recorded for this job, else ``str(job.id)``."""

    explicit = (job.result.metadata or {}).get("gold_document_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    try:
        manifest = json.loads(_GOLD_MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return str(job.id)
    except (OSError, ValueError):
        logger.warning("Cannot read gold manifest for document_id lookup", exc_info=True)
        return str(job.id)
    job_id = str(job.id)
    for entry in manifest.get("opinions", []) if isinstance(manifest, dict) else []:
        if isinstance(entry, dict) and entry.get("job_id") == job_id and entry.get("document_id"):
            return str(entry["document_id"])
    return job_id
