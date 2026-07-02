from __future__ import annotations

import enum

from pydantic import BaseModel, Field

# Historical/default ontology for the models layer. Intentionally a literal (pydantic
# field defaults must be class-def-time constants) and intentionally NOT
# settings.default_ontology: every legacy persisted job was FOLIO, so the on-disk
# default must reflect that regardless of a deployment's configured default.
DEFAULT_ONTOLOGY = "folio"


class DocumentFormat(str, enum.Enum):
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    WORD = "word"
    RTF = "rtf"
    EMAIL = "email"


class DocumentInput(BaseModel):
    content: str
    format: DocumentFormat = DocumentFormat.PLAIN_TEXT
    filename: str | None = None
    # Which ontology to enrich against. Single source of truth read by every
    # pipeline stage via job.input.ontology. Validated at the request boundary
    # (EnrichRequest.ontology); defaults so existing persisted jobs deserialize
    # unchanged. Not re-validated here (persisted model — must always deserialize).
    ontology: str = DEFAULT_ONTOLOGY


class TextElement(BaseModel):
    """Fine-grained document structure element."""
    text: str
    element_type: str = "paragraph"  # "heading", "paragraph", "list_item", "table_cell"
    section_path: list[str] = Field(default_factory=list)  # ["Article I", "Section 2"]
    page: int | None = None
    level: int | None = None  # heading level


class TextChunk(BaseModel):
    text: str
    start_offset: int
    end_offset: int
    chunk_index: int
    sentences: list[str] = Field(default_factory=list)


class CanonicalText(BaseModel):
    full_text: str
    chunks: list[TextChunk] = Field(default_factory=list)
    elements: list[TextElement] = Field(default_factory=list)
    source_format: DocumentFormat = DocumentFormat.PLAIN_TEXT
