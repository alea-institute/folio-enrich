"""Generate pre-computed demo JSON files by running each exemplar through the pipeline.

Usage:
    cd backend && .venv/bin/python scripts/generate_demos.py
    cd backend && .venv/bin/python scripts/generate_demos.py --check
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.document import DocumentInput, DocumentFormat
from app.models.job import Job, JobStatus
from app.pipeline.orchestrator import PipelineOrchestrator, TaskLLMs
from app.storage.job_store import JobStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = BACKEND_ROOT.parent / "frontend" / "demos"

# Paths whose changes should trigger demo regeneration.
_TRACKED_SOURCE_DIRS = [
    "app/pipeline/stages/",
    "app/services/folio/",
    "app/services/individual/",
    "app/services/property/",
    "app/services/dependency/",
    "app/services/embedding/",
    "app/services/nlp/",
]

_TRACKED_SOURCE_FILES = [
    "app/pipeline/orchestrator.py",
    "app/models/annotation.py",
    "app/models/document.py",
    "app/models/job.py",
    "scripts/demo_documents.py",
    "scripts/generate_demos.py",
]


def get_staleness_info() -> tuple[bool, str]:
    """Check whether demo files are stale relative to pipeline sources.

    Returns (is_stale, reason) — *True* when demos should be regenerated.
    """
    from scripts.demo_documents import DEMO_DOCUMENTS

    expected_slugs = list(DEMO_DOCUMENTS.keys())

    # --- 1. All demo files must exist ---
    missing = [s for s in expected_slugs if not (DEMOS_DIR / f"{s}.json").exists()]
    if missing:
        return True, f"Missing demo files: {', '.join(missing)}"

    # --- 2. Earliest generated_at across all demos ---
    earliest_generated: datetime | None = None
    for slug in expected_slugs:
        demo_path = DEMOS_DIR / f"{slug}.json"
        try:
            data = json.loads(demo_path.read_text())
            ts = datetime.fromisoformat(data["demo"]["generated_at"])
            if earliest_generated is None or ts < earliest_generated:
                earliest_generated = ts
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            return True, f"Cannot parse {slug}.json: {exc}"

    if earliest_generated is None:
        return True, "No valid generated_at timestamps found in demo files"

    # --- 3. Latest mtime across tracked source dirs/files ---
    latest_source_mtime = 0.0
    latest_source_path = ""

    for rel_dir in _TRACKED_SOURCE_DIRS:
        dir_path = BACKEND_ROOT / rel_dir
        if not dir_path.is_dir():
            continue
        for p in dir_path.rglob("*.py"):
            mt = p.stat().st_mtime
            if mt > latest_source_mtime:
                latest_source_mtime = mt
                latest_source_path = str(p.relative_to(BACKEND_ROOT))

    for rel_file in _TRACKED_SOURCE_FILES:
        file_path = BACKEND_ROOT / rel_file
        if not file_path.is_file():
            continue
        mt = file_path.stat().st_mtime
        if mt > latest_source_mtime:
            latest_source_mtime = mt
            latest_source_path = str(file_path.relative_to(BACKEND_ROOT))

    # --- 4. OWL cache file ---
    try:
        from app.services.folio.owl_cache import _CACHE_FILE

        if _CACHE_FILE.exists():
            mt = _CACHE_FILE.stat().st_mtime
            if mt > latest_source_mtime:
                latest_source_mtime = mt
                latest_source_path = str(_CACHE_FILE)
    except ImportError:
        pass  # Non-fatal — skip OWL cache check

    # --- 5. Compare ---
    if latest_source_mtime == 0.0:
        return False, "No tracked source files found — assuming fresh"

    latest_source_dt = datetime.fromtimestamp(latest_source_mtime, tz=timezone.utc)
    if latest_source_dt > earliest_generated:
        delta = latest_source_dt - earliest_generated
        return True, (
            f"Source '{latest_source_path}' modified {delta} after "
            f"earliest demo timestamp ({earliest_generated.isoformat()})"
        )

    return False, "All demos are up-to-date"


async def init_services() -> None:
    """Initialize FOLIO ontology and embedding index (mirrors app lifespan)."""
    from app.services.folio.owl_cache import ensure_owl_fresh
    from app.services.folio.folio_service import FolioService
    from app.services.embedding.service import EmbeddingService

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, ensure_owl_fresh)

    folio_service = FolioService.get_instance()
    embedding_service = EmbeddingService.get_instance()
    await loop.run_in_executor(None, embedding_service.index_folio_labels, folio_service)
    logger.info("Services initialized — %d embedding vectors", embedding_service.index_size)

    # Build FAISS index (optional — skip if it fails)
    try:
        from app.services.embedding.service import build_embedding_index
        await loop.run_in_executor(None, build_embedding_index, folio_service)
    except Exception as e:
        logger.warning("FAISS index build failed (non-fatal): %s", e)


def build_cache_payload(job: Job, doc_text: str) -> dict:
    """Build the cache shape that matches frontend cacheState() format."""
    job_dict = json.loads(job.model_dump_json())
    return {
        "jobId": str(job.id),
        "job": job_dict,
        "annotations": job_dict.get("result", {}).get("annotations", []),
        "individuals": job_dict.get("result", {}).get("individuals", []),
        "properties": job_dict.get("result", {}).get("properties", []),
        "normalizedText": job.result.canonical_text.full_text if job.result.canonical_text else doc_text,
        "activity": [],
        "docInput": doc_text,
        "filename": None,
    }


async def generate_demo(slug: str, doc_info: dict, tmp_dir: Path) -> None:
    """Run one document through the pipeline and save demo JSON."""
    logger.info("Generating demo: %s (%s)", slug, doc_info["title"])

    # Create job
    job = Job(
        input=DocumentInput(content=doc_info["text"], format=DocumentFormat.PLAIN_TEXT),
    )

    # Use temp job store
    job_store = JobStore(base_dir=tmp_dir)
    await job_store.save(job)

    # Build orchestrator (no LLM — regex/rule-based only for reproducibility)
    orchestrator = PipelineOrchestrator(
        job_store=job_store,
        llm=None,
        task_llms=TaskLLMs(),
    )

    # Run pipeline
    job = await orchestrator.run(job)

    if job.status != JobStatus.COMPLETED:
        logger.error("Demo %s failed: %s", slug, job.error)
        return

    # Build demo JSON
    cache = build_cache_payload(job, doc_info["text"])
    demo_json = {
        "demo": {
            "name": slug,
            "title": doc_info["title"],
            "description": doc_info["description"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "cache": cache,
    }

    # Write to frontend/demos/
    out_path = DEMOS_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(demo_json, indent=2, default=str))

    ann_count = len(job.result.annotations)
    ind_count = len(job.result.individuals)
    prop_count = len(job.result.properties)
    triple_count = len(job.result.triples)
    logger.info(
        "  %s: %d annotations, %d individuals, %d properties, %d triples",
        slug, ann_count, ind_count, prop_count, triple_count,
    )


async def main() -> None:
    from scripts.demo_documents import DEMO_DOCUMENTS

    DEMOS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing FOLIO services...")
    await init_services()

    with tempfile.TemporaryDirectory(prefix="folio_demo_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for slug, doc_info in DEMO_DOCUMENTS.items():
            await generate_demo(slug, doc_info, tmp_path)

    logger.info("Done — %d demo files written to %s", len(DEMO_DOCUMENTS), DEMOS_DIR)


if __name__ == "__main__":
    if "--check" in sys.argv:
        stale, reason = get_staleness_info()
        print(f"{'STALE' if stale else 'OK'}: {reason}")
        sys.exit(1 if stale else 0)
    asyncio.run(main())
