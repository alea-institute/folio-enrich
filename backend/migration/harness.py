#!/usr/bin/env python3
"""Golden-baseline harness for the folio-enrich -> folio-resolve migration.

Runs the committed synthetic corpus (migration/corpus.json) through folio-enrich's
DETERMINISTIC matching seams and writes a capture file. Rerun before and after the
Stage 1 internals swap; migration/compare.py buckets the delta.

Seams exercised (all deterministic, $0 LLM spend, no embeddings):
  1. label_resolution  -> ConceptResolver.resolve / resolve_multi  (the search.py fork)
  2. entity_ruler      -> FOLIOEntityRuler.find_matches            (exact/alias/lemma matching)
  3. reconciler        -> Reconciler.reconcile                     (ruler+LLM merge, fixed inputs)

Score-scale note: ConceptResolver.resolve() returns confidence in 0-1 (multi_strategy_search
emits 0-100, the resolver divides by 100). The raw search score is 0-100. Both are recorded.

Usage:
    .venv/bin/python migration/harness.py --out baseline
    .venv/bin/python migration/harness.py --out candidate

Writes migration/captures/<out>.json (and pins the corpus content hash into it).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Run from backend/: make `app` importable regardless of cwd.
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

MIGRATION = Path(__file__).resolve().parent
CORPUS_PATH = MIGRATION / "corpus.json"
CAPTURES_DIR = MIGRATION / "captures"


def _corpus_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _iri_hash(iri: str | None) -> str:
    return iri.rsplit("/", 1)[-1] if iri else ""


def _round(x: float | None) -> float | None:
    return round(x, 4) if isinstance(x, (int, float)) else x


def run_label_resolution(corpus: dict) -> list[dict]:
    from app.services.folio.resolver import ConceptResolver

    # No embedding service -> deterministic search-only scoring.
    resolver = ConceptResolver()
    out: list[dict] = []
    for item in corpus.get("label_resolution", []):
        text = item["text"]
        resolved = resolver.resolve(concept_text=text, source="harness")
        primary = None
        if resolved is not None:
            fc = resolved.folio_concept
            primary = {
                "iri": fc.iri,
                "iri_hash": _iri_hash(fc.iri),
                "label": fc.preferred_label,
                "branch": fc.branch,
                "branches": list(resolved.branches),
                "confidence_0_1": _round(resolved.confidence),
                "source": resolved.source,
            }
        # resolve_multi exposes the ranked candidate set (the search fork's top-N).
        multi = resolver.resolve_multi(concept_text=text, max_candidates=5)
        candidates = sorted(
            (
                {
                    "iri": r.folio_concept.iri,
                    "label": r.folio_concept.preferred_label,
                    "branch": r.folio_concept.branch,
                    "confidence_0_1": _round(r.confidence),
                }
                for r in multi
            ),
            key=lambda c: (-(c["confidence_0_1"] or 0.0), c["iri"]),
        )
        out.append(
            {
                "id": item["id"],
                "text": text,
                "category": item["category"],
                "extraction_path": "concept_resolver.resolve",
                "primary": primary,
                "candidates": candidates,
            }
        )
    return out


def run_entity_ruler(corpus: dict) -> list[dict]:
    from app.services.entity_ruler.ruler import FOLIOEntityRuler
    from app.services.folio.folio_service import FolioService

    service = FolioService.get_instance()
    labels = service.get_all_labels()
    ruler = FOLIOEntityRuler()
    ruler.load_patterns(labels)

    out: list[dict] = []
    for doc in corpus.get("entity_ruler_docs", []):
        matches = ruler.find_matches(doc["text"])
        rows = sorted(
            (
                {
                    "text": m.text,
                    "start": m.start_char,
                    "end": m.end_char,
                    "iri": m.entity_id,
                    "iri_hash": _iri_hash(m.entity_id),
                    "match_type": m.match_type,
                }
                for m in matches
            ),
            key=lambda r: (r["start"], r["end"], r["iri"]),
        )
        out.append(
            {
                "id": doc["id"],
                "text": doc["text"],
                "category": doc["category"],
                "extraction_path": "entity_ruler.find_matches",
                "matches": rows,
            }
        )
    return out


def run_reconciler(corpus: dict) -> list[dict]:
    from app.models.annotation import ConceptMatch
    from app.services.reconciliation.reconciler import Reconciler

    reconciler = Reconciler()  # no embedding service -> deterministic 3-pass merge
    out: list[dict] = []
    for case in corpus.get("reconciler_cases", []):
        ruler = [ConceptMatch(**c) for c in case.get("ruler", [])]
        llm = [ConceptMatch(**c) for c in case.get("llm", [])]
        results = reconciler.reconcile(ruler, llm)
        rows = sorted(
            (
                {
                    "concept_text": r.concept.concept_text,
                    "iri": r.concept.folio_iri or "",
                    "confidence": _round(r.concept.confidence),
                    "branches": list(r.concept.branches),
                    "source": r.concept.source,
                    "category": r.category,
                }
                for r in results
            ),
            key=lambda r: (r["category"], r["concept_text"], r["iri"]),
        )
        out.append({"id": case["id"], "extraction_path": "reconciler.reconcile", "results": rows})
    return out


def _environment() -> dict:
    env: dict = {}
    try:
        import importlib.metadata as m

        env["folio_python_version"] = m.version("folio-python")
    except Exception:
        env["folio_python_version"] = "unknown"
    try:
        import folio_resolve  # noqa: F401

        env["folio_resolve_present"] = True
        env["folio_resolve_version"] = getattr(folio_resolve, "__version__", "unknown")
    except Exception:
        env["folio_resolve_present"] = False
    try:
        from app.services.folio.folio_service import FolioService

        env["folio_concept_count"] = FolioService.get_instance().get_concept_count()
    except Exception:
        env["folio_concept_count"] = None
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="capture name, e.g. baseline / candidate")
    args = ap.parse_args()

    raw = CORPUS_PATH.read_bytes()
    corpus = json.loads(raw)

    capture = {
        "corpus_hash": _corpus_hash(raw),
        "corpus_version": corpus.get("version"),
        "environment": _environment(),
        "label_resolution": run_label_resolution(corpus),
        "entity_ruler": run_entity_ruler(corpus),
        "reconciler": run_reconciler(corpus),
    }

    CAPTURES_DIR.mkdir(exist_ok=True)
    out_path = CAPTURES_DIR / f"{args.out}.json"
    out_path.write_text(json.dumps(capture, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    lr = capture["label_resolution"]
    resolved = sum(1 for r in lr if r["primary"])
    print(f"wrote {out_path.relative_to(BACKEND)}")
    print(f"  corpus_hash: {capture['corpus_hash'][:16]}...")
    print(f"  folio_resolve_present: {capture['environment']['folio_resolve_present']}")
    print(f"  label_resolution: {resolved}/{len(lr)} resolved to a primary")
    print(f"  entity_ruler docs: {len(capture['entity_ruler'])}")
    print(f"  reconciler cases: {len(capture['reconciler'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
