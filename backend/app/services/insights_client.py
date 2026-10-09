"""Client for the folio-insights bridge API (status lookups and record push).

folio-enrich extracts propositions from one document; folio-insights holds the
multi-document corpus. Each enrich proposition carries a ``content_iri``
(``urn:folio:shard/<32 hex>``) equal to the insights shard IRI for the same
(source, span), so a reviewer can see each proposition's corpus status.

Contract (implemented by folio-insights):

* ``POST {base}/api/bridge/v1/status`` with ``{"iris": [...], "corpus": str|None}``
  (at most 500 IRIs per request; 422 above) → ``{"corpus", "insights_version",
  "results": [{"iri", "present", ...}]}``. 404 = unknown corpus.
* ``GET {base}/api/bridge/v1/health`` → ``{"status", "corpus", "shards"}``.
* ``POST {base}/api/bridge/v1/ingest?corpus=<name>&framework_id=<id>`` with the
  job's ``propositions`` export as the JSON body → 200 ``IngestReport``
  ``{"created", "existing", "skipped", "refused", ...}``; 401 bad token, 404
  route disabled, 413 record too large. Idempotent per shard IRI.

This module never raises to callers for network or protocol failures: every
outcome is an :class:`InsightsStatus` / :class:`InsightsHealth` whose ``state``
is one of ``connected``, ``not_configured``, ``unreachable`` or ``error``.
The bearer token is never logged, and neither the base URL nor the token is placed in
messages or results (httpx's own INFO request line logs the URL, never headers), so
routes can return these objects to the browser verbatim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

STATUS_PATH = "/api/bridge/v1/status"
HEALTH_PATH = "/api/bridge/v1/health"
INGEST_PATH = "/api/bridge/v1/ingest"
INGEST_COUNT_KEYS = ("created", "existing", "skipped", "refused")
MAX_IRIS_PER_REQUEST = 500

InsightsState = Literal["connected", "not_configured", "unreachable", "error"]

_RESULT_SCALAR_KEYS = (
    "shard_type",
    "epistemic_status",
    "supersedes",
    "superseded_by",
)
_EDGE_LIST_KEYS = ("related", "contesting")


@dataclass
class InsightsStatus:
    state: InsightsState
    message: str | None = None
    corpus: str | None = None
    insights_version: str | None = None
    status_code: int | None = None
    results: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def connected(self) -> bool:
        return self.state == "connected"


@dataclass
class InsightsHealth:
    state: InsightsState
    message: str | None = None
    corpus: str | None = None
    shards: int | None = None
    status_code: int | None = None

    @property
    def connected(self) -> bool:
        return self.state == "connected"


class _ProtocolError(Exception):
    """The insights response did not match the bridge contract."""


def _base_url() -> str | None:
    """Return the configured base URL without a trailing slash, or None."""
    raw = (settings.insights_api_url or "").strip()
    return raw.rstrip("/") or None


def _valid_base(base: str) -> bool:
    parsed = urlparse(base)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = (settings.insights_api_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _corpus() -> str | None:
    return (settings.insights_corpus or "").strip() or None


def _timeout() -> httpx.Timeout:
    seconds = settings.insights_timeout_seconds
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        seconds = 3.0
    return httpx.Timeout(float(seconds))


def _http_error_message(status_code: int) -> str:
    if status_code == 404:
        return "folio-insights does not know the configured corpus."
    if status_code in (401, 403):
        return "folio-insights rejected the configured credentials."
    if status_code == 422:
        return "folio-insights rejected the status request."
    if status_code >= 500:
        return f"folio-insights returned a server error ({status_code})."
    return f"folio-insights returned an unexpected status ({status_code})."


def _edge_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    edges: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("iri"), str):
            relation = item.get("relation")
            edges.append({"iri": item["iri"], "relation": relation if isinstance(relation, str) else ""})
    return edges


def _enrich_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sources = []
    for item in value:
        if isinstance(item, dict):
            sources.append({
                key: item.get(key)
                for key in ("document_id", "proposition_id", "proposition_type")
                if isinstance(item.get(key), (str, type(None)))
            })
    return sources


def _normalize_result(raw: Any) -> dict[str, Any]:
    """Whitelist one result object to the documented contract fields."""
    if not isinstance(raw, dict) or not isinstance(raw.get("iri"), str):
        raise _ProtocolError("result without an iri")
    result: dict[str, Any] = {
        "iri": raw["iri"],
        "present": bool(raw.get("present")),
        "contested": bool(raw.get("contested")),
    }
    for key in _RESULT_SCALAR_KEYS:
        value = raw.get(key)
        result[key] = value if isinstance(value, str) else None
    for key in _EDGE_LIST_KEYS:
        result[key] = _edge_list(raw.get(key))
    result["enrich_sources"] = _enrich_sources(raw.get("enrich_sources"))
    return result


def _dedupe(iris: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for iri in iris:
        if isinstance(iri, str) and iri and iri not in seen:
            seen.add(iri)
            ordered.append(iri)
    return ordered


def _not_configured() -> InsightsStatus:
    return InsightsStatus(state="not_configured", message="folio-insights is not connected.")


async def fetch_status(
    iris: list[str],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> InsightsStatus:
    """Look up corpus status for content IRIs, chunked at 500 per request.

    Never raises for network, HTTP or protocol failures.
    """
    base = _base_url()
    if base is None:
        return _not_configured()
    if not _valid_base(base):
        return InsightsStatus(state="error", message="The folio-insights URL is not a valid http(s) URL.")

    unique = _dedupe(iris)
    corpus = _corpus()
    if not unique:
        # Nothing to look up; report the configured state without a round trip.
        return InsightsStatus(state="connected", corpus=corpus)

    results: dict[str, dict[str, Any]] = {}
    response_corpus: str | None = corpus
    version: str | None = None
    try:
        async with httpx.AsyncClient(
            base_url=base,
            headers=_headers(),
            timeout=_timeout(),
            transport=transport,
            follow_redirects=False,
        ) as client:
            for start in range(0, len(unique), MAX_IRIS_PER_REQUEST):
                chunk = unique[start:start + MAX_IRIS_PER_REQUEST]
                response = await client.post(STATUS_PATH, json={"iris": chunk, "corpus": corpus})
                if response.status_code != 200:
                    return InsightsStatus(
                        state="error",
                        message=_http_error_message(response.status_code),
                        corpus=corpus,
                        status_code=response.status_code,
                    )
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    raise _ProtocolError("missing results list")
                if isinstance(payload.get("corpus"), str):
                    response_corpus = payload["corpus"]
                if isinstance(payload.get("insights_version"), str):
                    version = payload["insights_version"]
                for raw in payload["results"]:
                    normalized = _normalize_result(raw)
                    results[normalized["iri"]] = normalized
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.info("folio-insights status lookup unreachable: %s", type(exc).__name__)
        return InsightsStatus(state="unreachable", message="folio-insights could not be reached.", corpus=corpus)
    except (_ProtocolError, ValueError) as exc:
        logger.warning("folio-insights status response did not match the contract: %s", type(exc).__name__)
        return InsightsStatus(state="error", message="folio-insights returned an unexpected response.", corpus=corpus)

    return InsightsStatus(
        state="connected",
        corpus=response_corpus,
        insights_version=version,
        status_code=200,
        results=results,
    )


async def fetch_health(*, transport: httpx.AsyncBaseTransport | None = None) -> InsightsHealth:
    """Proxy the insights bridge health check. Never raises."""
    base = _base_url()
    if base is None:
        return InsightsHealth(state="not_configured", message="folio-insights is not connected.")
    if not _valid_base(base):
        return InsightsHealth(state="error", message="The folio-insights URL is not a valid http(s) URL.")
    corpus = _corpus()
    try:
        async with httpx.AsyncClient(
            base_url=base,
            headers=_headers(),
            timeout=_timeout(),
            transport=transport,
            follow_redirects=False,
        ) as client:
            response = await client.get(HEALTH_PATH)
            if response.status_code != 200:
                return InsightsHealth(
                    state="error",
                    message=_http_error_message(response.status_code),
                    corpus=corpus,
                    status_code=response.status_code,
                )
            payload = response.json()
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.info("folio-insights health check unreachable: %s", type(exc).__name__)
        return InsightsHealth(state="unreachable", message="folio-insights could not be reached.", corpus=corpus)
    except ValueError:
        return InsightsHealth(state="error", message="folio-insights returned an unexpected response.", corpus=corpus)
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return InsightsHealth(state="error", message="folio-insights reported an unhealthy status.", corpus=corpus, status_code=200)
    shards = payload.get("shards")
    return InsightsHealth(
        state="connected",
        corpus=payload.get("corpus") if isinstance(payload.get("corpus"), str) else corpus,
        shards=shards if isinstance(shards, int) and not isinstance(shards, bool) else None,
        status_code=200,
    )


PushState = Literal["pushed", "not_configured", "failed"]


@dataclass
class PushResult:
    state: PushState
    message: str | None = None
    status_code: int | None = None
    # Whitelisted IngestReport counts (created/existing/skipped/refused) + corpus.
    report: dict[str, Any] | None = None


def _push_timeout() -> httpx.Timeout:
    seconds = settings.insights_push_timeout_seconds
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        seconds = 30.0
    return httpx.Timeout(float(seconds))


def _push_error_message(status_code: int) -> str:
    if status_code in (401, 403):
        return "folio-insights rejected the configured credentials."
    if status_code == 404:
        return "folio-insights ingest is disabled or the corpus is unknown."
    if status_code == 413:
        return "folio-insights refused the record as too large."
    if status_code == 422:
        return "folio-insights rejected the proposition record."
    if status_code >= 500:
        return f"folio-insights returned a server error ({status_code})."
    return f"folio-insights returned an unexpected status ({status_code})."


def _normalize_ingest_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _ProtocolError("ingest report is not an object")
    report: dict[str, Any] = {}
    for key in INGEST_COUNT_KEYS:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise _ProtocolError(f"ingest report without integer {key}")
        report[key] = value
    if isinstance(payload.get("corpus"), str):
        report["corpus"] = payload["corpus"]
    return report


async def push_record(
    record: dict[str, Any],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PushResult:
    """Push one shared-schema proposition record to the insights ingest route.

    Never raises for network, HTTP or protocol failures. Messages never carry
    the base URL or the token, so callers may persist and display them.
    """
    base = _base_url()
    if base is None:
        return PushResult(state="not_configured", message="folio-insights is not connected.")
    if not _valid_base(base):
        return PushResult(state="failed", message="The folio-insights URL is not a valid http(s) URL.")
    params: dict[str, str] = {}
    corpus = _corpus()
    if corpus:
        params["corpus"] = corpus
    framework_id = (settings.insights_framework_id or "").strip()
    if framework_id:
        params["framework_id"] = framework_id
    headers = _headers()
    headers["Content-Type"] = "application/json"
    try:
        async with httpx.AsyncClient(
            base_url=base,
            headers=headers,
            timeout=_push_timeout(),
            transport=transport,
            follow_redirects=False,
        ) as client:
            response = await client.post(INGEST_PATH, params=params, json=record)
            if response.status_code != 200:
                return PushResult(
                    state="failed",
                    message=_push_error_message(response.status_code),
                    status_code=response.status_code,
                )
            report = _normalize_ingest_report(response.json())
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.info("folio-insights push unreachable: %s", type(exc).__name__)
        return PushResult(state="failed", message="folio-insights could not be reached.")
    except (_ProtocolError, ValueError) as exc:
        logger.warning("folio-insights ingest response did not match the contract: %s", type(exc).__name__)
        return PushResult(state="failed", message="folio-insights returned an unexpected response.", status_code=200)
    return PushResult(state="pushed", status_code=200, report=report)
