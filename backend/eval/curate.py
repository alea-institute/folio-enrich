"""Gold-set curation tool — seed / refresh the NER eval gold from baked demos.

Seeding is *non-circular*: spans come from the demo documents, but the correct
label for each span is decided by the **FOLIO label dictionary oracle**
(``FolioService.get_all_labels_multi``), not by the enrich pipeline's ranking.

    - surface maps to exactly ONE concept via a (lemma-)preferred label, and that
      concept is what the pipeline confirmed  → verification="deterministic",
      difficulty="clear", polarity="positive"  (safe to trust, scored)
    - surface is ambiguous (multiple concepts) or matched only via an alternative
      label                                    → verification="needs_review",
      difficulty="borderline", with the competing ``candidates`` recorded
      (the evidence-pack borderline pattern; excluded from scoring until a human
      promotes it to verification="human")

Idempotent: re-running regenerates the deterministic/needs_review entries but
**never touches entries whose verification == "human"** — Damien and other lanes
extend the set by hand and keep their work across refreshes.

Usage
-----
    cd backend
    .venv/bin/python -m eval.curate                       # default doc set
    .venv/bin/python -m eval.curate --docs contract,nda   # subset
    .venv/bin/python -m eval.curate --limit 25 --out eval/gold/folio_ner_gold.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .demo_source import load_demo_content
from .gold_schema import GoldCandidate, GoldEntry, GoldSpan, load_gold, save_gold
from .metrics import iri_key

_HERE = Path(__file__).resolve().parent
DEFAULT_OUT = _HERE / "gold" / "folio_ner_gold.jsonl"

DEFAULT_DOCS = ["contract", "nda", "motion", "opinion", "lease", "patent"]


def _doc_source_rel(doc_id: str) -> str:
    return f"frontend/demos/{doc_id}.json"


async def _annotate_full(text: str):
    """Deterministic run (flag OFF) → list of confirmed Annotation objects."""
    from app.config import settings
    from app.models.job import DocumentInput, Job
    from app.pipeline.orchestrator import PipelineOrchestrator
    from app.storage.job_store import JobStore

    prev = settings.ner_cross_validation_enabled
    settings.ner_cross_validation_enabled = False
    try:
        job = Job(input=DocumentInput(content=text, format="plain_text", filename="curate.txt"))
        out = await PipelineOrchestrator(JobStore()).run(job)
    finally:
        settings.ner_cross_validation_enabled = prev
    return [a for a in (out.result.annotations if out.result else [])
            if a.state == "confirmed" and a.concepts and a.concepts[0].folio_iri]


def _classify(concept_text: str, ann_iri: str, multi: dict) -> tuple[bool, list]:
    """Return (is_clear_deterministic, candidate_LabelInfos) for a surface form."""
    key = (concept_text or "").strip().lower()
    entries = multi.get(key, [])
    distinct = {}
    for e in entries:
        distinct.setdefault(iri_key(e.concept.iri), e)
    winner_is_preferred = any(
        iri_key(e.concept.iri) == iri_key(ann_iri)
        and e.label_type in ("preferred", "lemma_preferred")
        for e in entries
    )
    is_clear = len(distinct) == 1 and winner_is_preferred and bool(entries)
    return is_clear, list(distinct.values())


async def curate(doc_ids: list[str], limit: int) -> list[GoldEntry]:
    from app.services.folio.folio_service import FolioService

    svc = FolioService()
    svc.get_all_labels()
    multi = svc.get_all_labels_multi()

    entries: list[GoldEntry] = []
    for doc_id in doc_ids:
        text = load_demo_content(doc_id)
        anns = await _annotate_full(text)

        seen_iris: set[str] = set()
        n = 0
        # deterministic order: by span, so seeding is stable
        for ann in sorted(anns, key=lambda a: (a.span.start, a.span.end)):
            if n >= limit:
                break
            concept = ann.concepts[0]
            ik = iri_key(concept.folio_iri)
            if ik in seen_iris:
                continue  # one gold entry per distinct concept per doc (diverse, compact)
            oracle_concept = svc.get_concept(concept.folio_iri)
            if oracle_concept is None:
                continue  # oracle: IRI must exist in the ontology
            seen_iris.add(ik)
            n += 1

            is_clear, cand_infos = _classify(concept.concept_text, concept.folio_iri, multi)
            branch = (concept.branches or [""])[0] or getattr(oracle_concept, "branch", "")
            candidates = [
                GoldCandidate(
                    folio_iri=e.concept.iri, folio_label=e.concept.preferred_label,
                    branch=getattr(e.concept, "branch", ""),
                )
                for e in cand_infos if iri_key(e.concept.iri) != ik
            ][:4]

            # Content-derived id (H1): stable under reordering; a new concept never
            # collides with an unrelated preserved-human entry, and a human entry always
            # tracks the same concept in the same doc across re-curations.
            gid = f"GOLD-FOLIO-{doc_id.upper()}-{ik}"
            entries.append(GoldEntry(
                gold_id=gid,
                doc_id=doc_id,
                doc_source=_doc_source_rel(doc_id),
                span=GoldSpan(start=ann.span.start, end=ann.span.end, text=ann.span.text),
                expected_iri=concept.folio_iri,
                expected_label=concept.folio_label or "",
                branch=branch,
                polarity="positive",
                verification="deterministic" if is_clear else "needs_review",
                verified_by="folio-label-oracle 2026-07-07" if is_clear else "",
                difficulty="clear" if is_clear else "borderline",
                rationale=(
                    "Unique (lemma-)preferred FOLIO label match — oracle-confirmed."
                    if is_clear else
                    f"Ambiguous surface '{concept.concept_text}': "
                    f"{len(cand_infos)} competing concept(s); needs human verification."
                ),
                candidates=candidates,
            ))
    return entries


def merge_preserving_human(new: list[GoldEntry], existing_path: Path) -> list[GoldEntry]:
    """Keep every human-verified existing entry; take new for everything else.

    Preservation keys on ``verification == "human"`` only. A manual edit to a
    ``deterministic``/``needs_review`` entry that does NOT flip ``verification`` to
    ``"human"`` will be re-derived (i.e. overwritten) on the next run — so promoting a
    borderline case or correcting a label MUST set ``verification:"human"``
    (see ``gold/README.md``). Because gold_ids are content-derived, a preserved human
    entry always tracks the same (doc, concept) and never blocks a genuinely new one.
    """
    existing = load_gold(existing_path)
    human = [e for e in existing if e.verification == "human"]
    human_ids = {e.gold_id for e in human}
    merged = list(human) + [e for e in new if e.gold_id not in human_ids]
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed/refresh the NER eval gold set")
    ap.add_argument("--docs", default=",".join(DEFAULT_DOCS),
                    help="comma-separated demo doc ids")
    ap.add_argument("--limit", type=int, default=25, help="max gold entries per doc")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output gold JSONL")
    args = ap.parse_args()

    doc_ids = [d.strip() for d in args.docs.split(",") if d.strip()]
    new = asyncio.run(curate(doc_ids, args.limit))
    merged = merge_preserving_human(new, Path(args.out))
    for e in merged:
        e.validate()
    save_gold(merged, args.out)

    scored = sum(1 for e in merged if e.is_scored)
    review = sum(1 for e in merged if e.verification == "needs_review")
    human = sum(1 for e in merged if e.verification == "human")
    print(f"wrote {len(merged)} gold entries to {args.out}")
    print(f"  scored (deterministic+human): {scored}   needs_review: {review}   human: {human}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
