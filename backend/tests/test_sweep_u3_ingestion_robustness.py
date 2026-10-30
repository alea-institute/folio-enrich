"""U3 bug sweep: ingestion and pipeline robustness regressions."""
from __future__ import annotations

import base64
import io
from email.message import EmailMessage

import pytest

from app.models.document import DocumentFormat, DocumentInput
from app.models.job import Job, JobStatus
from app.pipeline.orchestrator import PipelineOrchestrator, TaskLLMs
from app.pipeline.stages.base import PipelineStage
from app.pipeline.stages.ingestion_stage import IngestionStage
from app.pipeline.stages.normalization_stage import NormalizationStage
from app.services.ingestion.email_ingestor import EmailIngestor
from app.services.ingestion.registry import (
    UnsupportedFormatError,
    detect_format,
    ingest,
)
from app.services.normalization.normalizer import (
    normalize_and_chunk,
    split_sentences,
)

OPINION_TEXT = (
    "The court granted the motion for summary judgment.\n\n"
    "Under Minn. Stat. § 504B.178, the landlord must return the deposit."
)


def _pdf_b64() -> str:
    from pypdf import PdfWriter

    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buf)
    return base64.b64encode(buf.getvalue()).decode()


def _docx_b64(text: str) -> str:
    from docx import Document

    buf = io.BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


# ── Defect 1: pre-parallel failure fails the job ─────────────────────


class _FailingStage(PipelineStage):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, job: Job) -> Job:
        raise RuntimeError("boom")


@pytest.mark.asyncio
class TestTextStageFailureFailsJob:
    async def test_parallel_mode_ingestion_failure_fails_job(self, job_store):
        # Plain text forced through the PDF ingestor: base64/PDF decode fails.
        job = Job(input=DocumentInput(
            content=OPINION_TEXT, format=DocumentFormat.PDF, filename="opinion.pdf",
        ))
        await job_store.save(job)
        orch = PipelineOrchestrator(job_store, llm=None, task_llms=None)
        result = await orch.run(job)

        assert result.status == JobStatus.FAILED
        assert result.error and result.error.startswith("Could not read the document")
        saved = await job_store.load(job.id)
        assert saved.status == JobStatus.FAILED

    async def test_flat_mode_ingestion_failure_fails_job(self, job_store):
        job = Job(input=DocumentInput(content="x", format=DocumentFormat.PLAIN_TEXT))
        orch = PipelineOrchestrator(job_store, stages=[_FailingStage("ingestion")])
        result = await orch.run(job)
        assert result.status == JobStatus.FAILED
        assert "boom" in result.error

    async def test_later_stage_failure_still_continues(self, job_store):
        job = Job(input=DocumentInput(content=OPINION_TEXT, format=DocumentFormat.PLAIN_TEXT))
        orch = PipelineOrchestrator(job_store, stages=[
            IngestionStage(), NormalizationStage(), _FailingStage("resolution"),
        ])
        result = await orch.run(job)
        assert result.status == JobStatus.COMPLETED
        assert result.result.canonical_text is not None


# ── Defect 2: tolerant format detection ──────────────────────────────


class TestTolerantFormatDetection:
    @pytest.mark.parametrize("filename", ["opinion.pdf", "contract.docx"])
    def test_extracted_text_with_binary_filename_is_plain_text(self, filename):
        assert detect_format(filename, OPINION_TEXT) == DocumentFormat.PLAIN_TEXT

    def test_real_base64_binaries_keep_their_format(self):
        assert detect_format("opinion.pdf", _pdf_b64()) == DocumentFormat.PDF
        assert detect_format("contract.docx", _docx_b64("Hi")) == DocumentFormat.WORD

    def test_line_wrapped_base64_pdf_keeps_pdf(self):
        b64 = _pdf_b64()
        wrapped = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
        assert detect_format("opinion.pdf", wrapped) == DocumentFormat.PDF

    def test_rtf_name_with_extracted_text_keeps_line_breaks(self):
        assert detect_format("memo.rtf", OPINION_TEXT) == DocumentFormat.PLAIN_TEXT
        doc = DocumentInput(content=OPINION_TEXT, format=DocumentFormat.RTF)
        assert ingest(doc) == OPINION_TEXT  # explicit format: no striprtf pass

    def test_real_rtf_still_detected(self):
        rtf = r"{\rtf1\ansi Hello \par World}"
        assert detect_format("memo.rtf", rtf) == DocumentFormat.RTF
        b64 = base64.b64encode(rtf.encode()).decode()
        assert detect_format("memo.rtf", b64) == DocumentFormat.RTF

    @pytest.mark.asyncio
    async def test_enrich_extracted_text_with_pdf_filename(self, client):
        # The exact UI repro: extracted text resubmitted with the binary name.
        r = await client.post(
            "/enrich/extract", json={"content": OPINION_TEXT, "filename": "opinion.pdf"},
        )
        assert r.status_code == 200
        assert r.json()["format"] == "plain_text"
        assert r.json()["text"] == OPINION_TEXT


# ── Defect 3: nupunkt sentence splitting ─────────────────────────────


class TestNupunktSentences:
    def test_legal_abbreviations_do_not_split(self):
        text = (
            "Under Minn. Stat. § 504B.178, the court in Smith v. Jones Corp. "
            "held X. Then Y happened."
        )
        assert split_sentences(text) == [
            "Under Minn. Stat. § 504B.178, the court in Smith v. Jones Corp. held X.",
            "Then Y happened.",
        ]

    def test_us_reporter_citation_does_not_split(self):
        text = "See Brown v. Board, 347 U.S. 483 (1954). The Court agreed."
        assert len(split_sentences(text)) == 2


# ── Defect 4: control characters stripped, offsets consistent ───────


class TestControlCharacters:
    RAW = "Tenant\x00shall\x07pay\x1frent.\x7f\tLandlord\x0bshall\r\nrepair\x0c."

    def test_control_chars_removed(self):
        canonical = normalize_and_chunk(self.RAW)
        text = canonical.full_text
        for ch in text:
            assert ch in "\t\n\r" or ord(ch) >= 0x20 and ord(ch) != 0x7F, repr(ch)
        assert text == "Tenant shall pay rent. Landlord shall\nrepair ."

    def test_chunks_and_sentences_index_normalized_text(self):
        canonical = normalize_and_chunk(self.RAW * 3)
        full = canonical.full_text
        for chunk in canonical.chunks:
            assert full[chunk.start_offset:chunk.end_offset] == chunk.text
            for sent in chunk.sentences:
                assert sent in full

    def test_xml_safe_after_normalization(self):
        from xml.etree import ElementTree as ET

        canonical = normalize_and_chunk(self.RAW)
        el = ET.Element("doc")
        el.text = canonical.full_text
        ET.fromstring(ET.tostring(el))  # well-formed


# ── Defect 5: raw EML text is not base64-"decoded" ───────────────────


def _make_email(subject_len: int, body_len: int) -> str:
    msg = EmailMessage()
    msg["From"] = "counsel@example.com"
    msg["To"] = "client@example.com"
    msg["Subject"] = "Lease " + "s" * subject_len
    msg.set_content("Tenant shall pay rent. " + "b" * body_len)
    return msg.as_string()


class TestEmailBase64:
    @pytest.mark.parametrize("subject_len,body_len", [
        (s, b) for s in range(0, 12, 3) for b in range(0, 9)
    ])
    def test_raw_and_base64_emails_parse(self, subject_len, body_len):
        raw = _make_email(subject_len, body_len)
        for content in (raw, base64.b64encode(raw.encode()).decode()):
            out = EmailIngestor().ingest(DocumentInput(content=content, filename="m.eml"))
            assert "Subject: Lease" in out
            assert "Tenant shall pay rent." in out

    def test_raw_email_with_length_divisible_by_four(self):
        # Lenient b64decode keeps only alphabet chars; when their count is a
        # multiple of 4 the old code "decoded" raw text into garbage.
        hits = 0
        for n in range(64):
            raw = _make_email(n, n % 5)
            alphabet = sum(c.isalnum() or c in "+/" for c in raw)
            if alphabet % 4:
                continue
            hits += 1
            out = EmailIngestor().ingest(DocumentInput(content=raw, filename="m.eml"))
            assert "Tenant shall pay rent." in out
        assert hits > 0


# ── Defect 6: legacy .doc rejected with a clear 4xx ──────────────────


class TestLegacyDoc:
    OLE_B64 = base64.b64encode(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64).decode()

    def test_detect_format_rejects_binary_doc(self):
        with pytest.raises(UnsupportedFormatError, match=r"\.docx"):
            detect_format("brief.doc", self.OLE_B64)

    def test_docx_saved_as_doc_still_works(self):
        assert detect_format("brief.doc", _docx_b64("Hi")) == DocumentFormat.WORD

    @pytest.mark.asyncio
    async def test_extract_doc_returns_400_with_clear_message(self, client):
        r = await client.post(
            "/enrich/extract", json={"content": self.OLE_B64, "filename": "brief.doc"},
        )
        assert r.status_code == 400
        assert ".doc files are not supported" in r.json()["detail"]


# ── Defect 7: request provider not overridden by Ollama tiering ──────


class TestOllamaTierRespectsRequestProvider:
    @pytest.fixture
    def ollama_tier_settings(self, monkeypatch):
        from app.config import settings
        from app.pipeline.orchestrator import LLM_TASKS

        monkeypatch.setattr(settings, "llm_provider", "ollama")
        monkeypatch.setattr(settings, "llm_model", "")
        for task in LLM_TASKS:
            monkeypatch.setattr(settings, f"llm_{task}_provider", "", raising=False)
            monkeypatch.setattr(settings, f"llm_{task}_model", "", raising=False)
        return settings

    def test_anthropic_request_keeps_anthropic(self, ollama_tier_settings):
        from app.services.llm.anthropic_provider import AnthropicProvider
        from app.services.llm.registry import get_provider

        fallback = get_provider("anthropic", api_key="sk-test", model="claude-test")
        task_llms = TaskLLMs.from_settings(fallback=fallback)
        for llm in (task_llms.concept, task_llms.classifier, task_llms.individual,
                    task_llms.property_llm, task_llms.document_type):
            assert isinstance(llm, AnthropicProvider)
            assert llm.model == "claude-test"

    def test_ollama_request_still_uses_tier_models(self, ollama_tier_settings):
        from app.services.llm.registry import get_provider

        fallback = get_provider("ollama")
        task_llms = TaskLLMs.from_settings(fallback=fallback)
        s = ollama_tier_settings
        assert task_llms.document_type.model == s.ollama_model_simple
        assert task_llms.concept.model == s.ollama_model_medium
        assert task_llms.classifier.model == s.ollama_model_complex
