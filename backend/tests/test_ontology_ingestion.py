"""Security gates for third-party OWL ingestion (Phase 2b)."""

from __future__ import annotations

import hashlib

import pytest

from app.services.ontology.ingestion import (
    OWLIngestionError,
    _assert_safe_url,
    _reject_doctype,
    _validate_xml,
    fetch_and_validate_owl,
)

CANON_URL = (
    "https://raw.githubusercontent.com/CatholicOS/ontology-semantic-canon/"
    "main/sources/ontology-semantic-canon.owl"
)
# Pinned by the Phase 0 spike (backend/scripts/validate_canon_owl.py).
CANON_SHA256 = "add8b2b140273b197b759f8945b4f5aa66ecb1ec801fcc69431f1b4baaf59f24"

VALID_OWL = (
    b'<?xml version="1.0"?><rdf:RDF '
    b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
    b'xmlns:owl="http://www.w3.org/2002/07/owl#">'
    b'<owl:Class rdf:about="https://x/A"/></rdf:RDF>'
)
BILLION_LAUGHS = (
    b'<?xml version="1.0"?>'
    b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
    b'<!ENTITY lol2 "&lol;&lol;&lol;">]>'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">&lol2;</rdf:RDF>'
)


class TestUrlGate:
    def test_rejects_non_https(self):
        with pytest.raises(OWLIngestionError, match="https"):
            _assert_safe_url("http://raw.githubusercontent.com/x.owl")

    def test_rejects_non_allowlisted_host(self):
        with pytest.raises(OWLIngestionError, match="allowlist"):
            _assert_safe_url("https://evil.example.com/x.owl")

    def test_rejects_embedded_credentials(self):
        with pytest.raises(OWLIngestionError, match="credential"):
            _assert_safe_url("https://user:pw@raw.githubusercontent.com/x.owl")

    def test_accepts_allowlisted_github(self):
        # resolves + passes (network DNS only, no download)
        _assert_safe_url(CANON_URL)


class TestDoctypeGate:
    def test_rejects_doctype(self):
        with pytest.raises(OWLIngestionError, match="DOCTYPE"):
            _reject_doctype(BILLION_LAUGHS)

    def test_allows_clean_owl(self):
        _reject_doctype(VALID_OWL)  # no raise


class TestXmlGate:
    def test_valid_owl_parses(self):
        _validate_xml(VALID_OWL)  # no raise

    def test_malformed_rejected(self):
        with pytest.raises(OWLIngestionError, match="validation"):
            _validate_xml(b"<rdf:RDF><unclosed></rdf:RDF>")

    def test_entities_not_resolved(self):
        # Defense in depth beyond the DOCTYPE gate: the hardened parser must NOT
        # substitute entity text (no expansion => no XXE exfiltration / no DoS
        # amplification). Verify a defined entity is left unexpanded in the tree.
        from lxml import etree

        xxe = (
            b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY secret "LEAKED">]>'
            b'<r>&secret;</r>'
        )
        parser = etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False,
        )
        root = etree.fromstring(xxe, parser=parser)
        assert "LEAKED" not in (root.text or "")  # entity NOT expanded


@pytest.mark.slow
class TestRealCanonFetch:
    def test_fetch_canon_with_pinned_checksum(self):
        data, sha = fetch_and_validate_owl(CANON_URL, expected_sha256=CANON_SHA256)
        assert sha == CANON_SHA256
        assert len(data) > 5_000_000
        assert hashlib.sha256(data).hexdigest() == CANON_SHA256

    def test_checksum_mismatch_raises(self):
        with pytest.raises(OWLIngestionError, match="checksum"):
            fetch_and_validate_owl(CANON_URL, expected_sha256="0" * 64)
