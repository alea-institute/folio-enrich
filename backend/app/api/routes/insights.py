"""folio-insights corpus status for a job's propositions.

Read-only bridge: the browser asks folio-enrich, folio-enrich asks the
configured folio-insights instance. The insights base URL and bearer token stay
server-side; responses carry only the typed state, a human message, the corpus
name and per-IRI results.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.routes import enrich as enrich_routes
from app.models.job import Job
from app.services import insights_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["insights"])


async def _load_job(job_id: UUID) -> Job:
    # Same access check as GET /enrich/{job_id}: the job id is the capability;
    # an unknown job is a 404. Resolved through the enrich module at call time
    # so both routes always share one job store.
    job = await enrich_routes._job_store.load(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _fallback_iri_factory(job: Job):
    """Return a callable computing content IRIs for legacy propositions, or None.

    Old jobs persisted before content IRIs were stamped lack ``content_iri``.
    When the job-source helper exists, derive the IRI the same way the
    extractor does: ``content_iri(job_source_uri(job), proposition.text)``.
    """
    try:
        from folio_propositions import content_iri
        from app.services.proposition.source import job_source_uri
    except ImportError:
        return None
    try:
        source_uri = job_source_uri(job)
    except Exception:  # noqa: BLE001 — a legacy job without text simply has no fallback
        logger.debug("job_source_uri unavailable for job %s", job.id, exc_info=True)
        return None
    if not source_uri:
        return None

    def compute(text: str) -> str | None:
        try:
            return content_iri(source_uri, text)
        except Exception:  # noqa: BLE001
            return None

    return compute


def _proposition_iris(job: Job) -> dict[str, str]:
    """Map proposition id → content IRI for the job's propositions."""
    propositions = job.result.propositions if job.result else []
    mapping: dict[str, str] = {}
    fallback = None
    fallback_resolved = False
    for proposition in propositions:
        iri = getattr(proposition, "content_iri", None)
        if not iri and proposition.text:
            if not fallback_resolved:
                fallback = _fallback_iri_factory(job)
                fallback_resolved = True
            iri = fallback(proposition.text) if fallback else None
        if iri:
            mapping[proposition.id] = iri
    return mapping


@router.get("/enrich/{job_id}/insights-status")
async def get_insights_status(job_id: UUID) -> dict[str, Any]:
    job = await _load_job(job_id)
    by_proposition = _proposition_iris(job)
    iris = list(dict.fromkeys(by_proposition.values()))
    status = await insights_client.fetch_status(iris)
    return {
        "connected": status.connected,
        "state": status.state,
        "message": status.message,
        "corpus": status.corpus,
        "insights_version": status.insights_version,
        "results": status.results if status.connected else {},
        # Lets the UI resolve gold-session copies of a proposition (which may
        # predate content IRIs) back to the job's IRI by proposition id.
        "propositions": by_proposition,
    }


@router.get("/insights/health")
async def get_insights_health() -> dict[str, Any]:
    health = await insights_client.fetch_health()
    return {
        "connected": health.connected,
        "state": health.state,
        "message": health.message,
        "corpus": health.corpus,
        "shards": health.shards,
    }
