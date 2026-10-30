from __future__ import annotations

import io

from app.models.job import Job
from app.services.export.base import ExporterBase


class ParquetExporter(ExporterBase):
    @property
    def format_name(self) -> str:
        return "parquet"

    @property
    def content_type(self) -> str:
        return "application/octet-stream"

    def export(self, job: Job) -> bytes:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError(
                "pyarrow is not available on this platform. "
                "Parquet export is not supported on Windows ARM64."
            )

        # One Parquet file holds every record kind. Writing a table per kind into
        # the same buffer concatenates several files, which no reader can open, so
        # emit a single table tagged by ``record_type`` over the union of columns
        # (null where a column does not apply). Concept rows keep their original
        # column names so concept-only consumers still find them.
        schema = pa.schema([
            ("record_type", pa.string()),
            ("job_id", pa.string()),
            ("span_start", pa.int64()),
            ("span_end", pa.int64()),
            ("span_text", pa.string()),
            ("concept_text", pa.string()),
            ("folio_iri", pa.string()),
            ("folio_label", pa.string()),
            ("branch", pa.string()),
            ("confidence", pa.float64()),
            ("source", pa.string()),
            ("document_type", pa.string()),
            ("individual_id", pa.string()),
            ("name", pa.string()),
            ("mention_text", pa.string()),
            ("individual_type", pa.string()),
            ("class_labels", pa.string()),
            ("class_iris", pa.string()),
            ("normalized_form", pa.string()),
            ("url", pa.string()),
            ("property_id", pa.string()),
            ("property_text", pa.string()),
            ("match_type", pa.string()),
            ("domain_iris", pa.string()),
            ("range_iris", pa.string()),
            ("triple_id", pa.string()),
            ("subject", pa.string()),
            ("predicate", pa.string()),
            ("object", pa.string()),
            ("sentence", pa.string()),
            ("voice", pa.string()),
            ("has_folio_link", pa.bool_()),
            ("subject_iri", pa.string()),
            ("object_iri", pa.string()),
            ("predicate_iri", pa.string()),
        ])
        document_type = str(job.result.metadata.get("document_type", "") or "")

        rows = []
        for ann in job.result.annotations:
            for concept in ann.concepts:
                rows.append({
                    "record_type": "concept",
                    "job_id": str(job.id),
                    "span_start": ann.span.start,
                    "span_end": ann.span.end,
                    "span_text": ann.span.text,
                    "concept_text": concept.concept_text,
                    "folio_iri": concept.folio_iri or "",
                    "folio_label": concept.folio_label or "",
                    "branch": concept.branches[0] if concept.branches else "",
                    "confidence": concept.confidence,
                    "source": concept.source,
                    "document_type": document_type,
                })

        for ind in job.result.individuals:
            class_labels = "; ".join(cl.folio_label or "" for cl in ind.class_links)
            class_iris = "; ".join(cl.folio_iri or "" for cl in ind.class_links)
            rows.append({
                "record_type": "individual",
                "job_id": str(job.id),
                "individual_id": ind.id,
                "name": ind.name,
                "mention_text": ind.mention_text,
                "individual_type": ind.individual_type,
                "span_start": ind.span.start,
                "span_end": ind.span.end,
                "class_labels": class_labels,
                "class_iris": class_iris,
                "confidence": ind.confidence,
                "source": ind.source,
                "normalized_form": ind.normalized_form or "",
                "url": ind.url or "",
            })

        for prop in job.result.properties:
            rows.append({
                "record_type": "property",
                "job_id": str(job.id),
                "property_id": prop.id,
                "property_text": prop.property_text,
                "folio_iri": prop.folio_iri or "",
                "folio_label": prop.folio_label or "",
                "span_start": prop.span.start,
                "span_end": prop.span.end,
                "confidence": prop.confidence,
                "source": prop.source,
                "match_type": prop.match_type or "",
                "domain_iris": "; ".join(prop.domain_iris),
                "range_iris": "; ".join(prop.range_iris),
            })

        for t in job.result.triples:
            subj_iri = next((l.folio_iri for l in t.subject_links if l.folio_iri), "")
            obj_iri = next((l.folio_iri for l in t.object_links if l.folio_iri), "")
            pred_iri = next((l.folio_iri for l in t.predicate_links if l.folio_iri), "")
            rows.append({
                "record_type": "triple",
                "job_id": str(job.id),
                "triple_id": t.id,
                "subject": t.subject,
                "predicate": t.predicate,
                "object": t.object,
                "sentence": t.sentence,
                "voice": t.voice,
                "has_folio_link": bool(t.subject_links or t.object_links or t.predicate_links),
                "subject_iri": subj_iri,
                "object_iri": obj_iri,
                "predicate_iri": pred_iri,
                "confidence": t.confidence,
                "source": t.source,
            })

        table = pa.Table.from_pylist(rows, schema=schema)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        return buf.getvalue()
