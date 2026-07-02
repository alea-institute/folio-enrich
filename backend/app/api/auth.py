"""Auth dependencies for privileged API routes."""

from __future__ import annotations

import hmac

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
    if not x_admin_token or not hmac.compare_digest(x_admin_token, token):
        raise HTTPException(status_code=403, detail="Valid X-Admin-Token required")
