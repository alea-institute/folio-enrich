"""Shared text sanitizing for exporters whose formats reject some characters."""

from __future__ import annotations

import re

# Characters XML 1.0 (and therefore XLSX/openpyxl) cannot hold: C0 controls other
# than tab/newline/carriage return, DEL, lone surrogates, and the U+FFFE/U+FFFF
# noncharacters. Stored jobs and demo data can carry these from PDF extraction.
_XML_ILLEGAL_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff￾￿]"
)


def strip_xml_illegal(value: str) -> str:
    """Remove characters that make XML or Excel output invalid."""
    return _XML_ILLEGAL_RE.sub("", value)


def clean_cell(value):
    """Sanitize a spreadsheet/XML value; non-strings pass through unchanged."""
    return strip_xml_illegal(value) if isinstance(value, str) else value
