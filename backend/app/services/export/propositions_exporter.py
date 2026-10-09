"""Shared-schema proposition exports consumed by folio-insights.

``propositions`` emits one ``folio_propositions.PropositionDocumentRecord``
(the current shared schema version) as JSON. ``propositions-ndjson`` emits the
same record as a streaming-friendly NDJSON: a ``header`` line carrying the
record without its propositions, then one flat ``proposition`` line per
proposition (``{"record_type": "proposition", **proposition}``). folio-insights'
NDJSON parser pops ``record_type`` and validates the remainder as a
``folio_propositions.Proposition``, so lines must not nest the proposition.

Every proposition carries ``content_iri`` computed from the record's
``source_uri``, so the record passes the library's IRI cross-check. Older jobs
whose stored propositions predate content IRIs are stamped on read.

The export route's ``include_dismissed`` flag filters rejected *annotations*
only; propositions have no dismissed state (their disposition is part of the
shared schema), so all job propositions are exported.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import metadata
from typing import Any

from folio_propositions import GeneratorInfo, PropositionDocumentRecord

from app.models.job import Job
from app.services.export.base import ExporterBase
from app.services.proposition.source import (
    job_document_id,
    job_source_uri,
    stamped_propositions,
)


@lru_cache(maxsize=1)
def app_version() -> str:
    try:
        return metadata.version("folio-enrich")
    except metadata.PackageNotFoundError:
        return "unknown"


def build_proposition_record(job: Job) -> PropositionDocumentRecord:
    """Build the validated shared-schema record for ``job``."""

    source_uri = job_source_uri(job)
    document_metadata: dict[str, Any] = {
        "job_id": str(job.id),
        "proposition_lexicon_version": (job.result.metadata or {}).get(
            "proposition_lexicon_version"
        ),
        "filename": job.input.filename if job.input is not None else None,
    }
    document_metadata = {k: v for k, v in document_metadata.items() if v is not None}
    return PropositionDocumentRecord(
        document_id=job_document_id(job),
        source_uri=source_uri,
        propositions=stamped_propositions(job, source_uri),
        generator=GeneratorInfo(tool="folio-enrich", version=app_version()),
        document_metadata=document_metadata,
    )


class PropositionsExporter(ExporterBase):
    @property
    def format_name(self) -> str:
        return "propositions"

    @property
    def content_type(self) -> str:
        return "application/json"

    def export(self, job: Job) -> str:
        record = build_proposition_record(job)
        return json.dumps(record.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


class PropositionsNDJSONExporter(ExporterBase):
    @property
    def format_name(self) -> str:
        return "propositions-ndjson"

    @property
    def content_type(self) -> str:
        return "application/x-ndjson"

    def export(self, job: Job) -> str:
        payload = build_proposition_record(job).model_dump(mode="json")
        propositions = payload.pop("propositions")
        lines = [json.dumps({"record_type": "header", **payload}, ensure_ascii=False)]
        lines.extend(
            json.dumps({"record_type": "proposition", **p}, ensure_ascii=False)
            for p in propositions
        )
        return "\n".join(lines) + "\n"
