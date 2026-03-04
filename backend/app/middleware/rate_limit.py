from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


# Only rate-limit expensive mutation endpoints (POST routes that trigger LLM work).
# Everything else (GET routes, frontend, docs, health) is exempt.
_RATE_LIMITED_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/enrich"),
    ("POST", "/synthetic"),
    ("POST", "/ollama/pull"),
    ("POST", "/ollama/setup"),
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory per-IP rate limiter using sliding window."""

    def __init__(self, app, max_requests: int = 200, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit specific expensive POST endpoints
        method = request.method
        path = request.url.path
        if not any(
            method == m and path.startswith(p) for m, p in _RATE_LIMITED_ROUTES
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window_start
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
