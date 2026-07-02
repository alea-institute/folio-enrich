"""Tuning harness for the backup semantic-relevance filter.

Runs the full resolution path over a document with the backup search FORCED ON
(``skip_backups_for_exact_matches=false``) so exact-match concepts also get their
noisy runner-ups, then prints — per concept, per backup — the similarity between
the mention's sentence context and the backup's definition/label. Use this to pick
``backup_semantic_relevance_threshold`` (keep the good alternatives, drop the junk).

Requires the FOLIO ontology + an EmbeddingService with sentence-transformers
available (i.e. PROD, not DEV/Railway). Run from the backend dir:

    .venv/bin/python scripts/tune_backup_semantic_filter.py

Optionally pass a path to a UTF-8 text file as argv[1] to tune on your own doc.
"""

from __future__ import annotations

import asyncio
import sys

DEFAULT_DOC = (
    "This Non-Disclosure Agreement is entered into between Acme Corporation and "
    "John Smith. The parties agree that confidential information shall not be "
    "disclosed. The Court shall have jurisdiction over any dispute arising under "
    "this contract. The plaintiff filed a motion to dismiss. Damages may be "
    "awarded for breach."
)


async def main(text: str) -> None:
    from app.config import settings
    from app.services.folio.owl_cache import ensure_owl_fresh, get_owl_content_hash
    from app.services.folio.folio_service import FolioService
    from app.services.embedding.service import EmbeddingService
    from app.services.folio.resolver import ConceptResolver
    from app.pipeline.stages.resolution_stage import ResolutionStage

    # Force the noisy backups on and disable the semantic filter so we see EVERY
    # candidate and its raw similarity (we score them ourselves below).
    settings.skip_backups_for_exact_matches = False
    settings.backup_semantic_filter_enabled = False

    ensure_owl_fresh()
    owl_hash = get_owl_content_hash()
    folio_service = FolioService.get_instance()
    embedding_service = EmbeddingService.get_instance()
    embedding_service.index_folio_labels(folio_service, owl_hash)
    if embedding_service.index_size == 0:
        print("EmbeddingService index is empty — sentence-transformers unavailable. "
              "Run this on PROD.", file=sys.stderr)
        return

    resolver = ConceptResolver()
    stage = ResolutionStage(resolver=resolver, embedding_service=embedding_service)

    # Resolve every whitespace token as a candidate mention (cheap, good enough for
    # tuning); attach backups the same way the pipeline does.
    resolved: list[dict] = []
    seen = set()
    for token in dict.fromkeys(text.replace(".", " ").split()):
        ct = token.strip()
        if len(ct) < 3 or ct.lower() in seen:
            continue
        seen.add(ct.lower())
        r = resolver.resolve(concept_text=ct, branches=[], confidence=0.5, source="tune")
        if not r:
            continue
        rd = stage._to_resolved_dict(r)
        stage._attach_backup_candidates(rd, {"concept_text": ct})
        if rd.get("_backup_candidates"):
            resolved.append(rd)

    # Print raw sims per backup using the SAME sentence-context extraction the filter uses.
    print(f"\n{'='*80}\nBackup semantic-relevance sims (threshold candidate: "
          f"{settings.backup_semantic_relevance_threshold})\n{'='*80}")
    for rd in resolved:
        sentence = stage._sentence_context(text, rd.get("concept_text", ""))
        backups = rd.get("_backup_candidates", [])
        pairs = [(sentence, b.get("folio_definition") or b.get("folio_label") or "") for b in backups]
        sims = embedding_service.similarity_batch(pairs)
        print(f"\n{rd['concept_text']!r} -> {rd['folio_label']}")
        for b, sim in sorted(zip(backups, sims), key=lambda t: t[1], reverse=True):
            mark = "KEEP" if sim >= settings.backup_semantic_relevance_threshold else "drop"
            print(f"  [{mark}] sim={sim:5.2f}  {b['folio_label']}")


if __name__ == "__main__":
    doc = DEFAULT_DOC
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            doc = fh.read()
    asyncio.run(main(doc))
