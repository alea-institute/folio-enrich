from __future__ import annotations

import email
import email.policy

from app.models.document import DocumentInput
from app.services.ingestion.base import IngestorBase


class EmailIngestor(IngestorBase):
    """Extract plain text from EML and MSG email files."""

    def ingest(self, doc: DocumentInput) -> str:
        content = doc.content
        filename = (doc.filename or "").lower()

        if filename.endswith(".msg"):
            return self._ingest_msg(content)
        else:
            # Default: EML format (RFC 2822)
            return self._ingest_eml(content)

    def _ingest_eml(self, content: str) -> str:
        """Parse EML using stdlib email module."""
        # Content may be base64-encoded raw bytes or the EML text directly
        try:
            import base64
            raw = base64.b64decode(content)
            content = raw.decode("utf-8", errors="replace")
        except Exception:
            pass

        msg = email.message_from_string(content, policy=email.policy.default)
        parts = []

        # Add headers
        for header in ("From", "To", "Subject", "Date"):
            value = msg.get(header, "")
            if value:
                parts.append(f"{header}: {value}")

        if parts:
            parts.append("")  # blank line separator

        # Extract body text
        body = msg.get_body(preferencelist=("plain", "html"))
        if body is not None:
            body_content = body.get_content()
            if body.get_content_type() == "text/html":
                # Strip HTML tags for plain text
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(body_content, "html.parser")
                    body_content = soup.get_text(separator="\n")
                except ImportError:
                    import re
                    body_content = re.sub(r"<[^>]+>", "", body_content)
            parts.append(body_content)

        return "\n".join(parts)

    def _ingest_msg(self, content: str) -> str:
        """Parse Outlook ``.msg`` files via ``olefile`` (BSD).

        A ``.msg`` file is an OLE2 compound document whose MAPI properties live
        in named streams. We read the few properties we need directly, avoiding
        the GPL-3.0 ``extract-msg`` dependency (folio-enrich is MIT).
        """
        import base64
        import io

        try:
            import olefile
        except ImportError:  # pragma: no cover - dependency is declared
            raise ImportError("olefile is required for .msg ingestion.")

        # MSG files are binary — decode from base64.
        msg_bytes = base64.b64decode(content)

        with olefile.OleFileIO(io.BytesIO(msg_bytes)) as ole:
            sender = _msg_str(ole, "0C1A")  # PidTagSenderName
            to = _msg_str(ole, "0E04")  # PidTagDisplayTo
            subject = _msg_str(ole, "0037")  # PidTagSubject
            date = _msg_date(ole)  # PidTagClientSubmitTime
            body = _msg_str(ole, "1000")  # PidTagBody

        parts = []
        if sender:
            parts.append(f"From: {sender}")
        if to:
            parts.append(f"To: {to}")
        if subject:
            parts.append(f"Subject: {subject}")
        if date:
            parts.append(f"Date: {date}")
        if parts:
            parts.append("")
        if body:
            parts.append(body)
        return "\n".join(parts)


def _msg_str(ole, prop_id: str) -> str | None:
    """Read a MAPI string property, preferring Unicode (``001F``) over ASCII (``001E``)."""
    for type_suffix, encoding in (("001F", "utf-16-le"), ("001E", "cp1252")):
        stream = f"__substg1.0_{prop_id}{type_suffix}"
        if ole.exists(stream):
            raw = ole.openstream(stream).read()
            try:
                value = raw.decode(encoding).rstrip("\x00").strip()
            except UnicodeDecodeError:
                continue
            return value or None
    return None


def _msg_date(ole) -> str | None:
    """Best-effort ISO date from PidTagClientSubmitTime (0x0039, PT_SYSTIME).

    Fixed-width properties are stored 16 bytes each in the top-level
    ``__properties_version1.0`` stream (32-byte header, then entries of
    ``[tag u32][flags u32][value u64]``). Returns ``None`` if absent/unparseable.
    """
    import datetime
    import struct

    stream = "__properties_version1.0"
    if not ole.exists(stream):
        return None
    try:
        data = ole.openstream(stream).read()
        target_tag = 0x00390040  # id 0x0039 (submit time) | type 0x0040 (PT_SYSTIME)
        pos = 32
        while pos + 16 <= len(data):
            tag = struct.unpack_from("<I", data, pos)[0]
            if tag == target_tag:
                filetime = struct.unpack_from("<Q", data, pos + 8)[0]
                if filetime:
                    epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
                    dt = epoch + datetime.timedelta(microseconds=filetime // 10)
                    return dt.isoformat()
                return None
            pos += 16
    except (struct.error, ValueError, OverflowError):
        return None
    return None
