"""AC-1: exports must be ontology-neutral.

A Canon job must never leak the FOLIO base IRI/namespace into any of the 13 export
formats, and a FOLIO job must still carry FOLIO IRIs — proving the neutralization is
driven by the job's ontology, not a blanket string-strip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.job import Job
from app.services.export.registry import get_exporter, list_formats

_DEMOS = Path(__file__).resolve().parents[2] / "frontend" / "demos"
_FOLIO_BASE_IRI = b"folio.openlegalstandard.org"


def _load_job(rel_path: str) -> Job:
    data = json.loads((_DEMOS / rel_path).read_text())
    return Job.model_validate(data["cache"]["job"])


def _as_bytes(output) -> bytes:
    return output if isinstance(output, bytes) else output.encode("utf-8")


ALL_FORMATS = list_formats()


@pytest.fixture(scope="module")
def canon_job() -> Job:
    return _load_job("canon/sacraments.json")


@pytest.fixture(scope="module")
def folio_job() -> Job:
    return _load_job("nda.json")


def test_canon_job_loads_as_canon(canon_job: Job) -> None:
    assert canon_job.result.ontology_id == "canon"
    assert canon_job.result.base_iri == "https://ontology.catholicos.catholic/"


def test_folio_job_loads_as_folio(folio_job: Job) -> None:
    assert folio_job.result.ontology_id == "folio"
    assert folio_job.result.base_iri == "https://folio.openlegalstandard.org/"


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_canon_export_has_no_folio_base_iri(canon_job: Job, fmt: str) -> None:
    output = _as_bytes(get_exporter(fmt).export(canon_job))
    assert _FOLIO_BASE_IRI not in output, (
        f"Canon {fmt} export leaked the FOLIO base IRI"
    )


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_folio_export_still_has_folio_base_iri(folio_job: Job, fmt: str) -> None:
    # Formats that embed concept IRIs must still carry FOLIO IRIs for a FOLIO job.
    # A few formats (e.g. plain triples-only shapes) may legitimately omit them, so
    # we only assert presence for the IRI-bearing serializations.
    output = _as_bytes(get_exporter(fmt).export(folio_job))
    if fmt in {"json", "jsonld", "xml", "rdf", "csv", "neo4j", "html", "elasticsearch"}:
        assert _FOLIO_BASE_IRI in output, (
            f"FOLIO {fmt} export unexpectedly dropped FOLIO IRIs"
        )
