from __future__ import annotations

import json
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import UUID, uuid4

from folio_propositions import SCHEMA_VERSION, Disposition, Proposition, migrate_record
from pydantic import BaseModel, Field

from app.config import settings
from app.models.document import CanonicalText
from app.storage.job_store import PROTECTED_JOB_IDS, JobStore

WRAPPER_SCHEMA_VERSION = 1
WrapperMigration = Callable[[dict[str, Any]], dict[str, Any]]
WRAPPER_MIGRATIONS: dict[tuple[int, int], WrapperMigration] = {}


def register_migration(version_from: int, version_to: int):
    if version_to != version_from + 1:
        raise ValueError("wrapper migrations must advance one version")

    def decorator(function: WrapperMigration) -> WrapperMigration:
        WRAPPER_MIGRATIONS[(version_from, version_to)] = function
        return function

    return decorator


@register_migration(1, 2)
def _v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(data)
    migrated["wrapper_schema_version"] = 2
    migrated["provenance_model"] = "origin+outcome"
    return migrated


def migrate_session(data: dict[str, Any], target_wrapper_version: int) -> dict[str, Any]:
    migrated = deepcopy(data)
    current = int(migrated.get("wrapper_schema_version", 1))
    if target_wrapper_version < current:
        raise ValueError("wrapper schema downgrades are not supported")
    while current < target_wrapper_version:
        migration = WRAPPER_MIGRATIONS.get((current, current + 1))
        if migration is None:
            raise ValueError(f"no wrapper migration registered for {current}->{current + 1}")
        migrated = migration(migrated)
        current += 1
    return migrated


def migrate_proposition_payload(data: dict[str, Any], target_version: int = SCHEMA_VERSION) -> dict[str, Any]:
    return migrate_record(deepcopy(data), target_version=target_version)


class PreSelector(BaseModel):
    source: Literal["lexicon-only", "lexicon+llm"]
    lexicon_version: str | None = None
    lexicon_config: dict[str, Any] = Field(default_factory=dict)
    llm_provider: str | None = None
    llm_model: str | None = None


class CandidateRecord(BaseModel):
    proposition: Proposition
    original: Proposition
    outcome: Literal["accepted", "edited", "deleted", "unreviewed"] = "unreviewed"
    edit_kind: Literal["field", "boundary", "both"] | None = None
    explicit_unresolved: bool = False


class HandAddedRecord(BaseModel):
    proposition: Proposition
    provenance: Literal["hand-added"] = "hand-added"
    explicit_unresolved: bool = False


class BlindSegment(BaseModel):
    start_char: int
    end_char: int


class CycleLearning(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["new-type", "unclassifiable", "forced-fit", "structural-misfit"]
    tag: str | None = None
    note: str | None = None
    annotation_id: str | None = None
    start_char: int | None = None
    end_char: int | None = None


class AnnotationSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    document_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    annotator: str = "damien"
    wrapper_schema_version: int = WRAPPER_SCHEMA_VERSION
    schema_version: int = SCHEMA_VERSION
    pre_selector: PreSelector
    candidates: list[CandidateRecord] = Field(default_factory=list)
    hand_added: list[HandAddedRecord] = Field(default_factory=list)
    cycle_learnings: list[CycleLearning] = Field(default_factory=list)
    baseline: bool = False
    blind_segment: BlindSegment | None = None
    blind_revealed_at: datetime | None = None
    blind_diff_report: dict[str, Any] | None = None
    blind_pending: int = 0
    coverage_pass_completed_at: datetime | None = None
    exported_at: datetime | None = None
    export_slug: str | None = None


class ExportResult(BaseModel):
    jsonl: Path
    ann: Path
    manifest: Path
    readme: Path
    precision: float
    recall_proxy: float
    density: dict[str, Any]


def precision_from_record(records: list[dict[str, Any]]) -> float:
    selected = [r for r in records if r.get("origin") == "pre-selected"]
    kept = sum(r.get("outcome") in ("accepted", "edited") for r in selected)
    deleted = sum(r.get("outcome") == "deleted" for r in selected)
    return kept / (kept + deleted) if kept + deleted else 1.0


def recall_proxy_from_record(records: list[dict[str, Any]]) -> float:
    gold = [r for r in records if r.get("record_type") == "annotation" and not r.get("deleted")]
    hand = sum(r.get("provenance") == "hand-added" for r in gold)
    return 1.0 - hand / len(gold) if gold else 1.0


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("export slug must contain a letter or number")
    return slug


def _validate_unresolved(proposition: Proposition, explicit: bool) -> None:
    if proposition.disposition == Disposition.UNRESOLVED and not explicit:
        raise ValueError("unresolved disposition requires explicit_unresolved=True")


class GoldStore:
    def __init__(self, job_store: JobStore | None = None, export_dir: Path | None = None) -> None:
        self.job_store = job_store or JobStore()
        self.session_dir = self.job_store.base_dir / "gold_sessions"
        self.export_dir = export_dir or Path(__file__).resolve().parents[3] / "eval/gold/propositions"

    def _path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.json"

    async def _save(self, session: AnnotationSession) -> None:
        session.updated_at = datetime.now(timezone.utc)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(self._path(session.session_id), session.model_dump_json(indent=2))
        if session.exported_at is None:
            PROTECTED_JOB_IDS.add(session.job_id)
        else:
            PROTECTED_JOB_IDS.discard(session.job_id)

    async def create_session(
        self,
        job_id: UUID | str,
        document_id: str | None = None,
        pre_selector: PreSelector | dict[str, Any] | None = None,
        annotator: str = "damien",
        baseline: bool = False,
    ) -> AnnotationSession:
        parsed = UUID(str(job_id))
        job = await self.job_store.load(parsed)
        if job is None:
            raise LookupError("job not found")
        selector = PreSelector.model_validate(pre_selector or {"source": "lexicon-only"})
        candidates = job.result.propositions
        if baseline:
            from app.services.proposition.extractor import PropositionExtractor

            selector = PreSelector(
                source="lexicon-only",
                lexicon_version=selector.lexicon_version,
                lexicon_config=selector.lexicon_config,
            )
            candidates = PropositionExtractor().extract(job)
        session = AnnotationSession(
            job_id=str(job.id),
            document_id=document_id or str(job.id),
            annotator=annotator,
            pre_selector=selector,
            baseline=baseline,
            candidates=[CandidateRecord(proposition=p, original=p.model_copy(deep=True)) for p in candidates],
        )
        await self._save(session)
        return session

    async def _load(self, session_id: str) -> AnnotationSession:
        path = self._path(session_id)
        if not path.exists():
            raise LookupError("session not found")
        raw = json.loads(path.read_text(encoding="utf-8"))
        for candidate in raw.get("candidates", []):
            candidate["proposition"] = migrate_proposition_payload(candidate["proposition"])
            candidate["original"] = migrate_proposition_payload(candidate["original"])
        for annotation in raw.get("hand_added", []):
            annotation["proposition"] = migrate_proposition_payload(annotation["proposition"])
        return AnnotationSession.model_validate(raw)

    @staticmethod
    def _intersects(start: int | None, end: int | None, segment: BlindSegment) -> bool:
        return start is not None and end is not None and start < segment.end_char and end > segment.start_char

    def _public_session(self, session: AnnotationSession) -> AnnotationSession:
        public = session.model_copy(deep=True)
        if public.blind_segment is not None and public.blind_revealed_at is None:
            hidden = [
                candidate for candidate in public.candidates
                if self._intersects(
                    candidate.original.start_char, candidate.original.end_char, public.blind_segment
                )
            ]
            public.candidates = [candidate for candidate in public.candidates if candidate not in hidden]
            public.blind_pending = len(hidden)
        else:
            public.blind_pending = 0
        return public

    async def get(self, session_id: str) -> AnnotationSession:
        return self._public_session(await self._load(session_id))

    async def list(self, job_id: str | None = None) -> list[AnnotationSession]:
        sessions = []
        for path in sorted(self.session_dir.glob("*.json")):
            try:
                session = await self.get(path.stem)
            except (ValueError, LookupError):
                continue
            if job_id is None or session.job_id == job_id:
                sessions.append(session)
        return sessions

    async def update(self, session: AnnotationSession) -> AnnotationSession:
        await self._save(session)
        return session

    async def record_candidate_outcome(
        self,
        session_id: str,
        candidate_id: str,
        *,
        outcome: Literal["accepted", "edited", "deleted", "unreviewed"],
        proposition: Proposition | dict[str, Any] | None = None,
        explicit_unresolved: bool = False,
    ) -> AnnotationSession:
        session = await self._load(session_id)
        candidate = next((c for c in session.candidates if c.proposition.id == candidate_id), None)
        if candidate is None:
            raise LookupError("candidate not found")
        current = Proposition.model_validate(proposition) if proposition is not None else candidate.proposition
        if outcome in ("accepted", "edited"):
            _validate_unresolved(current, explicit_unresolved)
        if outcome == "edited":
            boundary = (current.start_char, current.end_char) != (
                candidate.original.start_char, candidate.original.end_char
            )
            current_fields = current.model_dump(exclude={"start_char", "end_char"})
            original_fields = candidate.original.model_dump(exclude={"start_char", "end_char"})
            field = current_fields != original_fields
            candidate.edit_kind = "both" if boundary and field else "boundary" if boundary else "field"
        else:
            candidate.edit_kind = None
        candidate.proposition = current
        candidate.outcome = outcome
        candidate.explicit_unresolved = explicit_unresolved
        await self.update(session)
        return self._public_session(session)

    async def add_hand_added(
        self,
        session_id: str,
        proposition: Proposition | dict[str, Any],
        *,
        explicit_unresolved: bool = False,
    ) -> AnnotationSession:
        session = await self._load(session_id)
        model = Proposition.model_validate(proposition)
        _validate_unresolved(model, explicit_unresolved)
        session.hand_added.append(HandAddedRecord(proposition=model, explicit_unresolved=explicit_unresolved))
        await self.update(session)
        return self._public_session(session)

    async def add_learning(self, session_id: str, **data: Any) -> AnnotationSession:
        session = await self._load(session_id)
        session.cycle_learnings.append(CycleLearning.model_validate(data))
        await self.update(session)
        return self._public_session(session)

    async def set_blind_segment(self, session_id: str, start: int, end: int) -> AnnotationSession:
        session = await self._load(session_id)
        job = await self.job_store.load(UUID(session.job_id))
        text = job.result.canonical_text.full_text if job and job.result.canonical_text else ""
        if start < 0 or end <= start or end > len(text):
            raise ValueError("blind segment boundaries are invalid")
        if session.blind_segment is not None:
            raise ValueError("blind segment is already designated")
        segment = BlindSegment(start_char=start, end_char=end)
        reviewed = [
            candidate for candidate in session.candidates
            if candidate.outcome != "unreviewed"
            and self._intersects(candidate.original.start_char, candidate.original.end_char, segment)
        ]
        if reviewed:
            raise ValueError("blind segment must be annotated unassisted; it contains a reviewed candidate")
        session.blind_segment = segment
        await self.update(session)
        return self._public_session(session)

    async def reveal_blind_segment(self, session_id: str) -> AnnotationSession:
        session = await self._load(session_id)
        if session.blind_segment is None:
            raise ValueError("no blind segment is designated")
        if session.blind_revealed_at is not None:
            return self._public_session(session)
        segment = session.blind_segment
        tools = [
            candidate.original for candidate in session.candidates
            if self._intersects(candidate.original.start_char, candidate.original.end_char, segment)
        ]
        annotations = [
            item.proposition for item in session.hand_added
            if self._intersects(item.proposition.start_char, item.proposition.end_char, segment)
        ]
        unmatched_annotations = list(range(len(annotations)))
        matched_pairs: list[dict[str, Any]] = []
        tool_only: list[dict[str, Any]] = []
        for tool in tools:
            match = next(
                (
                    index for index in unmatched_annotations
                    if annotations[index].start_char < tool.end_char
                    and annotations[index].end_char > tool.start_char
                ),
                None,
            )
            if match is None:
                tool_only.append(tool.model_dump(mode="json"))
                continue
            annotator = annotations[match]
            unmatched_annotations.remove(match)
            matched_pairs.append({
                "tool": tool.model_dump(mode="json"),
                "annotator": annotator.model_dump(mode="json"),
            })
        annotator_only = [annotations[index].model_dump(mode="json") for index in unmatched_annotations]
        matched_count = len(matched_pairs)
        tool_count = len(tools)
        annotator_count = len(annotations)
        session.blind_diff_report = {
            "segment": segment.model_dump(),
            "matched_pairs": matched_pairs,
            "tool_only": tool_only,
            "annotator_only": annotator_only,
            "anchoring_loss": {
                "tool_count": tool_count,
                "annotator_count": annotator_count,
                "matched_count": matched_count,
                "tool_only_count": len(tool_only),
                "annotator_only_count": len(annotator_only),
                "match_fraction": matched_count / tool_count if tool_count else 1.0,
                "tool_miss_fraction": len(tool_only) / tool_count if tool_count else 0.0,
                "annotator_novel_fraction": len(annotator_only) / annotator_count if annotator_count else 0.0,
                "anchoring_loss_fraction": len(tool_only) / tool_count if tool_count else 0.0,
            },
        }
        session.blind_revealed_at = datetime.now(timezone.utc)
        await self.update(session)
        return self._public_session(session)

    async def record_coverage_pass(self, session_id: str) -> AnnotationSession:
        session = await self._load(session_id)
        if session.coverage_pass_completed_at is None:
            session.coverage_pass_completed_at = datetime.now(timezone.utc)
            await self.update(session)
        return self._public_session(session)

    @staticmethod
    def _completeness(session: AnnotationSession) -> dict[str, Any]:
        reasons: list[str] = []
        unreviewed = sum(candidate.outcome == "unreviewed" for candidate in session.candidates)
        if unreviewed:
            reasons.append(f"{unreviewed} candidate(s) remain unreviewed")
        if session.coverage_pass_completed_at is None:
            reasons.append("full-text coverage pass has not been recorded")
        if session.blind_segment is not None and session.blind_revealed_at is None:
            reasons.append("blind segment has not been revealed")
        return {"complete": not reasons, "reasons": reasons}

    async def completeness(self, session_id: str) -> dict[str, Any]:
        return self._completeness(await self._load(session_id))

    def _records(self, session: AnnotationSession) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for candidate in session.candidates:
            base = {
                "record_type": "annotation" if candidate.outcome != "deleted" else "candidate-audit",
                "annotation_id": candidate.proposition.id,
                "document_id": session.document_id,
                "origin": "pre-selected",
                "outcome": candidate.outcome,
                "provenance": "edited" if candidate.outcome == "edited" else "pre-selected-accepted" if candidate.outcome == "accepted" else None,
                "disposition": candidate.proposition.disposition.value,
                "explicit_unresolved": candidate.explicit_unresolved,
                "proposition": candidate.proposition.model_dump(mode="json"),
                "original": candidate.original.model_dump(mode="json"),
                "edit_kind": candidate.edit_kind,
            }
            if candidate.outcome == "deleted":
                base.update({"deleted": True, "audit": "deleted-candidate"})
            records.append(base)
        for item in session.hand_added:
            records.append({
                "record_type": "annotation", "annotation_id": item.proposition.id,
                "document_id": session.document_id, "origin": "hand-added",
                "outcome": "accepted", "provenance": "hand-added", "deleted": False,
                "disposition": item.proposition.disposition.value,
                "explicit_unresolved": item.explicit_unresolved,
                "proposition": item.proposition.model_dump(mode="json"),
            })
        for learning in session.cycle_learnings:
            records.append({"record_type": "cycle-learning", "document_id": session.document_id, **learning.model_dump(mode="json")})
        if session.blind_segment is not None:
            records.append({
                "record_type": "blind-segment",
                "document_id": session.document_id,
                "blind_segment": session.blind_segment.model_dump(),
                "blind_revealed_at": session.blind_revealed_at.isoformat() if session.blind_revealed_at else None,
                "diff_report": session.blind_diff_report,
            })
        return records

    @staticmethod
    def _density(session: AnnotationSession, canonical: CanonicalText | None) -> dict[str, Any]:
        gold = [c.proposition for c in session.candidates if c.outcome in ("accepted", "edited")]
        gold.extend(item.proposition for item in session.hand_added)
        words = len(canonical.full_text.split()) if canonical else 0
        result: dict[str, Any] = {"opinion": len(gold) * 1000 / words if words else 0.0, "word_count": words}
        if canonical and canonical.elements and any(element.section_path for element in canonical.elements):
            sections: dict[str, dict[str, float | int]] = {}
            offset = 0
            for element in canonical.elements:
                start = canonical.full_text.find(element.text, offset)
                if start < 0:
                    continue
                end = start + len(element.text)
                offset = end
                name = " / ".join(element.section_path) or "(unsectioned)"
                bucket = sections.setdefault(name, {"word_count": 0, "gold_count": 0, "density": 0.0})
                bucket["word_count"] += len(element.text.split())
                bucket["gold_count"] += sum(p.start_char is not None and start <= p.start_char < end for p in gold)
            for bucket in sections.values():
                bucket["density"] = bucket["gold_count"] * 1000 / bucket["word_count"] if bucket["word_count"] else 0.0
            result["sections"] = sections
        return result

    async def export(self, session_id: str, slug: str | None = None) -> ExportResult:
        from app.services.export.brat_exporter import BratExporter

        session = await self._load(session_id)
        unreviewed = sum(c.outcome == "unreviewed" for c in session.candidates)
        if unreviewed:
            raise ValueError(f"export refused: {unreviewed} unreviewed candidate(s)")
        job = await self.job_store.load(UUID(session.job_id))
        if job is None:
            raise LookupError("job not found")
        export_slug = _safe_slug(slug or session.document_id)
        records = self._records(session)
        jsonl = self.export_dir / f"{export_slug}.jsonl"
        ann = self.export_dir / f"{export_slug}.ann"
        manifest = self.export_dir / "manifest.json"
        readme = self.export_dir / "README.md"
        _atomic_write(jsonl, "".join(json.dumps(record, sort_keys=True) + "\n" for record in records))
        propositions = [c.proposition for c in session.candidates if c.outcome in ("accepted", "edited")]
        propositions.extend(item.proposition for item in session.hand_added)
        _atomic_write(ann, BratExporter.export_propositions(propositions))
        density = self._density(session, job.result.canonical_text)
        now = datetime.now(timezone.utc)
        manifest_data = {"manifest_schema_version": 1, "opinions": []}
        if manifest.exists():
            try:
                manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        entry = {
            "slug": export_slug, "session_id": session.session_id, "job_id": session.job_id,
            "document_id": session.document_id, "annotator": session.annotator,
            "wrapper_schema_version": session.wrapper_schema_version, "schema_version": session.schema_version,
            "pre_selector": session.pre_selector.model_dump(mode="json"),
            "baseline": session.baseline,
            "blind_segment": session.blind_segment is not None,
            "completeness": self._completeness(session),
            "counts": {name: sum(c.outcome == name for c in session.candidates) for name in ("accepted", "edited", "deleted", "unreviewed")},
            "hand_added_count": len(session.hand_added), "density": density,
            "precision": precision_from_record(records), "recall_proxy": recall_proxy_from_record(records),
            "exported_at": now.isoformat(),
        }
        manifest_data["opinions"] = [item for item in manifest_data.get("opinions", []) if item.get("slug") != export_slug] + [entry]
        _atomic_write(manifest, json.dumps(manifest_data, indent=2, sort_keys=True) + "\n")
        _atomic_write(readme, README)
        session.exported_at, session.export_slug = now, export_slug
        await self._save(session)
        return ExportResult(jsonl=jsonl, ann=ann, manifest=manifest, readme=readme,
                            precision=entry["precision"], recall_proxy=entry["recall_proxy"], density=density)


README = """# Proposition gold records

This directory contains human-reviewed proposition JSONL, brat standoff files, and a cycle manifest.
Gold is non-circular: exported labels come from explicit annotator outcomes, not from pipeline output alone.
Deleted pre-selected candidates remain as audit records so pre-selection precision is computable.

- Recall proxy: `1 - hand-added / total exported gold`.
- Precision: `(accepted + edited) / (accepted + edited + deleted)` over pre-selected candidates.
- Density: exported gold propositions per 1,000 words of normalized canonical text. Deleted candidates and learning-only tags are excluded.
"""
