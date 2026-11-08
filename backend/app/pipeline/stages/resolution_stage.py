from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.models.annotation import ConceptMatch, stamp_union_dict
from app.models.job import Job, JobStatus
from app.pipeline.stages.base import PipelineStage
from app.services.folio.branch_config import (
    EXCLUDED_BRANCHES,
    VIRTUAL_BRANCHES,
    VIRTUAL_BRANCH_TARGETS,
)
from app.config import settings
from app.services.folio.resolver import ConceptResolver

logger = logging.getLogger(__name__)


class ResolutionStage(PipelineStage):
    def __init__(
        self,
        resolver: ConceptResolver | None = None,
        embedding_service=None,
        registry_embeddings: bool = False,
    ) -> None:
        self.resolver = resolver or ConceptResolver()
        self._embedding_service = embedding_service
        # When True (production), fetch the per-ontology embedding service from the
        # registry at run time so a Canon job scores against Canon vectors. When
        # False (tests/back-compat), the injected embedding_service is used verbatim.
        self._registry_embeddings = registry_embeddings

    @property
    def name(self) -> str:
        return "resolution"

    @staticmethod
    def _to_resolved_dict(resolved, branch_hints: list[str] | None = None) -> dict:
        """Convert a ResolvedConcept to a dict with enriched metadata."""
        fc = resolved.folio_concept
        result = {
            "_resolution_path": resolved.resolution_path,
            "_branch_hints": list(branch_hints or []),
            "concept_text": resolved.concept_text,
            "folio_iri": fc.iri,
            "folio_label": fc.preferred_label,
            "folio_definition": fc.definition,
            "branches": resolved.branches,
            "branch_color": resolved.branch_color,
            "confidence": resolved.confidence,
            "source": resolved.source,
            "state": "confirmed",
            "hierarchy_path": resolved.hierarchy_path,
            "iri_hash": resolved.iri_hash,
            "folio_examples": fc.examples or None,
            "folio_notes": fc.notes or None,
            "folio_see_also": fc.see_also or None,
            "folio_source": fc.source or None,
            "folio_alt_labels": fc.alternative_labels or None,
            "folio_hidden_label": fc.hidden_label or None,
            "folio_editorial_note": fc.editorial_note or None,
            "folio_comment": fc.comment or None,
            "folio_description": fc.description or None,
            "folio_history_note": fc.history_note or None,
            "folio_country": fc.country or None,
            "folio_deprecated": fc.deprecated if fc.deprecated else None,
            "translations": fc.translations if fc.translations else None,
        }
        return result

    def _attach_backup_candidates(
        self, rd: dict, concept_data: dict
    ) -> None:
        """Attach runner-up candidates from multi-strategy search."""
        max_cand = settings.max_candidates
        if max_cand <= 1:
            return
        # (A) An exact FOLIO IRI match is definitive — its runner-ups are just other
        # labels sharing a word (measured noisy) and this search is the dominant
        # resolution cost. Skip it for confident exact matches; keep backups only for
        # genuinely ambiguous concepts (resolved via fuzzy search, i.e. no exact IRI).
        primary_iri = rd.get("folio_iri", "")
        if settings.skip_backups_for_exact_matches and primary_iri:
            return
        # (B) Backups are runner-ups: never display one as more confident than the
        # chosen primary.
        primary_conf = rd.get("confidence", 0.0)
        alternates = self.resolver.resolve_multi(
            concept_text=concept_data.get("concept_text", ""),
            branches=concept_data.get("branches", []),
            confidence=concept_data.get("confidence", 0.0),
            source=concept_data.get("source", "resolved"),
            max_candidates=max_cand,
        )
        backups = []
        for alt in alternates:
            if alt.folio_concept.iri == primary_iri:
                continue
            if any(b in EXCLUDED_BRANCHES for b in alt.branches):
                continue
            fc = alt.folio_concept
            backups.append({
                "concept_text": alt.concept_text,
                "folio_iri": fc.iri,
                "folio_label": fc.preferred_label,
                "folio_definition": fc.definition,
                "branches": alt.branches,
                "branch_color": alt.branch_color,
                "confidence": min(alt.confidence, primary_conf),
                "source": alt.source,
                "state": "backup",
                "iri_hash": alt.iri_hash,
                "folio_alt_labels": fc.alternative_labels or None,
            })
        if backups:
            rd["_backup_candidates"] = backups

    @staticmethod
    def _resolve_virtual_branches(resolved_dict: dict, folio_branch: str) -> None:
        """Replace virtual branches with actual FOLIO branches after resolution."""
        branches = resolved_dict.get("branches", [])
        new_branches = []
        for b in branches:
            if b in VIRTUAL_BRANCHES:
                targets = VIRTUAL_BRANCH_TARGETS.get(b, [])
                if folio_branch and any(folio_branch == t for t in targets):
                    new_branches.append(folio_branch)
                elif targets:
                    new_branches.append(targets[0])
                else:
                    new_branches.append(b)
            else:
                new_branches.append(b)
        resolved_dict["branches"] = new_branches

    @staticmethod
    def _sentence_context(full_text: str, concept_text: str) -> str:
        """Extract the sentence a mention appears in (bounded by nearest periods).

        Falls back to the concept text itself when the mention isn't found in the
        document (e.g. normalization altered casing/whitespace).
        """
        idx = full_text.lower().find(concept_text.lower())
        if idx < 0:
            return concept_text
        start = max(0, full_text.rfind(".", 0, idx) + 1)
        end = full_text.find(".", idx + len(concept_text))
        end = len(full_text) if end == -1 else end + 1
        return full_text[start:end].strip()

    def _apply_embedding_context_scores(
        self, resolved_concepts: list[dict], full_text: str, ontology_id: str = "folio"
    ) -> None:
        """Blend embedding context into primary scores AND filter backup candidates.

        In one batched forward pass this:
          - blends the mention's sentence-vs-definition similarity into each primary
            concept's confidence (60% search + 40% context), and
          - scores each backup candidate's definition/label against the same sentence
            context and drops backups below ``backup_semantic_relevance_threshold``
            (the raw search score cannot separate signal from noise). Survivors are
            re-scored to ``min(sim, primary_confidence)`` and sorted by relevance.

        No-op when the EmbeddingService is unavailable (service ``None`` or empty
        index) or the batch call fails — backups pass through UNCHANGED so we never
        strip alternatives we cannot score (e.g. on DEV/Railway).
        """
        if self._embedding_service is None:
            return
        # The startup index is FOLIO's. A job for another ontology must not score
        # its candidates against FOLIO vectors — skip (graceful degradation,
        # identical to the embeddings-disabled path). Per-ontology index building
        # is a later phase; PR #14 only needs Canon to degrade, not use FOLIO's index.
        if not self._embedding_service.matches_ontology(ontology_id):
            return
        try:
            if self._embedding_service.index_size == 0:
                return
        except Exception:
            return

        filter_backups = settings.backup_semantic_filter_enabled
        threshold = settings.backup_semantic_relevance_threshold
        branch_bonus = settings.backup_branch_coherence_bonus

        # One flat batch of (sentence, text) pairs across every primary definition and
        # (when enabled) every backup candidate — one forward pass scores both.
        pairs: list[tuple[str, str]] = []
        plan: list[tuple[dict, str, dict | None]] = []  # (rd, kind, backup_or_None)
        for rd in resolved_concepts:
            sentence = self._sentence_context(full_text, rd.get("concept_text", ""))
            definition = rd.get("folio_definition") or ""
            if definition:
                plan.append((rd, "primary", None))
                pairs.append((sentence, definition))
            if filter_backups:
                for bc in rd.get("_backup_candidates", []) or []:
                    text_b = bc.get("folio_definition") or bc.get("folio_label") or ""
                    if text_b:
                        plan.append((rd, "backup", bc))
                        pairs.append((sentence, text_b))

        if not pairs:
            return

        try:
            sims = self._embedding_service.similarity_batch(pairs)
        except Exception:
            return

        # id(rd) -> [(sim, rescored_backup_dict)] for backups clearing the threshold.
        # Primary pairs precede their backups in `plan`, so rd["confidence"] is already
        # the blended value by the time we cap backups against it.
        survivors: dict[int, list[tuple[float, dict]]] = {}
        dropped: set[int] = set()
        for (rd, kind, bc), sim in zip(plan, sims):
            sim = max(0.0, min(1.0, sim))  # clamp
            if kind == "primary":
                hints = {b.casefold() for b in rd.get("_branch_hints", [])}
                shares_hint = any(b.casefold() in hints for b in rd.get("branches", []))
                if (settings.fork_context_gate_enabled and rd.get("_resolution_path") == "fork"
                    and (sim < settings.fork_context_min_similarity
                         or (sim < settings.fork_context_branch_gate_similarity and not shares_hint))):
                    dropped.add(id(rd))
                    continue
                search_score = rd.get("confidence", 0.5)
                blended = round(search_score * 0.6 + sim * 0.4, 4)
                rd["confidence"] = blended
                events = rd.setdefault("_lineage_events", [])
                events.append({
                    "stage": "resolution",
                    "action": "embedding_context",
                    "detail": f"Embedding similarity={sim:.2f}, blended 60/40 (was {search_score:.2f})",
                    "confidence": blended,
                })
            else:  # backup — gate on similarity plus a structural branch-coherence bonus
                shares_branch = bool(
                    set(bc.get("branches") or []) & set(rd.get("branches") or [])
                )
                effective = sim + (branch_bonus if shares_branch else 0.0)
                if effective >= threshold:
                    rescored = dict(bc)
                    # Displayed confidence stays the honest raw similarity (capped at
                    # primary) — the branch bonus only influences keep/drop, not score.
                    rescored["confidence"] = min(sim, rd.get("confidence", 1.0))
                    survivors.setdefault(id(rd), []).append((sim, rescored))

        # Mutate the list itself: StringMatch must never expand a dropped primary.
        resolved_concepts[:] = [rd for rd in resolved_concepts if id(rd) not in dropped]

        if not filter_backups:
            return

        for rd in resolved_concepts:
            kept = survivors.get(id(rd))
            if kept is None:
                # Had backups but none survived (and embeddings ran) → clear the key.
                # A concept that never had backups is left untouched.
                if rd.get("_backup_candidates"):
                    rd.pop("_backup_candidates", None)
            else:
                kept.sort(key=lambda t: t[0], reverse=True)
                rd["_backup_candidates"] = [b for _, b in kept]

    async def execute(self, job: Job) -> Job:
        job.status = JobStatus.RESOLVING

        # Resolve against the job's ontology (default FOLIO). The resolver binds a
        # default service at construction; rebind per-job so a Canon document
        # resolves against Canon concepts, not FOLIO's.
        from app.services.folio.folio_service import FolioService
        if getattr(self.resolver.folio, "ontology_id", None) != job.ontology:
            self.resolver._cache.clear()
        self.resolver.folio = FolioService.get_instance(job.ontology)

        # Bind the embedding service built for THIS job's ontology (Canon jobs score
        # against Canon vectors, FOLIO jobs against FOLIO's). The matches_ontology
        # gate inside _apply_embedding_context_scores then passes as a safety assert.
        if self._registry_embeddings:
            from app.services.ontology.registry import get_embedding_service
            self._embedding_service = get_embedding_service(job.ontology)

        # Prefer reconciled concepts (merged ruler + LLM); fall back to individual sources
        reconciled = job.result.metadata.get("reconciled_concepts", [])
        resolved_concepts: list[dict] = []
        unresolved_mentions: list[dict] = []

        # Reconciliation may pick the ruler object, whose branch describes a
        # candidate rather than the LLM's intent. Recover the original hints.
        llm_hints_by_text: dict[str, list[str]] = {}
        for concepts in job.result.metadata.get("llm_concepts", {}).values():
            for concept in concepts:
                llm_hints_by_text.setdefault(concept.get("concept_text", "").casefold(), []).extend(concept.get("branches", []))

        def branch_hints(concept: dict) -> list[str]:
            return llm_hints_by_text.get(concept.get("concept_text", "").casefold(), concept.get("branches", []))

        if reconciled:
            for concept_data in reconciled:
                resolved = self.resolver.resolve(
                    concept_text=concept_data.get("concept_text", ""),
                    branches=concept_data.get("branches", []),
                    confidence=concept_data.get("confidence", 0.0),
                    source=concept_data.get("source", "reconciled"),
                    folio_iri=concept_data.get("folio_iri"),
                )
                if resolved is None:
                    unresolved_mentions.append(concept_data)
                if resolved and not any(b in EXCLUDED_BRANCHES for b in resolved.branches):
                    rd = self._to_resolved_dict(resolved, branch_hints(concept_data))
                    self._resolve_virtual_branches(rd, resolved.folio_concept.branch)
                    self._attach_backup_candidates(rd, concept_data)
                    # Carry forward upstream lineage events
                    events = list(concept_data.get("_lineage_events", []))
                    events.append({
                        "stage": "resolution",
                        "action": "enriched",
                        "detail": f"Resolved to FOLIO: '{resolved.folio_concept.preferred_label}'",
                        "confidence": resolved.confidence,
                    })
                    rd["_lineage_events"] = events
                    resolved_concepts.append(rd)
        else:
            # No reconciled concepts — resolve from individual sources
            ruler_raw = job.result.metadata.get("ruler_concepts", [])
            for concept_data in ruler_raw:
                resolved = self.resolver.resolve(
                    concept_text=concept_data.get("concept_text", ""),
                    branches=concept_data.get("branches", []),
                    confidence=concept_data.get("confidence", 0.5),
                    source="entity_ruler",
                    folio_iri=concept_data.get("folio_iri"),
                )
                if resolved and not any(b in EXCLUDED_BRANCHES for b in resolved.branches):
                    rd = self._to_resolved_dict(resolved, branch_hints(concept_data))
                    self._resolve_virtual_branches(rd, resolved.folio_concept.branch)
                    self._attach_backup_candidates(rd, concept_data)
                    resolved_concepts.append(rd)

            # Then LLM concepts
            llm_concepts = job.result.metadata.get("llm_concepts", {})
            seen_texts = {c["concept_text"].lower() for c in resolved_concepts}
            for chunk_idx, concepts in llm_concepts.items():
                for concept_data in concepts:
                    ct = concept_data.get("concept_text", "").lower()
                    if ct in seen_texts:
                        continue
                    seen_texts.add(ct)
                    resolved = self.resolver.resolve(
                        concept_text=concept_data.get("concept_text", ""),
                        branches=concept_data.get("branches", []),
                        confidence=concept_data.get("confidence", 0.0),
                        source="llm",
                        folio_iri=concept_data.get("folio_iri"),
                    )
                    if resolved is None:
                        unresolved_mentions.append(dict(concept_data, source="llm"))
                    if resolved and not any(b in EXCLUDED_BRANCHES for b in resolved.branches):
                        rd = self._to_resolved_dict(resolved, branch_hints(concept_data))
                        self._resolve_virtual_branches(rd, resolved.folio_concept.branch)
                        self._attach_backup_candidates(rd, concept_data)
                        resolved_concepts.append(rd)

        full_text = job.result.canonical_text.full_text if job.result.canonical_text else ""
        locations = {c["concept_text"].casefold() for c in resolved_concepts
                     if any(b.casefold() == "location" for b in c.get("branches", []))}

        def language_allowed(candidate: dict, mention: dict) -> bool:
            if not any(b.casefold() == "language" for b in candidate.get("branches", [])):
                return True
            text = mention.get("concept_text", "")
            if text.casefold() in locations:
                return False
            hints = mention.get("_branch_hints", []) if mention.get("source") != "entity_ruler" else []
            return (any(b.casefold() == "language" for b in hints)
                    or bool(re.search(r"\blanguage\b", self._sentence_context(full_text, text), re.IGNORECASE)))

        resolved_concepts = [c for c in resolved_concepts if language_allowed(c, c)]
        for rc in resolved_concepts:
            if rc.get("_backup_candidates"):
                rc["_backup_candidates"] = [bc for bc in rc["_backup_candidates"] if language_allowed(bc, rc)]

        # Prefer RDFS label matches before SKOS preferred labels within each group.
        homonym_groups: dict[tuple[str, str], list[int]] = {}
        for index, concept in enumerate(resolved_concepts):
            branches = concept.get("branches") or []
            key = (concept["concept_text"].casefold(), branches[0] if branches else "")
            homonym_groups.setdefault(key, []).append(index)
        dropped_indices: set[int] = set()
        for indices in homonym_groups.values():
            if len({resolved_concepts[i]["folio_iri"] for i in indices}) <= 1:
                continue
            rdfs_iris = set()
            preferred_iris = set()
            for i in indices:
                concept = resolved_concepts[i]
                text = " ".join(concept["concept_text"].split()).casefold()
                if text == " ".join(concept["folio_label"].split()).casefold():
                    rdfs_iris.add(concept["folio_iri"])
                    continue
                get_concept = getattr(self.resolver.folio, "get_concept", None)
                fc = get_concept(concept["folio_iri"]) if get_concept else None
                if fc:
                    if text == " ".join((fc.preferred_label or "").split()).casefold():
                        rdfs_iris.add(concept["folio_iri"])
                    elif text == " ".join((fc.folio_pref_label or "").split()).casefold():
                        preferred_iris.add(concept["folio_iri"])
            preferred_iris.update(rdfs_iris)
            exact_iris = rdfs_iris if len(rdfs_iris) == 1 else preferred_iris
            if len(exact_iris) == 1:
                dropped_indices.update(
                    i for i in indices
                    if resolved_concepts[i]["folio_iri"] not in exact_iris
                )
        dropped_homonyms = len(dropped_indices)
        resolved_concepts = [
            concept for i, concept in enumerate(resolved_concepts) if i not in dropped_indices
        ]

        # Score before coreference so rejected courts cannot supply an antecedent.
        before_context_gate = len(resolved_concepts)
        if full_text:
            self._apply_embedding_context_scores(
                resolved_concepts, full_text, ontology_id=job.ontology
            )

        dropped_forks = before_context_gate - len(resolved_concepts)

        # Resolve generic court mentions only from unambiguous courts in this job.
        from app.services.folio.court_names import is_deictic_court, normalize_court_text
        court_types = {
            "district court": ("district court",),
            "court of appeals": ("ct. app.", "court of appeals"),
            "appellate court": ("ct. app.", "court of appeals"),
            "circuit court": ("ct. app.", "court of appeals"),
            "bankruptcy court": ("bankruptcy court",),
        }
        resolved_texts = {c["concept_text"].casefold() for c in resolved_concepts}
        document_courts = list(resolved_concepts)
        for mention in unresolved_mentions:
            text = mention.get("concept_text", "")
            deictic = is_deictic_court(text)
            types = ("court", "ct.", "circuit") if deictic else court_types.get(normalize_court_text(text))
            if not types or text.casefold() in resolved_texts:
                continue
            candidates = {
                c["folio_iri"]: c for c in document_courts
                if any(t in c.get("folio_label", "").casefold() for t in types)
                and (not deictic or {"Forums and Venues", "Governmental Body"}.intersection(c.get("branches", [])))
            }
            if len(candidates) != 1:
                continue
            iri, candidate = next(iter(candidates.items()))
            resolved = self.resolver.resolve(
                text, folio_iri=iri, confidence=mention.get("confidence", 0.0),
                source=mention.get("source", "reconciled"),
            )
            if resolved and not any(b in EXCLUDED_BRANCHES for b in resolved.branches):
                rd = self._to_resolved_dict(resolved, mention.get("branches", []))
                rd["_lineage_events"] = list(mention.get("_lineage_events", [])) + [{
                    "stage": "resolution", "action": "coreference",
                    "detail": f"Generic court mention linked to the document's {candidate['folio_label']}",
                    "confidence": resolved.confidence,
                }]
                resolved_concepts.append(rd)
                resolved_texts.add(text.casefold())

        if job.ontology == "both":
            for rc in resolved_concepts:
                rc.update(stamp_union_dict(rc, self.resolver.folio))
                for backup in rc.get("_backup_candidates", []):
                    backup.update(stamp_union_dict(backup, self.resolver.folio))
        # Context-gate inputs have no downstream use. Remove them here so even
        # metadata serializers and demo slimming cannot expose private hints.
        for rc in resolved_concepts:
            rc.pop("_resolution_path", None)
            rc.pop("_branch_hints", None)
        job.result.metadata["resolved_concepts"] = resolved_concepts

        log = job.result.metadata.setdefault("activity_log", [])
        log.append({"ts": datetime.now(timezone.utc).isoformat(), "stage": self.name, "msg": f"Resolved {len(resolved_concepts)} concepts with FOLIO definitions; dropped {dropped_homonyms} same-branch homonyms; dropped {dropped_forks} fork context mismatches"})
        logger.info("Resolved %d concepts for job %s", len(resolved_concepts), job.id)
        return job
