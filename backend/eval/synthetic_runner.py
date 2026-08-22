"""Deterministic comparison runner for the shared synthetic-items contract.

Stage snapshots are candidate IRI sets immediately after the named stage:
EntityRuler reads ``metadata.ruler_concepts``; Reconciliation reads
``metadata.reconciled_concepts``; Resolution reads
``metadata.resolved_concepts``; and StringMatch reads the native span
annotations materialized by that stage.  They are diagnostic candidate sets,
not necessarily the final committed set.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import sys
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Iterator, Sequence

# Permit ``python backend/eval/synthetic_runner.py`` from the repository root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.models.document import DocumentInput
from app.models.job import Job, JobStatus
from app.pipeline.orchestrator import PipelineOrchestrator, TaskLLMs
from app.pipeline.stages.base import PipelineStage
from app.pipeline.stages.dependency_stage import TripleEnrichmentStage
from app.pipeline.stages.entity_ruler_stage import EntityRulerStage
from app.pipeline.stages.individual_stage import EarlyIndividualStage, LLMIndividualStage
from app.pipeline.stages.ingestion_stage import IngestionStage
from app.pipeline.stages.normalization_stage import NormalizationStage
from app.pipeline.stages.property_stage import EarlyPropertyStage, LLMPropertyStage
from app.pipeline.stages.proposition_stage import EarlyPropositionStage
from app.pipeline.stages.reconciliation_stage import ReconciliationStage
from app.pipeline.stages.resolution_stage import ResolutionStage
from app.pipeline.stages.string_match_stage import StringMatchStage
from app.pipeline.stages.triple_stage import EarlyTripleStage
from app.storage.job_store import JobStore


STAGE_NAMES = ("EntityRuler", "Reconciliation", "Resolution", "StringMatch")
SNAPSHOT_METADATA_KEY = "_synthetic_stage_snapshots"
_ERROR_METADATA_KEY = "_synthetic_stage_errors"
PROVIDER_ENV_KEYS = (
    "FOLIO_ENRICH_OPENAI_API_KEY",
    "FOLIO_ENRICH_ANTHROPIC_API_KEY",
    "FOLIO_ENRICH_GOOGLE_API_KEY",
    "FOLIO_ENRICH_MISTRAL_API_KEY",
    "FOLIO_ENRICH_COHERE_API_KEY",
    "FOLIO_ENRICH_META_LLAMA_API_KEY",
    "FOLIO_ENRICH_GROQ_API_KEY",
    "FOLIO_ENRICH_XAI_API_KEY",
    "FOLIO_ENRICH_GITHUB_MODELS_API_KEY",
)

# Pin every feature flag that can alter the no-LLM concept pipeline or cause
# environment-dependent work.
PINNED_FLAGS: dict[str, Any] = {
    "embedding_disabled": True,
    "contextual_rerank_enabled": False,
    "individual_extraction_enabled": True,
    "individual_regex_only": True,
    "property_extraction_enabled": True,
    "property_regex_only": True,
    "triple_extraction_enabled": True,
    "pos_tagging_enabled": True,
    "pos_confidence_enabled": True,
    "ner_cross_validation_enabled": False,
    "translation_matching_enabled": False,
    "folio_auto_update": False,
    "backup_semantic_filter_enabled": False,
    "proposition_extraction_enabled": False,
}

# These settings are environment-overridable and directly affect deterministic
# candidate selection, ranking, or commitment. Record and actively pin them.
PINNED_SCORING: dict[str, Any] = {
    "max_candidates": 5,
    "skip_backups_for_exact_matches": True,
    "semantic_similarity_threshold": 0.8,
    "pos_concept_mismatch_penalty": 0.15,
    "pos_property_mismatch_penalty": 0.12,
}


def _version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _candidate_iris(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    iris: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            iri = value.get("folio_iri")
            if isinstance(iri, str) and iri:
                iris.add(iri)
            concept = value.get("concept")
            if isinstance(concept, dict):
                iri = concept.get("folio_iri")
                if isinstance(iri, str) and iri:
                    iris.add(iri)
        else:
            iri = getattr(value, "folio_iri", None)
            if isinstance(iri, str) and iri:
                iris.add(iri)
    return sorted(iris)


def _annotation_iris(job: Job, *, committed_only: bool) -> list[str]:
    iris: set[str] = set()
    for annotation in job.result.annotations:
        if committed_only and annotation.state != "confirmed":
            continue
        for concept in annotation.concepts:
            if committed_only and concept.state in {"backup", "rejected", "preliminary"}:
                continue
            if concept.folio_iri:
                iris.add(concept.folio_iri)
    return sorted(iris)


class _SnapshotStage(PipelineStage):
    def __init__(self, stage: PipelineStage, label: str, metadata_key: str | None) -> None:
        self._stage = stage
        self._label = label
        self._metadata_key = metadata_key

    @property
    def name(self) -> str:
        return self._stage.name

    async def execute(self, job: Job) -> Job:
        try:
            job = await self._stage.execute(job)
        except Exception as exc:
            job.result.metadata.setdefault(_ERROR_METADATA_KEY, []).append(
                f"{self.name}: {type(exc).__name__}: {exc}"
            )
            raise
        if self._metadata_key is None:
            iris = _annotation_iris(job, committed_only=False)
        else:
            iris = _candidate_iris(job.result.metadata.get(self._metadata_key, []))
        job.result.metadata.setdefault(SNAPSHOT_METADATA_KEY, {})[self._label] = iris
        return job


def _deterministic_stages() -> list[PipelineStage]:
    """Mirror build_stages(None), with embedding-backed registry paths disabled."""
    return [
        IngestionStage(),
        NormalizationStage(),
        _SnapshotStage(EntityRulerStage(registry_embeddings=False), "EntityRuler", "ruler_concepts"),
        EarlyIndividualStage(),
        EarlyPropertyStage(),
        EarlyPropositionStage(llm=None),
        EarlyTripleStage(),
        _SnapshotStage(ReconciliationStage(registry_embeddings=False), "Reconciliation", "reconciled_concepts"),
        _SnapshotStage(ResolutionStage(registry_embeddings=False), "Resolution", "resolved_concepts"),
        _SnapshotStage(StringMatchStage(), "StringMatch", None),
        LLMIndividualStage(llm=None),
        LLMPropertyStage(llm=None),
        TripleEnrichmentStage(),
    ]


def _make_pipeline(jobs_dir: Path) -> PipelineOrchestrator:
    return PipelineOrchestrator(JobStore(base_dir=jobs_dir), stages=_deterministic_stages())


def _snapshot_pipeline_config(pipeline: PipelineOrchestrator) -> None:
    """Instrument the shipped parallel pipeline without changing its topology."""
    config = pipeline._config
    assert config is not None
    metadata_keys = {
        "entity_ruler": "ruler_concepts",
        "reconciliation": "reconciled_concepts",
        "resolution": "resolved_concepts",
    }

    def wrap(stage: PipelineStage | None) -> PipelineStage | None:
        if stage is None:
            return None
        return _SnapshotStage(stage, stage.name, metadata_keys.get(stage.name))

    config.pre_parallel = [wrap(stage) for stage in config.pre_parallel]  # type: ignore[list-item]
    config.entity_ruler = wrap(config.entity_ruler)
    config.llm_concept = wrap(config.llm_concept)
    config.early_individual = wrap(config.early_individual)
    config.early_property = wrap(config.early_property)
    config.early_proposition = wrap(config.early_proposition)
    config.early_triple = wrap(config.early_triple)
    config.document_type = wrap(config.document_type)
    config.post_parallel = [wrap(stage) for stage in config.post_parallel]  # type: ignore[list-item]


def _make_llm_pipeline(jobs_dir: Path, llm: Any) -> PipelineOrchestrator:
    """Build providers and stages through the same path as the enrich server."""
    task_llms = TaskLLMs.from_settings(fallback=llm)
    pipeline = PipelineOrchestrator(
        JobStore(base_dir=jobs_dir), llm=llm, task_llms=task_llms
    )
    pipeline._synthetic_task_llms = task_llms
    pipeline._synthetic_requires_area_of_law = task_llms.area_of_law is not None
    _snapshot_pipeline_config(pipeline)
    return pipeline


@contextmanager
def _pinned_settings() -> Iterator[None]:
    pinned = {**PINNED_FLAGS, **PINNED_SCORING}
    previous = {name: getattr(settings, name) for name in pinned}
    try:
        for name, value in pinned.items():
            setattr(settings, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(settings, name, value)


def _load_items(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"line {line_number}: blank lines are not allowed")
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"line {line_number}: item must be an object")
            if not isinstance(item.get("item_id"), str) or not item["item_id"]:
                raise ValueError(f"line {line_number}: item_id must be a nonempty string")
            if not isinstance(item.get("text"), str):
                raise ValueError(f"line {line_number}: text must be a string")
            segments = item.get("segments")
            if not isinstance(segments, list) or not all(isinstance(v, str) for v in segments):
                raise ValueError(f"line {line_number}: segments must be a list of strings")
            items.append(item)
    return items


def _header(
    lane: str,
    llm: Any = None,
    *,
    provider_name: str | None = None,
    task_llms: TaskLLMs | None = None,
) -> dict[str, Any]:
    scoring = {
        "max_candidates": settings.max_candidates,
        "skip_backups_for_exact_matches": settings.skip_backups_for_exact_matches,
        "semantic_similarity_threshold": settings.semantic_similarity_threshold,
        "pos_concept_mismatch_penalty": settings.pos_concept_mismatch_penalty,
        "pos_property_mismatch_penalty": settings.pos_property_mismatch_penalty,
    }
    if lane == "deterministic":
        config = {**PINNED_FLAGS, **scoring, "llm_provider": None, "registry_embeddings": False}
    else:
        llm_tasks = {}
        if task_llms is not None:
            for task, provider in vars(task_llms).items():
                if provider is not None:
                    config_task = "property" if task == "property_llm" else task
                    llm_tasks[task] = {
                        "provider": (
                            getattr(settings, f"llm_{config_task}_provider", "")
                            or provider_name
                            or type(provider).__name__
                        ),
                        "model": provider.model,
                    }
        config = {
            "embedding_disabled": settings.embedding_disabled,
            "contextual_rerank_enabled": settings.contextual_rerank_enabled,
            **scoring,
            "llm_provider": provider_name or type(llm).__name__,
            "llm_model": getattr(llm, "model", None),
            "llm_tasks": llm_tasks,
            "registry_embeddings": True,
        }
    return {
        "kind": "synthetic-stack-run",
        "stack": "folio-enrich",
        "lane": lane,
        "folio_resolve_version": _version("folio-resolve"),
        "folio_python_version": _version("folio-python"),
        "config": config,
    }


async def run(
    items_path: Path,
    out_path: Path,
    *,
    lane: str = "deterministic",
    llm: Any = None,
) -> None:
    items = _load_items(items_path)
    rows: list[dict[str, Any]] = []
    settings_context = _pinned_settings() if lane == "deterministic" else nullcontext()
    with settings_context, tempfile.TemporaryDirectory(prefix="folio-enrich-synthetic-") as temp:
        provider_name = None
        if lane == "llm-on":
            if llm is None:
                from app.pipeline.orchestrator import _try_get_llm

                llm = _try_get_llm()
                provider_name = settings.llm_provider
            if llm is None:
                raise RuntimeError("owner-run lane: provider env not configured")
            pipeline = _make_llm_pipeline(Path(temp) / "jobs", llm)
        else:
            pipeline = _make_pipeline(Path(temp) / "jobs")
        header = _header(
            lane,
            llm,
            provider_name=provider_name,
            task_llms=getattr(pipeline, "_synthetic_task_llms", None),
        )
        for item in items:
            job = await pipeline.run(Job(input=DocumentInput(content=item["text"])))
            errors = job.result.metadata.get(_ERROR_METADATA_KEY, [])
            if (
                getattr(pipeline, "_synthetic_requires_area_of_law", False)
                and "areas_of_law" not in job.result.metadata
            ):
                errors = [*errors, "area_of_law: LLM assessment did not complete"]
            if errors or job.status != JobStatus.COMPLETED:
                detail = "; ".join(errors) or job.error or job.status.value
                raise RuntimeError(f"item {item['item_id']}: pipeline failed: {detail}")
            snapshots = job.result.metadata.get(SNAPSHOT_METADATA_KEY, {})
            stage_names = STAGE_NAMES if lane == "deterministic" else tuple(snapshots)
            rows.append({
                "item_id": item["item_id"],
                "iris": _annotation_iris(job, committed_only=True),
                "stages": {name: sorted(set(snapshots.get(name, []))) for name in stage_names},
            })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [header, *rows]
    out_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in payload), encoding="utf-8")


def _provider_env_present() -> bool:
    return bool(os.environ.get("FOLIO_ENRICH_LLM_PROVIDER")) or any(
        os.environ.get(key) for key in PROVIDER_ENV_KEYS
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--lane", choices=("deterministic",), default="deterministic")
    parser.add_argument("--llm-on", action="store_true")
    args = parser.parse_args(argv)
    if args.llm_on:
        if not _provider_env_present():
            parser.error("owner-run lane: provider env not configured")
        args.lane = "llm-on"
    try:
        asyncio.run(run(args.items, args.out, lane=args.lane))
    except Exception as exc:
        parser.exit(1, f"synthetic runner error: {exc}\n")


if __name__ == "__main__":
    main()
