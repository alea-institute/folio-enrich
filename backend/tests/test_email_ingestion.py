"""Tests for Email ingestion."""

import pytest

from app.models.document import DocumentFormat, DocumentInput


class TestEmailIngestion:
    def test_email_format_enum(self):
        assert DocumentFormat.EMAIL == "email"

    def test_eml_ingestor(self):
        from app.services.ingestion.email_ingestor import EmailIngestor

        eml_content = (
            "From: sender@example.com\r\n"
            "To: recipient@example.com\r\n"
            "Subject: Test Email\r\n"
            "Date: Mon, 1 Jan 2024 00:00:00 +0000\r\n"
            "\r\n"
            "This is the body of the test email.\r\n"
        )
        doc = DocumentInput(
            content=eml_content,
            format=DocumentFormat.EMAIL,
            filename="test.eml",
        )
        ingestor = EmailIngestor()
        text = ingestor.ingest(doc)
        assert "sender@example.com" in text
        assert "Test Email" in text
        assert "body of the test email" in text

    def test_email_registered_in_registry(self):
        from app.services.ingestion.registry import get_ingestor

        ingestor = get_ingestor(DocumentFormat.EMAIL)
        assert ingestor is not None

    def test_detect_format_eml(self):
        from app.services.ingestion.registry import detect_format

        assert detect_format("message.eml", "") == DocumentFormat.EMAIL

    def test_detect_format_msg(self):
        from app.services.ingestion.registry import detect_format

        assert detect_format("message.msg", "") == DocumentFormat.EMAIL

    def test_msg_ingestor_parses_mapi_streams(self, monkeypatch):
        """.msg parsing via olefile: Unicode MAPI streams + submit-time date."""
        import base64
        import datetime
        import struct

        import olefile

        from app.services.ingestion.email_ingestor import EmailIngestor

        # MAPI string properties are stored as UTF-16-LE under the 001F type.
        streams = {
            "__substg1.0_0C1A001F": "Alice <alice@example.com>".encode("utf-16-le"),
            "__substg1.0_0E04001F": "Bob <bob@example.com>".encode("utf-16-le"),
            "__substg1.0_0037001F": "Quarterly report".encode("utf-16-le"),
            "__substg1.0_1000001F": "Please see the attached figures.".encode("utf-16-le"),
        }
        # Properties stream: 32-byte header + one PT_SYSTIME entry (submit time).
        dt = datetime.datetime(2026, 7, 6, 15, 30, tzinfo=datetime.timezone.utc)
        epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        filetime = int((dt - epoch).total_seconds()) * 10_000_000
        streams["__properties_version1.0"] = b"\x00" * 32 + struct.pack(
            "<IIQ", 0x00390040, 0x06, filetime
        )

        monkeypatch.setattr(olefile, "OleFileIO", lambda *a, **k: _FakeOle(streams))

        doc = DocumentInput(
            content=base64.b64encode(b"ignored-by-fake-ole").decode(),
            format=DocumentFormat.EMAIL,
            filename="report.msg",
        )
        text = EmailIngestor().ingest(doc)

        assert "From: Alice <alice@example.com>" in text
        assert "To: Bob <bob@example.com>" in text
        assert "Subject: Quarterly report" in text
        assert "Please see the attached figures." in text
        assert "Date: 2026-07-06T15:30:00+00:00" in text

    def test_msg_ingestor_ascii_fallback(self, monkeypatch):
        """Falls back to the ASCII (001E / cp1252) stream when Unicode is absent."""
        import base64

        import olefile

        from app.services.ingestion.email_ingestor import EmailIngestor

        streams = {"__substg1.0_0037001E": "Café meeting".encode("cp1252")}
        monkeypatch.setattr(olefile, "OleFileIO", lambda *a, **k: _FakeOle(streams))

        doc = DocumentInput(
            content=base64.b64encode(b"x").decode(),
            format=DocumentFormat.EMAIL,
            filename="m.msg",
        )
        text = EmailIngestor().ingest(doc)
        assert "Subject: Café meeting" in text


class _FakeOle:
    """Minimal stand-in for ``olefile.OleFileIO`` driven by a name→bytes map."""

    def __init__(self, streams):
        self._streams = streams

    def exists(self, name):
        return name in self._streams

    def openstream(self, name):
        import io

        return io.BytesIO(self._streams[name])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
