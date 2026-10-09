from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from folio_propositions import Proposition
from pydantic import BaseModel

from app.api.auth import annotation_access, require_annotation
from app.services.gold.store import GoldDataError, GoldStore, PreSelector
from app.storage.job_store import JobStore

router = APIRouter(prefix="/gold", tags=["gold"])
ANNOTATION_COOKIE_PATHS = ("/gold", "/enrich")
_job_store = JobStore()
_gold_store = GoldStore(_job_store)


class CreateSessionRequest(BaseModel):
    job_id: str
    document_id: str | None = None
    annotator: str = "damien"
    pre_selector: PreSelector
    baseline: bool = False


class CreateValidationSessionRequest(BaseModel):
    slug: str


class CandidateOutcomeRequest(BaseModel):
    outcome: Literal["accepted", "edited", "deleted", "unreviewed"]
    proposition: dict[str, Any] | None = None
    explicit_unresolved: bool = False


class AnnotationRequest(BaseModel):
    proposition: Proposition
    explicit_unresolved: bool = False


class LearningRequest(BaseModel):
    kind: Literal["new-type", "unclassifiable", "forced-fit", "structural-misfit"]
    tag: str | None = None
    note: str | None = None
    annotation_id: str | None = None
    start_char: int | None = None
    end_char: int | None = None


class ExportRequest(BaseModel):
    slug: str | None = None


class BlindSegmentRequest(BaseModel):
    start_char: int
    end_char: int


class AnnotationAccessRequest(BaseModel):
    token: str


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GoldDataError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


async def _require_annotation(
    request: Request,
    x_annotation_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    annotation_cookie: str | None = Cookie(default=None, alias="folio_annotation_access"),
    cf_access_jwt_assertion: str | None = Header(default=None),
) -> None:
    """Preserve the scoped auth gate without dispatching it to a worker thread."""
    require_annotation(
        x_annotation_token,
        x_admin_token,
        annotation_cookie,
        request.headers.get("origin"),
        request.headers.get("host"),
        cf_access_jwt_assertion,
    )


@router.get("/access")
async def get_annotation_access(
    response: Response,
    x_annotation_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    annotation_cookie: str | None = Cookie(default=None, alias="folio_annotation_access"),
    cf_access_jwt_assertion: str | None = Header(default=None),
):
    """Report verified annotation identity without returning any credentials."""
    response.headers["Cache-Control"] = "no-store"
    access = annotation_access(
        x_annotation_token, x_admin_token, annotation_cookie, cf_access_jwt_assertion
    )
    return asdict(access)


@router.post("/access")
async def exchange_annotation_access(request: AnnotationAccessRequest, response: Response):
    """Exchange a scoped bearer for a browser-only, gold-path cookie."""
    require_annotation(request.token, None, None, None, None)
    # Scoped to the gold routes and to /enrich, where the same access gates
    # requests to push a job into folio-insights. HttpOnly, never readable by JS.
    for path in ANNOTATION_COOKIE_PATHS:
        response.set_cookie(
            key="folio_annotation_access",
            value=request.token,
            max_age=7 * 24 * 60 * 60,
            path=path,
            secure=True,
            httponly=True,
            samesite="strict",
        )
    return {"authenticated": True}


@router.delete("/access", status_code=204)
async def clear_annotation_access(response: Response) -> None:
    for path in ANNOTATION_COOKIE_PATHS:
        response.delete_cookie(
            key="folio_annotation_access",
            path=path,
            secure=True,
            httponly=True,
            samesite="strict",
        )


@router.post("/sessions", status_code=201, dependencies=[Depends(_require_annotation)])
async def create_session(request: CreateSessionRequest):
    try:
        return await _gold_store.create_session(
            request.job_id, request.document_id, request.pre_selector, request.annotator,
            baseline=request.baseline,
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.get("/sessions")
async def list_sessions(job_id: str | None = Query(None)):
    return await _gold_store.list(job_id)


@router.get("/records")
async def list_records():
    try:
        return _gold_store.records()
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/validation-sessions", status_code=201, dependencies=[Depends(_require_annotation)])
async def create_validation_session(request: CreateValidationSessionRequest):
    try:
        return await _gold_store.create_validation_session(request.slug)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/bundle")
async def get_bundle(session_id: str):
    try:
        return await _gold_store.bundle(session_id)
    except LookupError as exc:
        raise _http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        return await _gold_store.get(session_id)
    except LookupError as exc:
        raise _http_error(exc) from exc


@router.patch(
    "/sessions/{session_id}/candidates/{candidate_id}",
    dependencies=[Depends(_require_annotation)],
)
async def record_outcome(session_id: str, candidate_id: str, request: CandidateOutcomeRequest):
    try:
        return await _gold_store.record_candidate_outcome(
            session_id, candidate_id, outcome=request.outcome,
            proposition=request.proposition, explicit_unresolved=request.explicit_unresolved,
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/annotations",
    status_code=201,
    dependencies=[Depends(_require_annotation)],
)
async def add_annotation(session_id: str, request: AnnotationRequest):
    try:
        return await _gold_store.add_hand_added(
            session_id, request.proposition, explicit_unresolved=request.explicit_unresolved
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/learnings",
    status_code=201,
    dependencies=[Depends(_require_annotation)],
)
async def add_learning(session_id: str, request: LearningRequest):
    try:
        return await _gold_store.add_learning(session_id, **request.model_dump())
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/blind-segment", dependencies=[Depends(_require_annotation)]
)
async def set_blind_segment(session_id: str, request: BlindSegmentRequest):
    try:
        return await _gold_store.set_blind_segment(
            session_id, request.start_char, request.end_char
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/blind-segment/reveal",
    dependencies=[Depends(_require_annotation)],
)
async def reveal_blind_segment(session_id: str):
    try:
        return await _gold_store.reveal_blind_segment(session_id)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/sessions/{session_id}/coverage-pass", dependencies=[Depends(_require_annotation)]
)
async def record_coverage_pass(session_id: str):
    try:
        return await _gold_store.record_coverage_pass(session_id)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/completeness")
async def session_completeness(session_id: str):
    try:
        return await _gold_store.completeness(session_id)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/export", dependencies=[Depends(_require_annotation)])
async def export_session(session_id: str, request: ExportRequest):
    try:
        return await _gold_store.export(session_id, request.slug)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc
