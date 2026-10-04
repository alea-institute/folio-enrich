"""Auth dependencies for privileged API routes."""

from __future__ import annotations

import hmac
import json
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import urlsplit

import jwt
from fastapi import Header, HTTPException
from jwt.algorithms import RSAAlgorithm


class AccessAuthError(ValueError):
    """An Access assertion could not be verified."""


class CfAccessVerifier:
    """RS256-only Access verification with a bounded, fail-closed JWKS cache.

    The fetcher is injectable for offline tests. A missing kid refreshes the
    team's keys once to support rotation; fetch errors never use stale keys.
    """

    def __init__(
        self,
        *,
        team_domain: str,
        aud: str,
        allowed_emails: str,
        jwks_fetcher: Callable[[], Mapping[str, Any]] | None = None,
        jwks_ttl: float = 600.0,
    ) -> None:
        domain = team_domain.strip().rstrip("/")
        if "://" not in domain:
            if "." not in domain:
                domain += ".cloudflareaccess.com"
            domain = "https://" + domain
        try:
            parsed = urlsplit(domain)
        except ValueError as exc:
            raise AccessAuthError("Invalid Cloudflare Access team domain") from exc
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment
        ):
            raise AccessAuthError("Invalid Cloudflare Access team domain")
        self.issuer = domain
        self.aud = aud.strip()
        self.allowed_emails = frozenset(
            email.strip().lower() for email in allowed_emails.split(",") if email.strip()
        )
        if not self.aud or not self.allowed_emails:
            raise AccessAuthError("Access audience and allowed emails required")
        self.certs_url = self.issuer + "/cdn-cgi/access/certs"
        self._fetch = jwks_fetcher or self._fetch_jwks
        self._jwks_ttl = jwks_ttl
        self._jwks_cache: Mapping[str, Any] | None = None
        self._jwks_fetched_at = 0.0
        self._lock = threading.Lock()

    def _fetch_jwks(self) -> Mapping[str, Any]:
        with urllib.request.urlopen(self.certs_url, timeout=5.0) as response:
            return json.loads(response.read())

    def _get_jwks(self, *, refresh: bool = False) -> Mapping[str, Any]:
        now = time.monotonic()
        if (
            not refresh and self._jwks_cache is not None
            and now - self._jwks_fetched_at < self._jwks_ttl
        ):
            return self._jwks_cache
        try:
            jwks = self._fetch()
        except Exception as exc:  # Any control-plane fetch/parse error denies.
            raise AccessAuthError("JWKS fetch failed") from exc
        keys = jwks.get("keys") if isinstance(jwks, Mapping) else None
        if not isinstance(keys, list) or not keys or not all(isinstance(key, dict) for key in keys):
            raise AccessAuthError("JWKS contained no usable keys")
        self._jwks_cache = jwks
        self._jwks_fetched_at = now
        return jwks

    def _public_key(self, token: str) -> Any:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise AccessAuthError("Malformed Access assertion") from exc
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not kid:
            raise AccessAuthError("RS256 assertion with a key id required")
        with self._lock:
            for refresh in (False, True):
                jwks = self._get_jwks(refresh=refresh)
                for candidate in jwks["keys"]:
                    if candidate.get("kid") != kid:
                        continue
                    if candidate.get("alg", "RS256") != "RS256" or candidate.get("use", "sig") != "sig":
                        raise AccessAuthError("Signing key is not an RS256 key")
                    try:
                        return RSAAlgorithm.from_jwk(json.dumps(candidate))
                    except (ValueError, TypeError, KeyError, jwt.InvalidKeyError) as exc:
                        raise AccessAuthError("Unusable Access signing key") from exc
        raise AccessAuthError("No JWKS key matches assertion kid")

    def verify(self, token: str) -> str:
        """Return only the verified, allow-listed email; never the credential."""
        public_key = self._public_key(token)
        try:
            claims = jwt.decode(
                token, key=public_key, algorithms=["RS256"],
                audience=self.aud, issuer=self.issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError) as exc:
            raise AccessAuthError("Access assertion rejected") from exc
        email = claims.get("email")
        if not isinstance(email, str) or email.strip().lower() not in self.allowed_emails:
            raise AccessAuthError("Email absent or not allowed")
        return email.strip()


def cf_access_enabled() -> bool:
    from app.config import settings

    return all(value.strip() for value in (
        settings.cf_access_team_domain, settings.cf_access_aud, settings.cf_access_allowed_emails
    ))


@lru_cache(maxsize=1)
def _configured_cf_access_verifier(team_domain: str, aud: str, allowed_emails: str) -> CfAccessVerifier:
    """One verifier per active configuration; keys live only in process memory."""
    return CfAccessVerifier(team_domain=team_domain, aud=aud, allowed_emails=allowed_emails)


def get_cf_access_verifier() -> CfAccessVerifier | None:
    from app.config import settings

    if not cf_access_enabled():
        return None
    return _configured_cf_access_verifier(
        settings.cf_access_team_domain, settings.cf_access_aud, settings.cf_access_allowed_emails
    )


@dataclass(frozen=True)
class AnnotationAccess:
    authenticated: bool = False
    via: Literal["cloudflare-access", "token", "open"] | None = None
    email: str | None = None


def _matches_annotation_token(candidate: str | None) -> bool:
    from app.config import settings

    return bool(candidate) and any(
        hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
        for expected in (settings.annotation_token, settings.admin_token) if expected
    )


def annotation_access(
    x_annotation_token: str | None = None,
    x_admin_token: str | None = None,
    annotation_cookie: str | None = None,
    cf_access_jwt_assertion: str | None = None,
) -> AnnotationAccess:
    """Identify authentication for status reads and the gold mutation gate."""
    from app.config import settings

    if _matches_annotation_token(x_annotation_token) or _matches_annotation_token(x_admin_token):
        return AnnotationAccess(True, "token")
    if cf_access_enabled() and cf_access_jwt_assertion:
        try:
            verifier = get_cf_access_verifier()
            if verifier is not None:
                return AnnotationAccess(True, "cloudflare-access", verifier.verify(cf_access_jwt_assertion))
        except AccessAuthError:
            pass  # Invalid Access credentials never authorize; break-glass still works.
    if _matches_annotation_token(annotation_cookie):
        return AnnotationAccess(True, "token")
    if not (settings.annotation_token or settings.admin_token or cf_access_enabled()):
        return AnnotationAccess(True, "open")
    return AnnotationAccess()


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate a mutating/privileged route behind the configured admin token.

    When ``settings.admin_token`` is empty (local/trusted deploy), the route is
    unauthenticated. When set (public deploy), the request must carry a matching
    ``X-Admin-Token`` header. Compared with a constant-time check.
    """
    from app.config import settings

    token = settings.admin_token
    if not token:
        return
    # Encode to bytes so a non-ASCII configured token can't raise TypeError (500)
    # instead of a clean 403.
    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.encode("utf-8"), token.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="Valid X-Admin-Token required")


def _require_same_origin(origin_header: str | None, request_host: str | None) -> None:
    try:
        origin = urlsplit(origin_header or "")
        if (
            origin.scheme in {"http", "https"}
            and origin.netloc and origin.netloc == request_host
            and origin.path in {"", "/"} and not origin.query and not origin.fragment
        ):
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="Same-origin request required")


def require_annotation(
    x_annotation_token: str | None = None,
    x_admin_token: str | None = None,
    annotation_cookie: str | None = None,
    annotation_origin: str | None = None,
    request_host: str | None = None,
    cf_access_jwt_assertion: str | None = None,
) -> None:
    """Gate gold writes with Access or break-glass credentials.

    Cookie and Access authentication require the same Origin/Host check.
    Local mode stays open only without tokens and without enabled Access.
    """
    access = annotation_access(
        x_annotation_token, x_admin_token, annotation_cookie, cf_access_jwt_assertion
    )
    if not access.authenticated:
        raise HTTPException(
            status_code=403,
            detail=(
                "Valid Cloudflare Access login, X-Annotation-Token or X-Admin-Token required"
                if cf_access_enabled() else "Valid X-Annotation-Token or X-Admin-Token required"
            ),
        )
    if access.via == "open":
        return
    if _matches_annotation_token(x_annotation_token) or _matches_annotation_token(x_admin_token):
        return
    _require_same_origin(annotation_origin, request_host)
