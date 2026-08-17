from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from folio_propositions import Proposition
from pydantic import BaseModel

from app.services.gold.store import GoldStore, PreSelector
from app.storage.job_store import JobStore

router = APIRouter(prefix="/gold", tags=["gold"])
_job_store = JobStore()
_gold_store = GoldStore(_job_store)


class CreateSessionRequest(BaseModel):
    job_id: str
    document_id: str | None = None
    annotator: str = "damien"
    pre_selector: PreSelector
    baseline: bool = False


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


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/sessions", status_code=201)
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


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        return await _gold_store.get(session_id)
    except LookupError as exc:
        raise _http_error(exc) from exc


@router.patch("/sessions/{session_id}/candidates/{candidate_id}")
async def record_outcome(session_id: str, candidate_id: str, request: CandidateOutcomeRequest):
    try:
        return await _gold_store.record_candidate_outcome(
            session_id, candidate_id, outcome=request.outcome,
            proposition=request.proposition, explicit_unresolved=request.explicit_unresolved,
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/annotations", status_code=201)
async def add_annotation(session_id: str, request: AnnotationRequest):
    try:
        return await _gold_store.add_hand_added(
            session_id, request.proposition, explicit_unresolved=request.explicit_unresolved
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/learnings", status_code=201)
async def add_learning(session_id: str, request: LearningRequest):
    try:
        return await _gold_store.add_learning(session_id, **request.model_dump())
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/blind-segment")
async def set_blind_segment(session_id: str, request: BlindSegmentRequest):
    try:
        return await _gold_store.set_blind_segment(
            session_id, request.start_char, request.end_char
        )
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/blind-segment/reveal")
async def reveal_blind_segment(session_id: str):
    try:
        return await _gold_store.reveal_blind_segment(session_id)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/coverage-pass")
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


@router.post("/sessions/{session_id}/export")
async def export_session(session_id: str, request: ExportRequest):
    try:
        return await _gold_store.export(session_id, request.slug)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc
