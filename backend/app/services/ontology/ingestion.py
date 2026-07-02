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


# Namespaced element tags for the AC-3 label-coverage gate (Clark notation).
_OWL_TAG = "{http://www.w3.org/2002/07/owl#}Class"
_RDFS_LABEL_TAG = "{http://www.w3.org/2000/01/rdf-schema#}label"
_RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"


def label_coverage_stats(data: bytes, offender_cap: int = 20) -> tuple[int, int, list[str]]:
    """Return (named_classes, missing_label, sample_offender_iris) for an OWL.

    Mirrors the Phase 0 spike (scripts/validate_canon_owl.py ``raw_class_stats``):
    counts ``owl:Class`` elements with an ``rdf:about`` (named classes) and how many
    of those lack an ``rdfs:label``. folio-python silently drops label-less classes,
    so this measures how much of the ontology would survive the load. Anonymous
    restrictions / blank nodes (no ``rdf:about``) are ignored. Offender IRIs are
    collected up to ``offender_cap`` for a clear error message. Uses the same hardened
    parser as :func:`_validate_xml`.
    """
    from lxml import etree

    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        remove_comments=True,
    )
    root = etree.fromstring(data, parser=parser)
    named = 0
    missing = 0
    offenders: list[str] = []
    for cls in root.iter(_OWL_TAG):
        about = cls.get(_RDF_ABOUT)
        if not about:
            continue  # anonymous restriction / blank node
        named += 1
        if cls.find(_RDFS_LABEL_TAG) is None:
            missing += 1
            if len(offenders) < offender_cap:
                offenders.append(about)
    return named, missing, offenders


def assert_label_coverage(data: bytes, min_coverage: float, ontology_id: str) -> None:
    """Raise OWLIngestionError if OWL label coverage < ``min_coverage`` percent.

    Fail-open on a gate-computation error (log a warning, do not block the load); the
    gate exists to catch a *silent* upstream regression, not to be a second XML
    validator — the hardened parse in :func:`fetch_and_validate_owl` already ran.
    Fail-closed only on a genuine coverage violation.
    """
    try:
        named, missing, offenders = label_coverage_stats(data)
    except Exception as exc:  # noqa: BLE001 - fail open on gate-computation error
        logger.warning(
            "Label-coverage gate could not parse OWL for '%s' (%s); allowing load",
            ontology_id, exc,
        )
        return
    if named == 0:
        logger.warning(
            "Label-coverage gate found no named owl:Class for '%s'; allowing load",
            ontology_id,
        )
        return
    retention = (named - missing) / named * 100
    if retention < min_coverage:
        sample = ", ".join(offenders) or "(none captured)"
        raise OWLIngestionError(
            f"OWL for '{ontology_id}' failed rdfs:label coverage gate: "
            f"{retention:.2f}% < {min_coverage:.2f}% required "
            f"({missing} of {named} named classes lack rdfs:label). "
            f"Sample offenders: {sample}"
        )
    logger.info(
        "Label-coverage gate passed for '%s': %.2f%% (>= %.2f%%)",
        ontology_id, retention, min_coverage,
    )


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
    # Resolve + reject any non-global target (SSRF): private, loopback, link-local,
    # reserved, multicast, and shared/CGNAT (100.64/10) — `not is_global` covers all
    # and future ranges. NB: this is best-effort vs DNS rebinding (httpx re-resolves
    # at connect time); mitigated because the host allowlist is GitHub-owned.
    try:
        for info in socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                raise OWLIngestionError(f"OWL host '{host}' resolves to a non-global address {ip}")
    except socket.gaierror as exc:
        raise OWLIngestionError(f"OWL host '{host}' did not resolve: {exc}") from exc


def _reject_doctype(data: bytes) -> None:
    # A valid OWL RDF/XML document never needs a DOCTYPE. Rejecting it is
    # defense-in-depth against entity-expansion DoS / external-entity XXE / SSRF-via-
    # DTD; the hardened parser (resolve_entities=False, no_network, load_dtd=False)
    # is the primary guarantee even if an exotic encoding slips a DOCTYPE past this
    # byte scan. A DOCTYPE is only legal in the XML prolog, so scanning the leading
    # bytes is sufficient and avoids lowercasing the whole ~14-18 MB payload. Handle
    # a UTF-16 BOM by stripping interleaved NULs from the prolog slice before matching.
    prolog = data[:8192]
    if prolog.startswith((b"\xff\xfe", b"\xfe\xff")):
        prolog = prolog.replace(b"\x00", b"")
    if b"<!doctype" in prolog.lower():
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
                # follow_redirects=False + raise_for_status only catches 4xx/5xx, so
                # reject a 3xx explicitly (clear error, no silent redirect-following).
                if resp.is_redirect:
                    raise OWLIngestionError(
                        f"OWL URL returned redirect {resp.status_code} (not allowed)"
                    )
                resp.raise_for_status()
                declared = resp.headers.get("Content-Length")
                if declared:
                    try:
                        declared_n = int(declared)
                    except ValueError:
                        declared_n = -1  # malformed header -> rely on the stream cap
                    if declared_n > MAX_OWL_BYTES:
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
