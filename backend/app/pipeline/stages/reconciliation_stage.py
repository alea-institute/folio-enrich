from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.annotation import ConceptMatch
from app.models.job import Job, JobStatus
from app.pipeline.stages.base import PipelineStage, record_lineage
from app.services.reconciliation.reconciler import Reconciler

logger = logging.getLogger(__name__)


# spaCy NER label → set of compatible branch names, keyed by ontology.
# Branch strings are the concept's resolved top-level branch labels as they appear
# in ``ConceptMatch.branches`` (FOLIO's curated display names; Canon's root class
# labels). The map for an unknown ontology is absent → the NER pass is a no-op.
_NER_BRANCH_AFFINITY_BY_ONTOLOGY: dict[str, dict[str, set[str]]] = {
    # FOLIO — from PR-#4 commit 50beecc (9-label map).
    "folio": {
        "ORG": {"Actor / Player", "Legal Entity", "Governmental Body", "Industry"},
        "PERSON": {"Actor / Player"},
        "GPE": {"Location", "Governmental Body"},
        "LOC": {"Location"},
        "DATE": {"Event", "Status"},
        "MONEY": {"Currency", "Financial Concepts and Metrics", "Asset Type"},
        "LAW": {"Legal Authorities"},
        "NORP": {"Actor / Player"},
        "FAC": {"Location", "Forums and Venues"},
    },
    # Catholic Semantic Canon — keyed on WS-A's real root labels (Actor / Authority
    # (Source and Scope) / Document / Artifact / Event / Normative Concepts /
    # Operational Concepts / Place). Branch labels here are the FULL root class
    # labels exactly as populated in ``branches`` (e.g. "Document / Artifact").
    "canon": {
        "PERSON": {"Actor"},
        "ORG": {"Actor"},
        "NORP": {"Actor"},
        "GPE": {"Place"},
        "LOC": {"Place"},
        "FAC": {"Place"},
        "DATE": {"Event"},
        "EVENT": {"Event"},
        "WORK_OF_ART": {"Document / Artifact"},
        "LAW": {"Document / Artifact"},
    },
}


def _find_overlapping_ner(
    span_start: int, span_end: int, ner_entities: list[dict]
) -> str | None:
    """Return the NER label of an entity overlapping the given character span.

    Any character-span overlap counts. Returns the label string (e.g. "ORG",
    "PERSON") or None when no NER entity overlaps the span.
    """
    for ent in ner_entities:
        ent_start = ent.get("start", 0)
        ent_end = ent.get("end", 0)
        if span_start < ent_end and span_end > ent_start:
            return ent.get("label")
    return None


class ReconciliationStage(PipelineStage):
    def __init__(
        self,
        reconciler: Reconciler | None = None,
        embedding_service=None,
        registry_embeddings: bool = False,
    ) -> None:
        self.reconciler = reconciler or Reconciler(embedding_service=embedding_service)
        # When True (production), the per-ontology embedding service is fetched from
        # the registry at run time and bound onto the reconciler; when False
        # (tests/back-compat), the reconciler's injected service is used verbatim.
        self._registry_embeddings = registry_embeddings

    @property
    def name(self) -> str:
        return "reconciliation"

    async def execute(self, job: Job) -> Job:
        # Gather ruler concepts
        ruler_raw = job.result.metadata.get("ruler_concepts", [])
        ruler_concepts = [ConceptMatch(**c) for c in ruler_raw]

        # Gather LLM concepts (flatten from per-chunk)
        llm_raw = job.result.metadata.get("llm_concepts", {})
        llm_concepts = [
            ConceptMatch(**c)
            for chunk_concepts in llm_raw.values()
            for c in chunk_concepts
        ]

        # Bind the embedding service built for THIS job's ontology so a Canon job
        # reconciles against Canon vectors (not FOLIO's). The matches_ontology check
        # below then passes as a safety assert; if the ontology has no usable index
        # (build failed / empty), fall back to non-embedding reconcile().
        if self._registry_embeddings:
            from app.services.ontology.registry import get_embedding_service
            self.reconciler._embedding_service = get_embedding_service(job.ontology)

        emb = self.reconciler._embedding_service
        if emb is not None and emb.matches_ontology(job.ontology) and emb.index_size > 0:
            results = self.reconciler.reconcile_with_embedding_triage(ruler_concepts, llm_concepts)
        else:
            results = self.reconciler.reconcile(ruler_concepts, llm_concepts)

        # Store reconciled concepts for resolution stage (all start as "preliminary")
        # Propagate _lineage_event from LLM concepts into reconciled dicts
        llm_lineage_by_text: dict[str, dict] = {}
        for chunk_concepts in llm_raw.values():
            for c in chunk_concepts:
                evt = c.get("_lineage_event")
                if evt:
                    llm_lineage_by_text[c.get("concept_text", "").lower()] = evt

        reconciled = []
        for r in results:
            rd: dict = {
                "concept_text": r.concept.concept_text,
                "branches": r.concept.branches,
                "confidence": r.concept.confidence,
                "source": r.concept.source,
                "folio_iri": r.concept.folio_iri,
                "category": r.category,
                "state": "preliminary",
            }
            # Carry forward LLM lineage events
            lineage_events: list[dict] = []
            llm_evt = llm_lineage_by_text.get(r.concept.concept_text.lower())
            if llm_evt:
                lineage_events.append(llm_evt)
            rd["_lineage_events"] = lineage_events
            reconciled.append(rd)
        job.result.metadata["reconciled_concepts"] = reconciled

        # Update preliminary annotation states based on reconciliation results
        reconciled_by_key: dict[tuple[str, str], str] = {}
        for r in results:
            rkey = (r.concept.concept_text.lower(), r.concept.folio_iri or "")
            reconciled_by_key[rkey] = r.category

        _CATEGORY_DETAIL = {
            "both_agree": "Both EntityRuler and LLM agree",
            "conflict_resolved": "Conflict resolved via embedding similarity",
            "ruler_only": "EntityRuler only (confidence >= threshold)",
        }

        # Build secondary text-only lookup for LLM annotations that lack an IRI
        reconciled_by_text: dict[str, str] = {}
        for (text, iri), cat in reconciled_by_key.items():
            if text not in reconciled_by_text:
                reconciled_by_text[text] = cat
            elif cat in ("both_agree", "conflict_resolved"):
                reconciled_by_text[text] = cat  # prefer stronger categories

        for ann in job.result.annotations:
            if ann.state != "preliminary":
                continue
            concept_text = ann.concepts[0].concept_text.lower() if ann.concepts else ""
            concept_iri = ann.concepts[0].folio_iri or "" if ann.concepts else ""
            category = reconciled_by_key.get((concept_text, concept_iri))
            # Fallback: text-only lookup for LLM annotations with empty/different IRI
            if category is None and concept_iri == "":
                category = reconciled_by_text.get(concept_text)
            if category in ("both_agree", "conflict_resolved"):
                ann.state = "confirmed"
                record_lineage(ann, "reconciliation", "confirmed",
                               detail=_CATEGORY_DETAIL.get(category, ""))
            elif category in ("llm_only",):
                # LLM-only concepts stay preliminary (may be confirmed by resolution)
                record_lineage(ann, "reconciliation", "kept",
                               detail="LLM-only concept — awaiting resolution")
            elif category is None:
                # Not in reconciled set — low confidence, filtered out
                ann.state = "rejected"
                record_lineage(ann, "reconciliation", "rejected",
                               detail="Filtered out (not in reconciled set)")
            else:
                # "ruler_only" stays as "preliminary" (confirmed later by resolution)
                record_lineage(ann, "reconciliation", "kept",
                               detail=_CATEGORY_DETAIL.get(category, f"Category: {category}"))

        # POS-based confidence penalty pass
        pos_adjusted = self._apply_pos_penalties(job)

        # NER cross-validation pass (runs AFTER the POS pass so both signals stack).
        # No-op unless explicitly enabled; guarded on ontology + metadata presence.
        ner_boosted, ner_penalized = self._apply_ner_adjustments(job)

        confirmed = sum(1 for a in job.result.annotations if a.state == "confirmed")
        ruler_only = sum(1 for r in results if r.category == "ruler_only")
        rejected = sum(1 for a in job.result.annotations if a.state == "rejected")
        log = job.result.metadata.setdefault("activity_log", [])
        msg = f"Reconciled: {confirmed} confirmed, {ruler_only} ruler-only, {rejected} rejected"
        if pos_adjusted:
            msg += f", {pos_adjusted} POS-adjusted"
        if ner_boosted or ner_penalized:
            msg += f", {ner_boosted} NER-boosted, {ner_penalized} NER-penalized"
        log.append({"ts": datetime.now(timezone.utc).isoformat(), "stage": self.name, "msg": msg})
        return job

    @staticmethod
    def _apply_pos_penalties(job: Job) -> int:
        """Penalize annotations where POS tag mismatches expected concept sense."""
        from app.config import settings
        from app.services.nlp.pos_lookup import get_majority_pos

        if not settings.pos_confidence_enabled or not settings.pos_tagging_enabled:
            return 0

        sentence_pos = job.result.metadata.get("sentence_pos", [])
        if not sentence_pos:
            return 0

        penalty = settings.pos_concept_mismatch_penalty
        adjusted = 0

        for ann in job.result.annotations:
            if ann.state == "rejected" or not ann.concepts:
                continue

            concept = ann.concepts[0]
            span_text = ann.span.text

            # Only penalize single-word alternative-label matches
            is_single_word = " " not in span_text.strip()
            if not is_single_word:
                continue

            pos = get_majority_pos(ann.span.start, ann.span.end, sentence_pos)
            if pos is None:
                continue

            # VERB/ADV used for a noun-sense concept → penalize
            if pos in ("VERB", "ADV") and concept.match_type in ("alternative", "lemma_alternative"):
                concept.confidence = max(0.0, concept.confidence - penalty)
                adjusted += 1
                record_lineage(
                    ann, "reconciliation", "pos_adjusted",
                    detail=f"POS mismatch: {pos} for noun concept '{concept.concept_text}'",
                    confidence=concept.confidence,
                )
                if concept.confidence < 0.20:
                    ann.state = "rejected"
                    record_lineage(
                        ann, "reconciliation", "rejected",
                        detail="Confidence below 0.20 after POS penalty",
                    )

        return adjusted

    @staticmethod
    def _apply_ner_adjustments(job: Job) -> tuple[int, int]:
        """Cross-validate annotations against spaCy NER entities (per-ontology).

        For each non-rejected annotation whose span overlaps a NER entity:
        - NER label's affinity set intersects the concept's branch(es) → small boost
        - NER label is mapped but NONE of the branches are compatible → penalty
        - No overlapping NER entity, or an unmapped NER label → no change

        Returns (boosted, penalized). Complete no-op — returning (0, 0) — when the
        feature flag is off, when no NER entities were captured, or when the job's
        ontology has no affinity map (unknown ontology is safe).
        """
        from app.config import settings

        if not settings.ner_cross_validation_enabled:
            return 0, 0

        ner_entities = job.result.metadata.get("spacy_ner_entities", [])
        if not ner_entities:
            return 0, 0

        affinity = _NER_BRANCH_AFFINITY_BY_ONTOLOGY.get(job.ontology)
        if not affinity:
            return 0, 0  # Unknown / unmapped ontology → safe no-op

        boost_val = settings.ner_agreement_boost
        penalty_val = settings.ner_contradiction_penalty
        boosted = 0
        penalized = 0

        for ann in job.result.annotations:
            if ann.state == "rejected" or not ann.concepts:
                continue

            concept = ann.concepts[0]
            branches = concept.branches or []
            if not branches:
                # Branch not yet assigned — skip (nothing to cross-check against).
                continue

            ner_label = _find_overlapping_ner(ann.span.start, ann.span.end, ner_entities)
            if ner_label is None:
                continue  # No NER signal on this span → preserve recall, no change.

            compatible_branches = affinity.get(ner_label)
            if not compatible_branches:
                continue  # NER label not in this ontology's map → do nothing.

            branch = branches[0]  # Primary branch, for lineage detail.
            if compatible_branches & set(branches):
                # NER agreement → bounded boost.
                concept.confidence = min(1.0, concept.confidence + boost_val)
                boosted += 1
                record_lineage(
                    ann, "reconciliation", "ner_boosted",
                    detail=f"NER agreement: {ner_label} confirms branch '{branch}'",
                    confidence=concept.confidence,
                )
            else:
                # NER contradiction → bounded penalty.
                concept.confidence = max(0.0, concept.confidence - penalty_val)
                penalized += 1
                record_lineage(
                    ann, "reconciliation", "ner_penalized",
                    detail=f"NER contradiction: {ner_label} vs branch '{branch}'",
                    confidence=concept.confidence,
                )
                if concept.confidence < 0.20:
                    ann.state = "rejected"
                    record_lineage(
                        ann, "reconciliation", "rejected",
                        detail="Confidence below 0.20 after NER penalty",
                    )

        return boosted, penalized
