from __future__ import annotations

import base64
import binascii
import re

from app.models.document import DocumentFormat, DocumentInput, TextElement
from app.services.ingestion.base import IngestorBase
from app.services.ingestion.html_ingestor import HTMLIngestor
from app.services.ingestion.markdown_ingestor import MarkdownIngestor
from app.services.ingestion.pdf_ingestor import PDFIngestor
from app.services.ingestion.plain_text import PlainTextIngestor
from app.services.ingestion.word_ingestor import WordIngestor
from app.services.ingestion.rtf_ingestor import RTFIngestor
from app.services.ingestion.email_ingestor import EmailIngestor

_INGESTORS: dict[DocumentFormat, type[IngestorBase]] = {
    DocumentFormat.PLAIN_TEXT: PlainTextIngestor,
    DocumentFormat.PDF: PDFIngestor,
    DocumentFormat.WORD: WordIngestor,
    DocumentFormat.HTML: HTMLIngestor,
    DocumentFormat.MARKDOWN: MarkdownIngestor,
    DocumentFormat.RTF: RTFIngestor,
    DocumentFormat.EMAIL: EmailIngestor,
}


class UnsupportedFormatError(ValueError):
    """The upload's format can't be ingested (the API maps ValueError to 400)."""


# Leading bytes of each binary format we accept as base64 uploads.
_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"  # DOCX is a ZIP package


def _b64_prefix(content: str, n: int = 16) -> bytes | None:
    """Strictly base64-decode the start of *content*; None if it isn't base64."""
    compact = "".join(content[:128].split())[:64]
    compact = compact[: len(compact) - len(compact) % 4]
    if not compact:
        return None
    try:
        return base64.b64decode(compact, validate=True)[:n]
    except (binascii.Error, ValueError):
        return None


def _looks_like_text(content: str) -> bool:
    """Prose has interior spaces/tabs; base64 (even line-wrapped) never does."""
    return bool(re.search(r"[ \t]", content.strip()))


def _binary_or_text(fmt: DocumentFormat, content: str, magic: bytes) -> DocumentFormat:
    """Keep *fmt* unless *content* is plainly already-extracted text.

    The frontend extracts a PDF/DOCX client-side and then submits the text with
    the original filename, so a ``.pdf`` name doesn't mean base64 PDF bytes.
    """
    prefix = _b64_prefix(content)
    if prefix is not None and prefix.startswith(magic):
        return fmt
    if _looks_like_text(content):
        return DocumentFormat.PLAIN_TEXT
    return fmt  # let the ingestor report the decode error


def _is_rtf(content: str) -> bool:
    stripped = content.lstrip()
    if stripped.startswith("{\\rtf"):
        return True
    prefix = _b64_prefix(stripped)
    return prefix is not None and prefix.lstrip().startswith(b"{\\rtf")


def register_ingestor(fmt: DocumentFormat, cls: type[IngestorBase]) -> None:
    _INGESTORS[fmt] = cls


def get_ingestor(fmt: DocumentFormat) -> IngestorBase:
    cls = _INGESTORS.get(fmt)
    if cls is None:
        raise ValueError(f"No ingestor registered for format: {fmt}")
    return cls()


def detect_format(filename: str | None, content: str) -> DocumentFormat:
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        ext_map = {
            "txt": DocumentFormat.PLAIN_TEXT,
            "md": DocumentFormat.MARKDOWN,
            "html": DocumentFormat.HTML,
            "htm": DocumentFormat.HTML,
            "pdf": DocumentFormat.PDF,
            "docx": DocumentFormat.WORD,
            "rtf": DocumentFormat.RTF,
            "eml": DocumentFormat.EMAIL,
            "msg": DocumentFormat.EMAIL,
        }
        if ext == "doc":
            prefix = _b64_prefix(content)
            if prefix is not None and prefix.startswith(_ZIP_MAGIC):
                return DocumentFormat.WORD  # a .docx saved with a .doc name
            if content.strip() and _looks_like_text(content):
                return DocumentFormat.PLAIN_TEXT
            raise UnsupportedFormatError(
                "Legacy Word .doc files are not supported. "
                "Save the document as .docx (or PDF) and upload it again."
            )
        if ext in ext_map:
            fmt = ext_map[ext]
            if fmt == DocumentFormat.PDF:
                return _binary_or_text(fmt, content, _PDF_MAGIC)
            if fmt == DocumentFormat.WORD:
                return _binary_or_text(fmt, content, _ZIP_MAGIC)
            if fmt == DocumentFormat.RTF and content.strip() and not _is_rtf(content):
                # Already-extracted text: striprtf would drop its line breaks.
                return DocumentFormat.PLAIN_TEXT
            return fmt

    # Heuristic detection for content without filename
    stripped = content.strip()

    # Base64-encoded PDF (starts with %PDF -> JVBER in base64)
    if stripped.startswith("JVBER"):
        return DocumentFormat.PDF

    # Base64-encoded ZIP/DOCX (starts with PK\x03\x04 -> UEsDB in base64)
    if stripped.startswith("UEsDB"):
        return DocumentFormat.WORD

    # RTF
    if stripped.startswith("{\\rtf"):
        return DocumentFormat.RTF

    # Email (RFC 2822 headers)
    if re.match(r"^(From|Subject|Date|To|Message-ID):\s", stripped, re.IGNORECASE):
        return DocumentFormat.EMAIL

    # HTML
    if stripped.startswith("<!") or stripped.lower().startswith("<html"):
        return DocumentFormat.HTML

    # Markdown
    if stripped.startswith("# ") or "\n## " in stripped:
        return DocumentFormat.MARKDOWN

    return DocumentFormat.PLAIN_TEXT


def ingest(doc: DocumentInput) -> str:
    ingestor = get_ingestor(doc.format)
    return ingestor.ingest(doc)


def ingest_with_elements(doc: DocumentInput) -> tuple[str, list[TextElement]]:
    """Ingest document returning both raw text and structural elements."""
    ingestor = get_ingestor(doc.format)
    return ingestor.ingest_with_elements(doc)
