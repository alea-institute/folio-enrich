from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.storage.job_store import JobStore

# Re-export shared helpers so they're available via conftest too
from tests.helpers import (  # noqa: F401
    SAMPLE_LEGAL_TEXT,
    SAMPLE_INDIVIDUAL_TEXT,
    SAMPLE_PROPERTY_TEXT,
    make_job,
    FakeLLMProvider,
    FailingLLMProvider,
)


# ── Rate limiter reset ────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the in-memory rate limiter between tests to prevent 429s."""
    from app.middleware.rate_limit import RateLimitMiddleware

    obj = getattr(app, "middleware_stack", None)
    while obj is not None:
        if isinstance(obj, RateLimitMiddleware):
            obj._requests.clear()
            break
        obj = getattr(obj, "app", None)
    yield


# ── Common fixtures ───────────────────────────────────────────────────


@pytest.fixture
def tmp_jobs_dir(tmp_path: Path) -> Path:
    return tmp_path / "jobs"


@pytest.fixture
def job_store(tmp_jobs_dir: Path) -> JobStore:
    return JobStore(base_dir=tmp_jobs_dir)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
