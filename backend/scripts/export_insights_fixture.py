"""Write a ``propositions`` export for one text file, for folio-insights fixtures.

Runs only the deterministic proposition path (spaCy dependency parse plus the
proposition lexicon; no LLM, no FOLIO concept matching) over a plain-text
document and writes the shared-schema ``PropositionDocumentRecord`` JSON that
``GET /enrich/{job_id}/export?format=propositions`` would return.

The job id defaults to a uuid5 of the source URI, so re-running the command on
the same input reproduces the file byte for byte (the generator version comes
from the installed folio-enrich package metadata).

Produce the folio-insights end-to-end fixture (run from ``backend/``)::

    .venv/bin/python scripts/export_insights_fixture.py \\
        eval/gold/propositions/palsgraf-248-ny-339.txt \\
        --source-uri https://example.org/opinions/palsgraf-248-ny-339 \\
        --document-id palsgraf-248-ny-339 \\
        --output /path/to/folio-insights/tests/fixtures/palsgraf.propositions.json

Without ``--source-uri`` the record uses the deterministic
``urn:sha256:<digest of the normalized text>`` source URI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_job(text: str, *, source_uri: str | None, job_id: UUID | None,
              document_id: str | None, filename: str | None):
    from folio_propositions import document_source_uri

    from app.models.document import CanonicalText, DocumentInput
    from app.models.job import Job, JobResult, JobStatus
    from app.services.proposition.source import validate_source_uri

    validate_source_uri(source_uri)
    identity_uri = source_uri or document_source_uri(text)
    job = Job(
        id=job_id or uuid5(NAMESPACE_URL, f"folio-enrich:insights-fixture:{identity_uri}"),
        status=JobStatus.COMPLETED,
        input=DocumentInput(content=text, filename=filename, source_uri=source_uri),
        result=JobResult(canonical_text=CanonicalText(full_text=text)),
    )
    if document_id:
        job.result.metadata["gold_document_id"] = document_id
    return job


async def extract(job):
    from app.config import settings
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    previous = settings.proposition_extraction_enabled
    settings.proposition_extraction_enabled = True
    try:
        return await EarlyPropositionStage(llm=None).execute(job)
    finally:
        settings.proposition_extraction_enabled = previous


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text_file", type=Path, help="UTF-8 plain-text document")
    parser.add_argument("--output", "-o", type=Path, required=True,
                        help="where to write the propositions export JSON")
    parser.add_argument("--source-uri", default=None,
                        help="canonical source URI (default: urn:sha256 of the text)")
    parser.add_argument("--document-id", default=None,
                        help="record document_id (default: the job id)")
    parser.add_argument("--job-id", type=UUID, default=None,
                        help="job id (default: uuid5 of the source URI)")
    args = parser.parse_args(argv)

    from folio_propositions import PropositionDocumentRecord

    from app.services.export.registry import get_exporter

    text = args.text_file.read_bytes().decode("utf-8")
    job = build_job(text, source_uri=args.source_uri, job_id=args.job_id,
                    document_id=args.document_id, filename=args.text_file.name)
    job = asyncio.run(extract(job))
    content = get_exporter("propositions").export(job)
    record = PropositionDocumentRecord.model_validate_json(content)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"wrote {len(record.propositions)} propositions "
          f"(source_uri={record.source_uri}) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
