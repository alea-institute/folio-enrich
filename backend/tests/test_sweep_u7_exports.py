"""Regression tests for the U7 export sweep: Parquet validity, control
characters in XML/Excel/HTML, HTML span offsets, and brat line framing."""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pytest

from app.models.annotation import (
    Annotation,
    ConceptMatch,
    Individual,
    IndividualClassLink,
    PropertyAnnotation,
    Span,
    SPOTriple,
    TripleLink,
)
from app.models.job import Job
from app.services.export.brat_exporter import BratExporter
from app.services.export.excel_exporter import ExcelExporter
from app.services.export.html_exporter import HTMLExporter
from app.services.export.parquet_exporter import ParquetExporter
from app.services.export.registry import get_exporter, list_formats
from app.services.export.sanitize import strip_xml_illegal
from app.services.export.xml_exporter import XMLExporter

from tests.helpers import make_job

CTRL = "\x02\x08\x16\x1b"
FOLIO = "https://folio.openlegalstandard.org/"


def _rich_job(noise: str = "") -> Job:
    """A job with concepts, individuals, properties and triples.

    ``noise`` is spliced into every free-text field (not the document text, so
    spans stay valid) to mimic old stored jobs that kept PDF control chars.
    """
    text = "The court & <counsel> granted the motion in Smith v. Jones."
    c = text.index("court")
    m = text.index("motion")
    g = text.index("granted")
    s = text.index("Smith v. Jones")
    annotations = [
        Annotation(
            span=Span(start=c, end=c + 5, text="court" + noise),
            concepts=[ConceptMatch(
                concept_text="court" + noise, folio_iri=FOLIO + "R1",
                folio_label="Court" + noise, folio_definition="A tribunal" + noise,
                branches=["Actor / Player"], confidence=0.95, source="llm",
            )],
        ),
        Annotation(
            span=Span(start=m, end=m + 6, text="motion"),
            concepts=[
                ConceptMatch(concept_text="motion", folio_iri=FOLIO + "R2",
                             folio_label="Motion", branches=["Document / Artifact"],
                             confidence=0.8, source="entity_ruler"),
                ConceptMatch(concept_text="motion", folio_iri=FOLIO + "R3",
                             folio_label="Motion (Event)", branches=["Event"],
                             confidence=0.5, source="llm"),
            ],
        ),
    ]
    individuals = [Individual(
        name="Smith v. Jones" + noise, mention_text="Smith v. Jones" + noise,
        individual_type="legal_citation", span=Span(start=s, end=s + 14, text="Smith v. Jones"),
        class_links=[IndividualClassLink(folio_iri=FOLIO + "R4", folio_label="Case" + noise,
                                         confidence=0.9)],
        confidence=0.9, source="eyecite", normalized_form="Smith v. Jones" + noise,
    )]
    properties = [PropertyAnnotation(
        property_text="granted" + noise, folio_iri=FOLIO + "P1",
        folio_label="granted" + noise, span=Span(start=g, end=g + 7, text="granted"),
        confidence=0.7, domain_iris=[FOLIO + "D1"], range_iris=[FOLIO + "D2"],
    )]
    job = make_job(text=text, annotations=annotations, individuals=individuals,
                   properties=properties, document_type="Motion" + noise)
    job.result.triples = [SPOTriple(
        subject="court" + noise, predicate="granted" + noise, object="motion" + noise,
        sentence=text, confidence=0.6,
        subject_links=[TripleLink(entity_type="concept", folio_iri=FOLIO + "R1")],
    )]
    return job


def _load_parquet(data: bytes):
    import pyarrow.parquet as pq
    return pq.read_table(io.BytesIO(data))


# ── Parquet ──────────────────────────────────────────────────────────


class TestParquetSingleFile:
    def test_rich_job_reads_back_with_counts_per_record_type(self):
        job = _rich_job()
        table = _load_parquet(ParquetExporter().export(job))

        counts: dict[str, int] = {}
        for rt in table.column("record_type").to_pylist():
            counts[rt] = counts.get(rt, 0) + 1
        assert counts == {"concept": 3, "individual": 1, "property": 1, "triple": 1}

        concept_cols = {"job_id", "span_start", "span_end", "span_text", "concept_text",
                        "folio_iri", "folio_label", "branch", "confidence", "source",
                        "document_type"}
        assert concept_cols <= set(table.column_names)
        assert {"individual_id", "mention_text", "property_text", "domain_iris",
                "subject", "predicate", "object", "has_folio_link"} <= set(table.column_names)

        rows = table.to_pylist()
        concept = next(r for r in rows if r["record_type"] == "concept")
        assert concept["folio_label"] == "Court"
        assert concept["document_type"] == "Motion"
        assert concept["subject"] is None  # union column, not applicable
        triple = next(r for r in rows if r["record_type"] == "triple")
        assert triple["has_folio_link"] is True
        assert triple["subject_iri"] == FOLIO + "R1"
        assert triple["concept_text"] is None
        prop = next(r for r in rows if r["record_type"] == "property")
        assert prop["domain_iris"] == FOLIO + "D1"

    def test_concepts_only_job_reads_back(self):
        job = make_job(annotations=_rich_job().result.annotations[:1])
        table = _load_parquet(ParquetExporter().export(job))
        assert table.column("record_type").to_pylist() == ["concept"]

    def test_empty_job_reads_back_with_schema(self):
        table = _load_parquet(ParquetExporter().export(make_job(annotations=[])))
        assert table.num_rows == 0
        assert "record_type" in table.column_names
        assert "concept_text" in table.column_names


# ── Control characters ───────────────────────────────────────────────


class TestControlCharacters:
    def test_sanitizer_keeps_whitespace_drops_controls(self):
        assert strip_xml_illegal("a\tb\nc\rd" + CTRL + "\x7f\x00e\ud800") == "a\tb\nc\rde"

    def test_xml_parses(self):
        out = XMLExporter().export(_rich_job(CTRL))
        root = ET.fromstring(out.encode("utf-8"))
        assert root.find(".//individual/name").text == "Smith v. Jones"
        assert root.find(".//field[@name='document_type']").text == "Motion"
        for ch in CTRL:
            assert ch not in out

    def test_excel_loads(self):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(ExcelExporter().export(_rich_job(CTRL))))
        assert wb["FOLIO Annotations"]["D2"].value == "court"
        assert wb["Individuals"]["C2"].value == "Smith v. Jones"
        assert wb["Properties"]["C2"].value == "granted"
        assert wb["Triples"]["A2"].value == "court"

    def test_html_has_no_raw_controls(self):
        out = HTMLExporter().export(_rich_job(CTRL))
        for ch in CTRL:
            assert ch not in out

    @pytest.mark.parametrize("noise", [CTRL, ""])
    @pytest.mark.parametrize("empty", [False, True])
    def test_every_format_exports_valid_output(self, noise, empty):
        job = _rich_job(noise)
        if empty:
            job.result.individuals = []
            job.result.properties = []
            job.result.triples = []
        for fmt in list_formats():
            out = get_exporter(fmt).export(job)
            assert out, fmt
            if fmt in ("json", "jsonld", "rag", "propositions"):
                json.loads(out)
            elif fmt in ("jsonl", "elasticsearch", "propositions-ndjson"):
                for line in out.strip().splitlines():
                    json.loads(line)
            elif fmt == "xml":
                ET.fromstring(out.encode("utf-8"))
            elif fmt == "rdf":
                import rdflib
                rdflib.Graph().parse(data=out, format="turtle")
            elif fmt == "parquet":
                _load_parquet(out)
            elif fmt == "excel":
                import openpyxl
                openpyxl.load_workbook(io.BytesIO(out))


# ── HTML span offsets ────────────────────────────────────────────────


class _SpanText(HTMLParser):
    """Collect the text inside each annotated span, keyed by class."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str | None] = []
        self.found: dict[str, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        if tag == "span":
            cls = dict(attrs).get("class")
            self.stack.append(cls)
            if cls:
                self.found.setdefault(cls, []).append("")

    def handle_endtag(self, tag):
        if tag == "span" and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        for cls in self.stack:
            if cls:
                self.found[cls][-1] += data


class TestHTMLOffsets:
    def test_spans_wrap_their_text_after_escaped_characters(self):
        # "&", "<" and ">" precede every span; whole-string escaping used to
        # shift each tag by the entity length and split entities apart.
        parser = _SpanText()
        parser.feed(HTMLExporter().export(_rich_job()))
        assert parser.found["folio-annotation"] == ["court", "motion"]
        assert parser.found["folio-property"] == ["granted"]
        assert parser.found["folio-individual"] == ["Smith v. Jones"]

    def test_document_text_survives_round_trip(self):
        job = _rich_job()
        out = HTMLExporter().export(job)
        body = out[out.index("<pre"):out.index("</pre>")]

        class _Text(HTMLParser):
            text = ""

            def handle_data(self, data):
                self.text += data

        p = _Text(convert_charrefs=True)
        p.feed(body + "</pre>")
        assert p.text == job.result.canonical_text.full_text


# ── brat line framing ────────────────────────────────────────────────


class TestBratFraming:
    def test_multiline_span_text_stays_on_one_line(self):
        text = "The motion to\ndismiss was granted."
        s = text.index("motion")
        e = text.index(" was")
        job = make_job(text=text, annotations=[Annotation(
            span=Span(start=s, end=e, text=text[s:e]),
            concepts=[ConceptMatch(concept_text="motion to dismiss", folio_iri=FOLIO + "R9",
                                   folio_label="Motion\tto Dismiss", branches=["Document"],
                                   confidence=0.9, source="llm")],
        )])
        lines = BratExporter().export(job).split("\n")
        assert len(lines) == 3  # T line + IRI attribute + label attribute
        assert lines[0] == f"T1\tDocument {s} {e}\tmotion to dismiss"
        assert lines[2] == "A2\tFOLIO_Label T1 Motion to Dismiss"
        for line in lines:
            assert line.split("\t")[0][0] in "TA"
