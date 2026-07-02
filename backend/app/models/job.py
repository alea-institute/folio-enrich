from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

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
    metadata: dict = Field(default_factory=dict)
    # Ontology this result was produced against (stamped by the orchestrator from
    # job.input.ontology). Exporters/clients read these instead of assuming FOLIO.
    # Defaults to "folio"/its identity so legacy jobs deserialize + export cleanly.
    ontology_id: str = DEFAULT_ONTOLOGY
    ontology_name: str = "FOLIO"
    base_iri: str = "https://folio.openlegalstandard.org/"


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input: DocumentInput | None = None
    result: JobResult = Field(default_factory=JobResult)
    error: str | None = None

    @property
    def ontology(self) -> str:
        """The ontology this job enriches against (None-safe; defaults to folio)."""
        return self.input.ontology if self.input is not None else DEFAULT_ONTOLOGY
