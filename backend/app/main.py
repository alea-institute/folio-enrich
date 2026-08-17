import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import concepts, enrich, export, feedback, folio_update, gold, health, ollama, ontologies, settings, synthetic
from app.config import settings as app_settings
from app.middleware.error_handler import register_error_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import SecurityMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def _index_folio_embeddings() -> None:
    """Pre-compute FOLIO label embeddings at startup (blocks startup until ready)."""
    try:
        from app.services.folio.owl_cache import ensure_owl_fresh, get_owl_content_hash
        from app.services.folio.folio_service import FolioService
        from app.services.embedding.service import EmbeddingService, build_embedding_index
        from app.services.ontology.registry import get_registry

        # Ensure OWL cache is fresh before FOLIO init reads it
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ensure_owl_fresh)

        owl_hash = get_owl_content_hash()

        registry = get_registry()
        default_id = registry.default_id
        folio_service = FolioService.get_instance()
        # Build ONLY the default (FOLIO) embedding service via the registry — using
        # the shared provider and the registry's per-ontology cache. Canon (and any
        # other ontology) stays lazy: a FOLIO-only deploy pays no Canon cost here.
        # Run the heavy encoding in a thread to avoid blocking the event loop.
        embedding_service = await loop.run_in_executor(
            None, registry.get_embedding_service, default_id,
        )
        # Seed the legacy singleton so EmbeddingService.get_instance() callers
        # (health route, OWL updater re-index) share the registry-owned FOLIO service.
        EmbeddingService._instance = embedding_service
        logger.info("FOLIO embedding index ready (%d vectors)", embedding_service.index_size)
        # Also build the FAISS-backed index for semantic search (FOLIO-only, unchanged)
        await loop.run_in_executor(None, build_embedding_index, folio_service, owl_hash)
    except Exception:
        logger.warning("Failed to pre-compute FOLIO embeddings — semantic features disabled", exc_info=True)


async def _periodic_job_cleanup() -> None:
    """Periodically clean up expired jobs."""
    from app.storage.job_store import JobStore

    store = JobStore()
    while True:
        try:
            deleted = await store.cleanup_expired()
            if deleted:
                logger.info("Cleaned up %d expired jobs", deleted)
        except Exception:
            logger.warning("Job cleanup failed", exc_info=True)
        await asyncio.sleep(3600)  # Every hour


async def _periodic_owl_update_check() -> None:
    """Periodically check for and apply FOLIO OWL updates."""
    from app.services.folio.owl_updater import OWLUpdateManager

    manager = OWLUpdateManager.get_instance()
    while True:
        interval = app_settings.folio_update_check_interval_hours * 3600
        await asyncio.sleep(interval)
        if not app_settings.folio_auto_update:
            continue
        try:
            result = await manager.check_and_apply()
            if result:
                logger.info("FOLIO ontology auto-updated: %d → %d concepts",
                            result.get("concepts_before", 0),
                            result.get("concepts_after", 0))
        except Exception:
            logger.warning("FOLIO auto-update failed", exc_info=True)


async def _manage_ollama() -> None:
    """Detect and optionally start Ollama at startup."""
    if not (app_settings.ollama_auto_manage and app_settings.llm_provider == "ollama"):
        return

    try:
        from app.services.ollama.manager import OllamaManager
        manager = OllamaManager.get_instance()
        info = await manager.detect()

        if info.status.value == "running":
            logger.info("Ollama already running (v%s) with %d model(s)", info.version, len(info.models))
        elif info.status.value == "installed":
            logger.info("Ollama installed — starting server...")
            started = await manager.start()
            if started:
                logger.info("Ollama server started")
            else:
                logger.warning("Failed to start Ollama server — run setup via Settings")
        else:
            logger.warning("Ollama not installed — run setup via Settings or POST /ollama/setup")
    except Exception:
        logger.warning("Ollama auto-management failed", exc_info=True)


async def _stop_ollama() -> None:
    """Stop managed Ollama process on shutdown."""
    if not (app_settings.ollama_auto_manage and app_settings.llm_provider == "ollama"):
        return
    try:
        from app.services.ollama.manager import OllamaManager
        manager = OllamaManager.get_instance()
        await manager.stop()
    except Exception:
        logger.warning("Failed to stop Ollama", exc_info=True)


def _warn_insecure_admin_config() -> None:
    """A public deploy (require_user_api_key) with no admin_token leaves the
    mutating OWL-update routes (fetch/reload/rollback) open — warn loudly."""
    if app_settings.require_user_api_key and not app_settings.admin_token:
        logger.warning(
            "SECURITY: require_user_api_key is set (public posture) but admin_token "
            "is empty — /folio/update/{check,apply,rollback} are UNAUTHENTICATED. "
            "Set FOLIO_ENRICH_ADMIN_TOKEN to gate them.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_insecure_admin_config()

    # Startup: detect/start Ollama if configured
    await _manage_ollama()

    # Startup: eager-load FOLIO ontology and embedding index before accepting requests
    logger.info("Loading FOLIO ontology and building embedding index...")
    await _index_folio_embeddings()

    # Own the ontology registry lifecycle at the app level and expose it to request
    # handlers via request.app.state. The module-global registry remains the
    # accessor source of truth (get_registry / FolioService.get_instance); this is
    # an additive reference, not a migration of the ~24 call sites.
    try:
        from app.services.ontology.registry import get_registry

        registry = get_registry()
        app.state.ontology_registry = registry
        app.state.default_ontology = registry.default_id
    except Exception:
        logger.warning("Could not attach ontology registry to app.state", exc_info=True)

    # Seed pre-baked demo jobs so demo-mode exports resolve server-side
    try:
        from app.services.demo_seed import seed_demo_jobs
        await seed_demo_jobs()
    except Exception:
        logger.warning("Demo job seeding failed (exports in demo mode may 404)", exc_info=True)

    # Reconcile jobs orphaned by the previous process: their pipeline tasks
    # died with that process but their files are still non-terminal, so they
    # would keep counting toward max_concurrent_jobs ("Too many concurrent
    # jobs"). Fail them so the active count starts clean after every restart.
    try:
        from app.storage.job_store import JobStore
        await JobStore().fail_orphaned_jobs()
    except Exception:
        logger.warning("Orphaned-job reconciliation failed", exc_info=True)

    cleanup_task = asyncio.create_task(_periodic_job_cleanup())
    owl_update_task = asyncio.create_task(_periodic_owl_update_check())
    yield
    # Shutdown
    cleanup_task.cancel()
    owl_update_task.cancel()
    await _stop_ollama()


app = FastAPI(title=app_settings.app_name, version="0.4.11", lifespan=lifespan)

# Middleware (order matters: outermost first)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=app_settings.rate_limit_requests,
    window_seconds=app_settings.rate_limit_window,
)
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
register_error_handlers(app)

# Routes
app.include_router(health.router)
app.include_router(enrich.router)
app.include_router(export.router)
app.include_router(synthetic.router)
app.include_router(concepts.router)
app.include_router(feedback.router)
app.include_router(gold.router)
app.include_router(settings.router)
app.include_router(ollama.router)
app.include_router(folio_update.router)
app.include_router(ontologies.router)

# Serve frontend
_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if _frontend_dir.is_dir():
    @app.get("/", include_in_schema=False)
    async def _serve_index():
        # no-cache: the browser must revalidate the HTML on every load, so a new
        # deploy shows up immediately without a hard refresh (the ETag still lets
        # unchanged content return a cheap 304).
        return FileResponse(_frontend_dir / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.svg", include_in_schema=False)
    async def _serve_favicon_svg():
        return FileResponse(_frontend_dir / "favicon.svg", media_type="image/svg+xml")

    @app.get("/favicon.ico", include_in_schema=False)
    async def _serve_favicon_ico():
        return FileResponse(_frontend_dir / "favicon.svg", media_type="image/svg+xml")

    app.mount("/static", StaticFiles(directory=_frontend_dir), name="frontend")
