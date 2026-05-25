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
    "app/services/concept/",
    "app/services/llm/",
]

# Only pipeline code that actually affects enrichment OUTPUT is mtime-tracked. The
# generator scripts (generate_demos/demo_documents/extract_exemplars) are scaffolding and
# the exemplar text + ontology are content-hashed instead (see .owl-version/.samples-version),
# so editing the generator or unrelated index.html UI no longer false-positives staleness.
_TRACKED_SOURCE_FILES = [
    "app/pipeline/orchestrator.py",
    "app/models/annotation.py",
    "app/models/document.py",
    "app/models/job.py",
]


def _compute_samples_hash() -> str | None:
    """Stable hash of the 22 exemplar source texts (None if Node unavailable)."""
    try:
        import hashlib

        from scripts.extract_exemplars import extract_exemplar_texts

        texts = extract_exemplar_texts()
        blob = json.dumps(texts, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
    except Exception:
        return None


def _compute_pipeline_hash() -> str | None:
    """Content hash of enrichment-affecting pipeline code.

    Hashing content (not mtime) makes freshness robust: app startup, ``git checkout``,
    ``git merge``, and ``git pull`` all bump file mtimes without changing behavior, which
    made the old mtime comparison false-positive demos as stale.
    """
    try:
        import hashlib

        files: list[Path] = []
        for rel_dir in _TRACKED_SOURCE_DIRS:
            d = BACKEND_ROOT / rel_dir
            if d.is_dir():
                files.extend(d.rglob("*.py"))
        for rel_file in _TRACKED_SOURCE_FILES:
            f = BACKEND_ROOT / rel_file
            if f.is_file():
                files.append(f)

        h = hashlib.sha256()
        for p in sorted(set(files), key=lambda x: str(x)):
            h.update(str(p.relative_to(BACKEND_ROOT)).encode("utf-8"))
            h.update(p.read_bytes())
        return h.hexdigest()[:16]
    except Exception:
        return None


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

    # Freshness is purely content-based (OWL + exemplar text + pipeline code hashes). The
    # previous mtime approach false-positived because app startup and git operations bump
    # file mtimes without changing behavior.

    # --- 4. OWL ontology content version ---
    try:
        from app.services.folio.owl_cache import get_owl_content_hash

        sidecar = DEMOS_DIR / ".owl-version"
        if sidecar.exists():
            gen_hash = sidecar.read_text().strip()
            cur_hash = get_owl_content_hash()
            if gen_hash and cur_hash and gen_hash != cur_hash:
                return True, (
                    f"FOLIO ontology changed since generation "
                    f"(generated against {gen_hash}, current {cur_hash})"
                )
    except Exception:
        pass  # Non-fatal — skip OWL version check

    # --- 4b. Exemplar source text version (content hash, not index.html mtime) ---
    sidecar = DEMOS_DIR / ".samples-version"
    if sidecar.exists():
        gen_hash = sidecar.read_text().strip()
        cur_hash = _compute_samples_hash()
        if gen_hash and cur_hash and gen_hash != cur_hash:
            return True, "Exemplar source text changed since generation (SAMPLES edited)"

    # --- 5. Pipeline code version (content hash — robust to mtime/git touches) ---
    sidecar = DEMOS_DIR / ".pipeline-version"
    if sidecar.exists():
        gen_hash = sidecar.read_text().strip()
        cur_hash = _compute_pipeline_hash()
        if gen_hash and cur_hash and gen_hash != cur_hash:
            return True, "Pipeline code changed since generation"

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


def build_generation_llm(provider_name: str | None, model: str | None, explicit_key: str | None):
    """Build an LLM provider for demo generation (mirrors the /enrich request path).

    Defaults to the app's configured provider (``settings.llm_provider`` = google →
    Gemini 3 Flash). ``model`` left empty lets each provider resolve its own default —
    never hardcode a provider-specific model id here. Raises if a required key is absent.
    """
    from app.config import settings
    from app.services.llm.registry import REQUIRES_API_KEY, get_provider
    from app.api.routes.settings import _get_api_key_for_provider
    from app.models.llm_models import LLMProviderType

    provider_name = provider_name or settings.llm_provider
    model = model if model is not None else settings.llm_model

    normalized = provider_name.replace("-", "_")
    if normalized == "lm_studio":
        normalized = "lmstudio"
    provider_type = LLMProviderType(normalized)

    api_key = _get_api_key_for_provider(provider_type, explicit_key)
    if REQUIRES_API_KEY.get(provider_type, True) and not api_key:
        env_hint = f"FOLIO_ENRICH_{provider_name.upper()}_API_KEY"
        raise SystemExit(
            f"No API key for provider '{provider_name}'. Set {env_hint} (or pass --api-key) "
            "before generating LLM demos."
        )

    return get_provider(provider_type, api_key=api_key, model=model or "")


def build_cache_payload(job: Job, doc_text: str) -> dict:
    """Build the demo cache payload.

    annotations/individuals/properties/triples are NOT duplicated at the top level —
    they live in ``job.result`` and the frontend derives them from there on hydrate.
    (Duplicating them ~doubled demo file size.)
    """
    job_dict = json.loads(job.model_dump_json())
    return {
        "jobId": str(job.id),
        "job": job_dict,
        "normalizedText": job.result.canonical_text.full_text if job.result.canonical_text else doc_text,
        "activity": [],
        "docInput": doc_text,
        "filename": None,
    }


async def generate_demo(slug: str, doc_info: dict, tmp_dir: Path, llm, task_llms: TaskLLMs) -> None:
    """Run one document through the pipeline and save demo JSON."""
    logger.info("Generating demo: %s (%s)", slug, doc_info["title"])

    # Create job
    job = Job(
        input=DocumentInput(content=doc_info["text"], format=DocumentFormat.PLAIN_TEXT),
    )

    # Use temp job store
    job_store = JobStore(base_dir=tmp_dir)
    await job_store.save(job)

    # Build orchestrator with the full LLM pipeline (per-task LLMs + fallback)
    orchestrator = PipelineOrchestrator(
        job_store=job_store,
        llm=llm,
        task_llms=task_llms,
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

    # Write to frontend/demos/ (compact — these are machine-served, not hand-edited)
    out_path = DEMOS_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(demo_json, separators=(",", ":"), default=str))

    ann_count = len(job.result.annotations)
    ind_count = len(job.result.individuals)
    prop_count = len(job.result.properties)
    triple_count = len(job.result.triples)
    logger.info(
        "  %s: %d annotations, %d individuals, %d properties, %d triples",
        slug, ann_count, ind_count, prop_count, triple_count,
    )


def _arg_value(flag: str) -> str | None:
    """Read ``--flag value`` from argv, or None if absent."""
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


async def main() -> None:
    from scripts.demo_documents import load_demo_documents

    DEMOS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Resolve LLM config (default: app provider = google / Gemini 3 Flash) ---
    use_llm = "--no-llm" not in sys.argv
    if use_llm:
        provider = _arg_value("--provider")
        model = _arg_value("--model")
        api_key = _arg_value("--api-key")
        llm = build_generation_llm(provider, model, api_key)
        task_llms = TaskLLMs.from_settings(fallback=llm)
        logger.info("LLM generation ENABLED (provider=%s, model=%s)",
                    provider or "default", model or "default")
    else:
        llm = None
        task_llms = TaskLLMs()
        logger.info("LLM generation DISABLED (--no-llm): rule-based only")

    # --- Resolve which exemplars to generate ---
    only = _arg_value("--only")
    docs = load_demo_documents()
    if only:
        if only not in docs:
            raise SystemExit(f"--only '{only}' is not a known exemplar slug. Choices: {', '.join(docs)}")
        docs = {only: docs[only]}

    logger.info("Initializing FOLIO services...")
    await init_services()

    with tempfile.TemporaryDirectory(prefix="folio_demo_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for slug, doc_info in docs.items():
            await generate_demo(slug, doc_info, tmp_path, llm, task_llms)

    # Record the input versions these demos were generated against (freshness check).
    try:
        from app.services.folio.owl_cache import get_owl_content_hash
        (DEMOS_DIR / ".owl-version").write_text(get_owl_content_hash())
    except Exception:
        logger.warning("Could not write .owl-version sidecar", exc_info=True)
    samples_hash = _compute_samples_hash()
    if samples_hash:
        (DEMOS_DIR / ".samples-version").write_text(samples_hash)
    pipeline_hash = _compute_pipeline_hash()
    if pipeline_hash:
        (DEMOS_DIR / ".pipeline-version").write_text(pipeline_hash)

    logger.info("Done — %d demo file(s) written to %s", len(docs), DEMOS_DIR)


if __name__ == "__main__":
    if "--check" in sys.argv:
        stale, reason = get_staleness_info()
        print(f"{'STALE' if stale else 'OK'}: {reason}")
        sys.exit(1 if stale else 0)
    asyncio.run(main())
