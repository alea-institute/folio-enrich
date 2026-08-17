"""Auth dependencies for privileged API routes."""

from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from fastapi import Header, HTTPException


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


def require_annotation(
    x_annotation_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    annotation_cookie: str | None = None,
    annotation_origin: str | None = None,
    request_host: str | None = None,
) -> None:
    """Gate gold mutations with a scoped annotation or full admin token.

    Local/trusted deployments remain open only when neither credential is
    configured. The admin token remains a valid break-glass credential, while
    the annotation token cannot authorize any non-gold administrative route.
    """
    from app.config import settings

    configured = tuple(
        token for token in (settings.annotation_token, settings.admin_token) if token
    )
    if not configured:
        return

    def matches(candidate: str | None) -> bool:
        return bool(candidate) and any(
            hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
            for expected in configured
        )

    if matches(x_annotation_token) or matches(x_admin_token):
        return

    if matches(annotation_cookie):
        origin = urlsplit(annotation_origin or "")
        if (
            origin.scheme in {"http", "https"}
            and origin.netloc
            and origin.netloc == request_host
            and origin.path in {"", "/"}
            and not origin.query
            and not origin.fragment
        ):
            return
        raise HTTPException(status_code=403, detail="Same-origin request required")

    raise HTTPException(
        status_code=403,
        detail="Valid X-Annotation-Token or X-Admin-Token required",
    )
