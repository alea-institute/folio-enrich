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

from fastapi import APIRouter

from app.api.routes.enrich import load_job_or_404
from app.models.job import Job
from app.services import insights_client
from app.services.proposition.source import stamped_propositions

logger = logging.getLogger(__name__)

router = APIRouter(tags=["insights"])


def _proposition_iris(job: Job) -> dict[str, str]:
    """Map proposition id → content IRI, using the same stamping as export/push.

    ``stamped_propositions`` derives every IRI from ``job_source_uri(job)``, so
    legacy jobs whose stored propositions predate content IRIs get them too and
    the keys match what the export and push paths send to folio-insights.
    """
    return {
        proposition.id: proposition.content_iri
        for proposition in stamped_propositions(job)
        if proposition.content_iri
    }


@router.get("/enrich/{job_id}/insights-status")
async def get_insights_status(job_id: UUID) -> dict[str, Any]:
    job = await load_job_or_404(job_id)
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
        # predate content IRIs) back to the job's IRI by proposition id, and
        # count propositions (not distinct IRIs) in the banner.
        "propositions": by_proposition,
    }


_HEALTH_MESSAGES = {
    "connected": "folio-insights is connected.",
    "not_configured": "folio-insights is not connected.",
    "unreachable": "folio-insights could not be reached.",
    "error": "folio-insights is unavailable.",
}


@router.get("/insights/health")
async def get_insights_health() -> dict[str, Any]:
    # Public and unauthenticated: expose only the connection state and a
    # generic message — no corpus name, shard counts or upstream detail.
    health = await insights_client.fetch_health()
    return {
        "connected": health.connected,
        "state": health.state,
        "message": _HEALTH_MESSAGES.get(health.state, "folio-insights is unavailable."),
    }
