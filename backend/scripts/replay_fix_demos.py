"""Replay re-bake: refresh baked demo concepts against the current deterministic
pipeline WITHOUT re-calling the LLM.

Why: the "Agreement" -> "License (Agreement)" precision fix lives entirely in the
deterministic concept path (label index + EntityRuler + reconciliation + resolution
+ deterministic individual class-link resolution). The LLM-identified content in the
demos (llm_concepts, individuals, properties, triples) is unchanged by the fix and is
preserved verbatim. So we reconstruct each baked Job, re-run only the concept stages
(feeding the demo's preserved metadata.llm_concepts into reconciliation), re-resolve
individual class-link IRIs, refresh triple cross-links, and rewrite the demo.

Embeddings are loaded from the on-disk cache (keyed by the unchanged OWL hash), so the
semantic ruler / embedding-context scoring are identical to the original bake — the
ONLY changes are from the deterministic label-index fix.

Usage:
  cd backend && .venv/bin/python scripts/replay_fix_demos.py            # all demos
  cd backend && .venv/bin/python scripts/replay_fix_demos.py --only nda # one demo
  cd backend && .venv/bin/python scripts/replay_fix_demos.py --dry-run  # report only
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("replay")
logger.setLevel(logging.INFO)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = BACKEND_ROOT.parent / "frontend" / "demos"


def _arg(flag: str) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    return None


async def _init_services():
    from app.services.folio.owl_cache import ensure_owl_fresh, get_owl_content_hash
    from app.services.folio.folio_service import FolioService
    from app.services.embedding.service import EmbeddingService

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, ensure_owl_fresh)
    folio = FolioService.get_instance()
    folio.get_all_labels()
    folio.get_all_labels_multi()
    owl_hash = get_owl_content_hash()
    emb = EmbeddingService.get_instance()
    # Loads the cached label embeddings (frozen to the original bake's OWL hash).
    await loop.run_in_executor(None, emb.index_folio_labels, folio, owl_hash)
    logger.info("Services ready — %d embedding vectors (owl %s)", emb.index_size, owl_hash)
    return folio, emb


def _concept_summary(job) -> dict:
    """IRI-per-Agreement-span + counts, for before/after comparison."""
    agree_to = {}
    for a in job.result.annotations:
        txt = (a.span.text if a.span else "") or ""
        if txt.lower() == "agreement":
            primary = next((c for c in a.concepts if c.state == "confirmed"), None) or (
                a.concepts[0] if a.concepts else None)
            if primary:
                agree_to[a.span.start] = primary.folio_iri.rsplit("/", 1)[-1]
    return {
        "annotations": len(job.result.annotations),
        "individuals": len(job.result.individuals),
        "properties": len(job.result.properties),
        "triples": len(job.result.triples),
        "agreement_spans": agree_to,
    }


async def replay_one(slug: str, folio, emb, dry_run: bool) -> bool:
    """Recompute one demo's deterministic concepts. Returns True if it changed."""
    from app.models.job import Job
    from app.pipeline.stages.entity_ruler_stage import EntityRulerStage
    from app.pipeline.stages.reconciliation_stage import ReconciliationStage
    from app.pipeline.stages.resolution_stage import ResolutionStage
    from app.pipeline.stages.string_match_stage import StringMatchStage
    from app.pipeline.stages.dependency_stage import TripleEnrichmentStage
    from app.pipeline.stages.individual_stage import _resolve_class_link_iris

    path = DEMOS_DIR / f"{slug}.json"
    raw = json.loads(path.read_text())
    job = Job.model_validate(raw["cache"]["job"])
    before = _concept_summary(job)

    # Reset concept annotations so the semantic ruler's "known spans" starts clean
    # (mirrors the original bake, where EntityRuler ran first). metadata.llm_concepts
    # is preserved and consumed by ReconciliationStage.
    job.result.annotations = []

    await EntityRulerStage(embedding_service=emb).execute(job)
    await ReconciliationStage(embedding_service=emb).execute(job)
    await ResolutionStage(embedding_service=emb).execute(job)
    # ContextualRerank is default-disabled; BranchJudge needs an LLM (skipped — it only
    # assigns branches to branch-less concepts, which the ontology already supplies here).
    await StringMatchStage().execute(job)

    # Deterministic individual class-link IRIs (reuses the preserved individuals).
    _resolve_class_link_iris(job.result.individuals, folio)
    # Refresh triple cross-links to the (possibly changed) concept/individual IRIs.
    try:
        await TripleEnrichmentStage().execute(job)
    except Exception:
        logger.warning("  [%s] triple enrichment skipped", slug, exc_info=False)

    after = _concept_summary(job)
    changed = before["agreement_spans"] != after["agreement_spans"] or \
        before["annotations"] != after["annotations"]

    # Report
    fixed = sum(1 for k, v in after["agreement_spans"].items()
                if before["agreement_spans"].get(k) != v)
    logger.info(
        "  [%s] annotations %d->%d | individuals %d (kept) | properties %d (kept) | "
        "triples %d | agreement-spans changed: %d",
        slug, before["annotations"], after["annotations"], after["individuals"],
        after["properties"], after["triples"], fixed,
    )

    if changed and not dry_run:
        from scripts.generate_demos import build_cache_payload
        raw["cache"] = build_cache_payload(job, raw["cache"].get("docInput", ""))
        # Preserve original demo wrapper (name/title/description); note the replay.
        raw.setdefault("demo", {})["replayed_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()
        path.write_text(json.dumps(raw, separators=(",", ":"), default=str))
    return changed


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    only = _arg("--only")
    folio, emb = await _init_services()

    from scripts.demo_documents import DEMO_DOCUMENTS
    slugs = [only] if only else list(DEMO_DOCUMENTS.keys())

    logger.info("Replaying %d demo(s)%s\n", len(slugs), " [DRY RUN]" if dry_run else "")
    changed_slugs = []
    for slug in slugs:
        try:
            if await replay_one(slug, folio, emb, dry_run):
                changed_slugs.append(slug)
        except Exception:
            logger.exception("  [%s] FAILED", slug)

    logger.info("\nChanged %d/%d demos: %s", len(changed_slugs), len(slugs),
                ", ".join(changed_slugs) or "(none)")

    if changed_slugs and not dry_run:
        from scripts.generate_demos import _compute_pipeline_hash
        ph = _compute_pipeline_hash()
        if ph:
            (DEMOS_DIR / ".pipeline-version").write_text(ph)
            logger.info("Updated .pipeline-version -> %s", ph)


if __name__ == "__main__":
    asyncio.run(main())
