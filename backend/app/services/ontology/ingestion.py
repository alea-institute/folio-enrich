"""Hardened OWL ingestion for third-party ontologies.

The app is the SOLE ingestion point for any ontology OWL: it downloads with a
size cap + timeout, rejects DOCTYPE (defeating XXE / entity-expansion), validates
with a hardened lxml parser, and verifies an integrity checksum before the bytes
are ever handed to folio-python. folio-python's own direct HTTP fetch (un-sized,
un-timed, un-guarded) must never run in production — callers pre-seed the local
cache from `fetch_and_validate_owl` and load with `use_cache=True`.

See docs/plans/2026-07-01-002-...-plan.md (Security section).
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# ~32 MB ceiling (FOLIO ~18 MB, Canon ~14 MB). Aborts streaming past this.
MAX_OWL_BYTES = 32 * 1024 * 1024
_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 30.0
_CHUNK = 64 * 1024

# Only these hosts may serve an ontology OWL. A config-driven repo can't point the
# fetch at an arbitrary/internal host (SSRF).
HOST_ALLOWLIST: frozenset[str] = frozenset({
    "raw.githubusercontent.com",
    "api.github.com",
})


class OWLIngestionError(Exception):
    """Raised when an OWL download fails a security or integrity gate."""


def _assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise OWLIngestionError(f"OWL URL must be https, got '{parsed.scheme}'")
    host = parsed.hostname or ""
    if host not in HOST_ALLOWLIST:
        raise OWLIngestionError(
            f"OWL host '{host}' is not allowlisted ({sorted(HOST_ALLOWLIST)})"
        )
    if parsed.username or parsed.password:
        raise OWLIngestionError("OWL URL must not embed credentials")
    # Resolve + reject private/loopback/link-local/metadata targets (SSRF).
    try:
        for info in socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise OWLIngestionError(f"OWL host '{host}' resolves to a blocked address {ip}")
    except socket.gaierror as exc:
        raise OWLIngestionError(f"OWL host '{host}' did not resolve: {exc}") from exc


def _reject_doctype(data: bytes) -> None:
    # A valid OWL RDF/XML document never needs a DOCTYPE. Rejecting it neutralizes
    # entity-expansion DoS + external-entity XXE + SSRF-via-DTD, independent of the
    # libxml2 version's default entity handling.
    if b"<!doctype" in data[:8192].lower() or b"<!doctype" in data.lower():
        raise OWLIngestionError("OWL contains a DOCTYPE declaration — rejected")


def _validate_xml(data: bytes) -> None:
    from lxml import etree

    parser = etree.XMLParser(
        resolve_entities=False,   # no entity substitution (billion-laughs / XXE)
        no_network=True,          # no external DTD/entity fetch (SSRF)
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,          # keep libxml2's built-in size/expansion guards on
        remove_comments=True,
    )
    try:
        etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise OWLIngestionError(f"OWL failed hardened XML validation: {exc}") from exc


def fetch_and_validate_owl(url: str, expected_sha256: str | None = None) -> tuple[bytes, str]:
    """Download, security-gate, and integrity-verify an OWL. Returns (bytes, sha256).

    Gates, in order: HTTPS + host allowlist + non-private target, streamed download
    with a hard byte cap and timeout, DOCTYPE rejection, hardened-parser validation,
    and (if provided) SHA-256 match. Raises OWLIngestionError on any failure.
    """
    _assert_safe_url(url)

    total = 0
    chunks: list[bytes] = []
    digest = hashlib.sha256()
    try:
        with httpx.Client(follow_redirects=False, timeout=httpx.Timeout(
            _READ_TIMEOUT, connect=_CONNECT_TIMEOUT,
        )) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                declared = resp.headers.get("Content-Length")
                if declared and int(declared) > MAX_OWL_BYTES:
                    raise OWLIngestionError(
                        f"OWL Content-Length {declared} exceeds cap {MAX_OWL_BYTES}"
                    )
                for chunk in resp.iter_bytes(_CHUNK):
                    total += len(chunk)
                    if total > MAX_OWL_BYTES:
                        raise OWLIngestionError(f"OWL exceeded size cap {MAX_OWL_BYTES} bytes")
                    digest.update(chunk)
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise OWLIngestionError(f"OWL download failed: {exc}") from exc

    data = b"".join(chunks)
    _reject_doctype(data)
    _validate_xml(data)

    sha = digest.hexdigest()
    if expected_sha256 and sha != expected_sha256:
        raise OWLIngestionError(
            f"OWL checksum mismatch: expected {expected_sha256}, got {sha}"
        )
    logger.info("Ingested OWL from %s (%d bytes, sha256=%s)", url, total, sha)
    return data, sha
