from __future__ import annotations

import abc
import json

from app.models.annotation import UNION_CONCEPT_FIELDS
from app.models.job import Job


def union_fields(concept) -> dict:
    return {k: v for k, v in concept.model_dump().items() if k in UNION_CONCEPT_FIELDS}


def union_cells(concept) -> list:
    cells = []
    for key in UNION_CONCEPT_FIELDS:
        value = getattr(concept, key)
        cells.append(json.dumps(value) if isinstance(value, list) else value)
    return cells


class ExporterBase(abc.ABC):
    @property
    @abc.abstractmethod
    def format_name(self) -> str: ...

    @property
    @abc.abstractmethod
    def content_type(self) -> str: ...

    @abc.abstractmethod
    def export(self, job: Job) -> str | bytes:
        """Export job results to the target format."""
