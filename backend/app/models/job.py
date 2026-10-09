from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from folio_propositions import Proposition, migrate_record
from pydantic import BaseModel, Field, field_validator, model_serializer

from app.models.annotation import Annotation, Individual, PropertyAnnotation, SPOTriple
from app.models.document import DEFAULT_ONTOLOGY, CanonicalText, DocumentInput


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    NORMALIZING = "normalizing"
    ENRICHING = "enriching"
    IDENTIFYING = "identifying"
    RESOLVING = "resolving"
    MATCHING = "matching"
    JUDGING = "judging"
    EXTRACTING_INDIVIDUALS = "extracting_individuals"
    EXTRACTING_PROPERTIES = "extracting_properties"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResult(BaseModel):
    canonical_text: CanonicalText | None = None
    annotations: list[Annotation] = Field(default_factory=list)
    individuals: list[Individual] = Field(default_factory=list)
    properties: list[PropertyAnnotation] = Field(default_factory=list)
    triples: list[SPOTriple] = Field(default_factory=list)
    propositions: list[Proposition] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    # Ontology this result was produced against (stamped by the orchestrator from
    # job.input.ontology). Exporters/clients read these instead of assuming FOLIO.
    # Defaults to "folio"/its identity so legacy jobs deserialize + export cleanly.
    ontology_id: str = DEFAULT_ONTOLOGY
    ontology_name: str = "FOLIO"
    base_iri: str = "https://folio.openlegalstandard.org/"

    @field_validator("propositions", mode="before")
    @classmethod
    def migrate_persisted_propositions(cls, value):
        if not isinstance(value, list):
            return value
        return [
            migrate_record(item) if isinstance(item, dict) else item
            for item in value
        ]


ReviewChoice = Literal["required", "skipped"]
PushChoice = Literal["requested", "not_requested"]
# pending_job: the pipeline has not finished yet; not_required: review skipped.
ReviewStatus = Literal["pending_job", "not_required", "awaiting_review", "completed"]
PushStatus = Literal[
    "not_requested",
    "waiting_for_job",
    "waiting_for_review",
    "pending",
    "pushed",
    "failed",
    "not_configured",
]


class PostJobState(BaseModel):
    """What happens after the pipeline finishes: optional review, optional push.

    The defaults describe a legacy job (persisted before this field existed):
    no review step and no push to folio-insights.
    """

    review: ReviewChoice = "skipped"
    push: PushChoice = "not_requested"
    review_status: ReviewStatus = "not_required"
    review_completed_at: datetime | None = None
    push_status: PushStatus = "not_requested"
    push_attempts: int = 0
    last_push_at: datetime | None = None
    # Sanitized human message; never contains the insights URL or token.
    last_push_error: str | None = None
    # Counts reported by the insights ingest route (created/existing/skipped/refused).
    last_push_report: dict[str, Any] | None = None


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input: DocumentInput | None = None
    result: JobResult = Field(default_factory=JobResult)
    error: str | None = None
    # None = legacy job (no review, no push); set at submission by /enrich.
    post_job: PostJobState | None = None

    @model_serializer(mode="wrap")
    def _omit_unset_post_job(self, handler):
        # Jobs that never chose a post-job flow serialize exactly as before.
        data = handler(self)
        if isinstance(data, dict) and data.get("post_job") is None:
            data.pop("post_job", None)
        return data

    @property
    def ontology(self) -> str:
        """The ontology this job enriches against (None-safe; defaults to folio)."""
        return self.input.ontology if self.input is not None else DEFAULT_ONTOLOGY
