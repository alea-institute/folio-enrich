from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

import spacy

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.job import Job, JobStatus
from app.pipeline.stages.base import PipelineStage, record_lineage
from app.services.entity_ruler.pattern_builder import build_patterns
from app.services.entity_ruler.ruler import EntityRulerMatch, FOLIOEntityRuler
from app.services.entity_ruler.semantic_ruler import SemanticEntityRuler, can_encode
from app.services.folio.branch_config import get_branch_color
from app.services.folio.folio_service import FolioService
from app.services.normalization.normalizer import build_sentence_index, find_sentence_for_span

logger = logging.getLogger(__name__)

# Confidence scores based on match quality
# Multi-word preferred labels are almost certainly correct
# Single-word alt labels (e.g., "grant" → Donation) are very unreliable
_CONFIDENCE = {
    ("preferred", True): 0.90,   # multi-word preferred label
    ("preferred", False): 0.72,  # single-word preferred label
    ("lemma_preferred", True): 0.85,   # multi-word lemma of a preferred label
    ("lemma_preferred", False): 0.68,  # single-word lemma of a preferred label (e.g. "agreement"->"Agreements")
    ("alternative", True): 0.65, # multi-word alternative label
    ("alternative", False): 0.35,  # single-word alternative label — high false-positive rate
    ("lemma_alternative", True): 0.60,   # multi-word lemma of an alternative label
    ("lemma_alternative", False): 0.33,  # single-word lemma of an alternative label
    ("translation", True): 0.60,   # multi-word translation
    ("translation", False): 0.30,  # single-word translation
}


def _match_confidence(match: EntityRulerMatch) -> float:
    """Compute confidence score based on match type and word count."""
    is_multi_word = len(match.text.split()) > 1
    return _CONFIDENCE.get((match.match_type, is_multi_word), 0.50)


@dataclass
class _RulerBundle:
    """A loaded FOLIO EntityRuler plus its lookup maps, shared across jobs.

    ``labels``/``labels_multi`` are the exact dicts the bundle was built from.
    FolioService swaps in new dicts when the ontology reloads (and the registry
    builds a new service on re-admission), so an identity check detects staleness.
    """
    ruler: FOLIOEntityRuler
    iri_to_branch: dict[str, str]
    iri_to_concept: dict[str, object]
    label_to_concepts: dict[str, list]
    labels: object
    labels_multi: object
    # The spaCy Language inside the ruler is shared across concurrent jobs, which
    # run it on worker threads; serialize calls rather than rely on spaCy's
    # thread-safety.
    lock: threading.Lock = field(default_factory=threading.Lock)
    max_label_chars: int = 0

    def find_matches(self, text: str) -> list[EntityRulerMatch]:
        """Match *text* in overlapping windows.

        spaCy's token Matcher holds the GIL for the whole call and costs
        O(tokens x patterns): with ~18k FOLIO patterns a 65 KB document is one
        ~7 s call, which freezes the event loop even from a worker thread.
        Matching ~2 KB windows bounds each GIL hold. Every window carries a
        context margin longer than any label on both sides and keeps only the
        matches that START in its own region, so overlap resolution sees the
        same neighbours as a whole-document pass.
        """
        margin = self.max_label_chars + _WINDOW_MARGIN_SLACK
        n = len(text)
        if n <= _WINDOW_CHARS + 2 * margin:
            with self.lock:
                return self.ruler.find_matches(text)
        matches: list[EntityRulerMatch] = []
        pos = 0
        while pos < n:
            own_end = _snap_forward(text, min(pos + _WINDOW_CHARS, n))
            lo = _snap_back(text, max(0, pos - margin))
            hi = _snap_forward(text, min(n, own_end + margin))
            with self.lock:
                window_matches = self.ruler.find_matches(text[lo:hi])
            for m in window_matches:
                start = m.start_char + lo
                if pos <= start < own_end:
                    m.start_char = start
                    m.end_char += lo
                    matches.append(m)
            pos = own_end
        return matches


_WINDOW_CHARS = 2000
_WINDOW_MARGIN_SLACK = 50


def _snap_forward(text: str, i: int) -> int:
    """Move *i* forward to the next whitespace (or the end) so windows never
    split a token."""
    n = len(text)
    while i < n and not text[i].isspace():
        i += 1
    return i


def _snap_back(text: str, i: int) -> int:
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return i


# Built rulers keyed by ontology id. Building one compiles every ontology label
# into a spaCy EntityRuler (seconds), so it happens once per ontology version,
# not once per job.
_RULER_CACHE: dict[str, _RulerBundle] = {}
_RULER_CACHE_LOCK = threading.Lock()


def _build_fast_ruler(all_labels: dict) -> FOLIOEntityRuler:
    """Build a FOLIOEntityRuler whose patterns match exactly as
    ``FOLIOEntityRuler.load_patterns`` would, but mostly via the PhraseMatcher.

    ``build_patterns`` emits every multi-word label as a token pattern
    (``[{"LOWER": w}, ...]``). spaCy's token Matcher scans all of them at every
    token — ~19k FOLIO patterns made a 64 KB document a ~10 s, GIL-holding call.
    When the tokenizer splits a label's lowercase text into exactly those words,
    the token pattern and a LOWER phrase pattern match the same spans, so it is
    added as a phrase pattern (hash lookup) instead. Labels the tokenizer would
    split differently stay token patterns, preserving their behavior.
    """
    nlp = spacy.blank("en")
    ruler = FOLIOEntityRuler(nlp=nlp)
    if not all_labels:
        return ruler
    ruler.load_patterns({})  # creates the (empty) entity_ruler pipe; marks loaded
    patterns = []
    for pattern in build_patterns(all_labels):
        spec = pattern["pattern"]
        if isinstance(spec, list) and all(set(tok) == {"LOWER"} for tok in spec):
            words = [tok["LOWER"] for tok in spec]
            phrase = " ".join(words)
            if [t.lower_ for t in nlp.make_doc(phrase)] == words:
                pattern = {**pattern, "pattern": phrase}
        patterns.append(pattern)
    nlp.get_pipe("entity_ruler").add_patterns(patterns)
    return ruler


def _get_ruler_bundle(ontology_id: str) -> _RulerBundle:
    folio_service = FolioService.get_instance(ontology_id)
    all_labels = folio_service.get_all_labels()
    all_labels_multi = folio_service.get_all_labels_multi()
    key = folio_service.ontology_id
    with _RULER_CACHE_LOCK:
        bundle = _RULER_CACHE.get(key)
        if (
            bundle is not None
            and bundle.labels is all_labels
            and bundle.labels_multi is all_labels_multi
        ):
            return bundle

        ruler = _build_fast_ruler(all_labels)
        if all_labels:
            logger.info("EntityRuler loaded %d FOLIO patterns", len(all_labels))
        else:
            logger.warning("No FOLIO labels found — EntityRuler will be empty")

        # Build IRI→branch and IRI→concept maps from multi-label data
        # so we know about ALL concepts including multi-branch entries
        iri_to_branch: dict[str, str] = {}
        iri_to_concept: dict[str, object] = {}
        label_to_concepts: dict[str, list] = {}
        for label_key, entries in all_labels_multi.items():
            for entry in entries:
                fc = entry.concept
                if fc.iri:
                    if fc.branch:
                        iri_to_branch[fc.iri] = fc.branch
                    iri_to_concept[fc.iri] = fc
            label_to_concepts[label_key] = entries

        bundle = _RulerBundle(
            ruler=ruler,
            iri_to_branch=iri_to_branch,
            iri_to_concept=iri_to_concept,
            label_to_concepts=label_to_concepts,
            labels=all_labels,
            labels_multi=all_labels_multi,
            max_label_chars=max((len(k) for k in all_labels), default=0),
        )
        _RULER_CACHE[key] = bundle
        return bundle


class EntityRulerStage(PipelineStage):
    def __init__(
        self,
        ruler: FOLIOEntityRuler | None = None,
        embedding_service=None,
        job_store=None,
        registry_embeddings: bool = False,
    ) -> None:
        # An injected ruler (tests/scripts) is used verbatim and loaded per stage;
        # otherwise the stage borrows the shared, cached ruler for the job's ontology.
        self._owns_ruler = ruler is None
        self._bundle: _RulerBundle | None = None
        self.ruler = ruler or FOLIOEntityRuler()
        self._embedding_service = embedding_service
        # When True (production), fetch the per-ontology embedding service from the
        # registry at run time (Canon jobs semantic-match against Canon vectors);
        # when False (tests/back-compat), the injected service is used verbatim.
        self._registry_embeddings = registry_embeddings
        # Optional: lets this stage flush the fast deterministic annotations
        # mid-execute so the UI renders them immediately, before the slower
        # semantic (embedding) pass runs. When None, no early flush happens.
        self._job_store = job_store
        self._patterns_loaded = False
        self._iri_to_branch: dict[str, str] = {}
        self._iri_to_concept: dict[str, object] = {}  # IRI → FOLIOConcept

    def _ensure_patterns_loaded(self, ontology_id: str = "folio") -> None:
        """Load ontology patterns into the EntityRuler on first use."""
        if self._patterns_loaded:
            return
        if self._owns_ruler:
            try:
                bundle = _get_ruler_bundle(ontology_id)
            except Exception:
                logger.warning("Failed to load FOLIO patterns into EntityRuler", exc_info=True)
                self._patterns_loaded = True
                return
            self._bundle = bundle
            self.ruler = bundle.ruler
            self._iri_to_branch = bundle.iri_to_branch
            self._iri_to_concept = bundle.iri_to_concept
            self._label_to_concepts = bundle.label_to_concepts
            self._patterns_loaded = True
            return
        try:
            folio_service = FolioService.get_instance(ontology_id)
            all_labels = folio_service.get_all_labels()
            if all_labels:
                self.ruler.load_patterns(all_labels)
                logger.info("EntityRuler loaded %d FOLIO patterns", len(all_labels))
            else:
                logger.warning("No FOLIO labels found — EntityRuler will be empty")

            # Build IRI→branch and IRI→concept maps from multi-label data
            # so we know about ALL concepts including multi-branch entries
            all_labels_multi = folio_service.get_all_labels_multi()
            self._label_to_concepts: dict[str, list] = {}
            for label_key, entries in all_labels_multi.items():
                for entry in entries:
                    fc = entry.concept
                    if fc.iri:
                        if fc.branch:
                            self._iri_to_branch[fc.iri] = fc.branch
                        self._iri_to_concept[fc.iri] = fc
                self._label_to_concepts[label_key] = entries
        except Exception:
            logger.warning("Failed to load FOLIO patterns into EntityRuler", exc_info=True)
        self._patterns_loaded = True

    @property
    def name(self) -> str:
        return "entity_ruler"

    async def execute(self, job: Job) -> Job:
        if job.result.canonical_text is None:
            return job

        full_text = job.result.canonical_text.full_text
        # Pattern loading, spaCy matching and annotation building are CPU-bound
        # (seconds on large documents): run them OFF the event loop so the SSE
        # poller, /health and other requests stay responsive.
        (
            matches, sentence_index, ruler_concepts, match_types, deterministic_annotations,
        ) = await asyncio.to_thread(self._run_deterministic, job.ontology, full_text)

        # --- Commit the FAST deterministic (Aho-Corasick) annotations first, then
        # flush, so the UI renders them immediately — before the slower semantic
        # (embedding) pass below. Progressive rendering stays snappy even with
        # embeddings enabled. ---
        job.result.metadata["ruler_concepts"] = ruler_concepts
        job.result.metadata["ruler_match_types"] = match_types
        job.result.annotations = deterministic_annotations

        # Early flush: persist deterministic tags now so the SSE stream emits them
        # without waiting for the embedding pass.
        if self._job_store is not None:
            job.updated_at = datetime.now(timezone.utc)
            try:
                await self._job_store.save(job)
            except Exception as e:
                logger.warning("EntityRuler early flush failed for job %s: %s", job.id, e)

        # --- Semantic EntityRuler: near-matches missed by exact matching. This
        # embeds many n-grams + FAISS-searches — CPU-bound, so run it OFF the
        # event loop (asyncio.to_thread) so it doesn't block the SSE poller or the
        # rest of the parallel phase. A failure here must NOT drop the
        # deterministic annotations already committed above. ---
        # Bind the embedding service built for THIS job's ontology so a Canon job
        # semantic-matches against Canon vectors (not FOLIO's). The matches_ontology
        # check below then passes as a safety assert; an empty/failed index skips.
        if self._registry_embeddings:
            from app.services.ontology.registry import get_embedding_service
            self._embedding_service = get_embedding_service(job.ontology)

        semantic_matches = []
        if (
            self._embedding_service is not None
            and self._embedding_service.matches_ontology(job.ontology)
            and self._embedding_service.index_size > 0
            and can_encode(self._embedding_service)
        ):
            known_spans = {(m.start_char, m.end_char) for m in matches}
            try:
                semantic_ruler = SemanticEntityRuler(self._embedding_service)
                semantic_matches = await asyncio.to_thread(
                    semantic_ruler.find_semantic_matches, full_text, known_spans
                )
            except Exception as e:
                logger.warning("SemanticEntityRuler skipped for job %s: %s", job.id, e)
                semantic_matches = []

        return await self._finish(job, matches, sentence_index, ruler_concepts, semantic_matches)

    def _find_matches(self, full_text: str) -> list[EntityRulerMatch]:
        if self._bundle is not None and self.ruler is self._bundle.ruler:
            return self._bundle.find_matches(full_text)
        return self.ruler.find_matches(full_text)

    def _run_deterministic(self, ontology_id: str, full_text: str):
        """Synchronous exact-match pass; runs on a worker thread."""
        self._ensure_patterns_loaded(ontology_id)
        sentence_index = build_sentence_index(full_text)
        matches = self._find_matches(full_text)

        ruler_concepts = []
        match_types = {}
        label_to_concepts = getattr(self, "_label_to_concepts", {})

        for match in matches:
            label_key = match.text.lower()
            # Emit ALL concepts that share this label (multi-branch support)
            multi_entries = label_to_concepts.get(label_key, [])
            if multi_entries:
                for entry in multi_entries:
                    fc = entry.concept
                    branch = fc.branch or ""
                    is_multi_word = len(match.text.split()) > 1
                    conf = _CONFIDENCE.get((entry.label_type, is_multi_word), 0.50)
                    ruler_concepts.append(
                        ConceptMatch(
                            concept_text=match.text,
                            folio_iri=fc.iri,
                            folio_label=fc.preferred_label,
                            folio_definition=fc.definition,
                            folio_alt_labels=fc.alternative_labels if fc.alternative_labels else None,
                            branches=[branch] if branch else [],
                            branch_color=get_branch_color(branch) if branch else None,
                            confidence=conf,
                            source="entity_ruler",
                            match_type=entry.label_type,
                        ).model_dump()
                    )
            else:
                # Fallback: use the single match from the EntityRuler
                confidence = _match_confidence(match)
                branch = self._iri_to_branch.get(match.entity_id, "")
                fc = self._iri_to_concept.get(match.entity_id)
                ruler_concepts.append(
                    ConceptMatch(
                        concept_text=match.text,
                        folio_iri=match.entity_id,
                        folio_label=fc.preferred_label if fc else None,
                        folio_definition=fc.definition if fc else None,
                        folio_alt_labels=fc.alternative_labels if fc and fc.alternative_labels else None,
                        branches=[branch] if branch else [],
                        branch_color=get_branch_color(branch) if branch else None,
                        confidence=confidence,
                        source="entity_ruler",
                        match_type=match.match_type,
                    ).model_dump()
                )

            # Store match_type metadata — one entry per match text
            match_types[label_key] = {
                "match_type": match.match_type,
                "is_multi_word": len(match.text.split()) > 1,
                "confidence": _match_confidence(match),
                "folio_iri": match.entity_id,
            }

        deterministic_annotations = self._dedupe_annotations(
            self._build_preliminary_annotations(matches, full_text, sentence_index)
        )
        return matches, sentence_index, ruler_concepts, match_types, deterministic_annotations

    async def _finish(self, job, matches, sentence_index, ruler_concepts, semantic_matches) -> Job:
        semantic_annotations: list[Annotation] = []
        for sm in semantic_matches:
            sm_fc = self._iri_to_concept.get(sm.iri)
            sm_label = sm_fc.preferred_label if sm_fc else sm.matched_label
            ruler_concepts.append(
                ConceptMatch(
                    concept_text=sm.text,
                    folio_iri=sm.iri,
                    folio_label=sm_label,
                    confidence=sm.similarity,
                    source="semantic_ruler",
                ).model_dump()
            )
            ann = Annotation(
                span=Span(
                    start=sm.start, end=sm.end, text=sm.text,
                    sentence_text=find_sentence_for_span(sentence_index, sm.start, sm.end),
                ),
                concepts=[ConceptMatch(
                    concept_text=sm.text,
                    folio_iri=sm.iri,
                    folio_label=sm_label,
                    confidence=sm.similarity,
                    source="semantic_ruler",
                )],
                state="preliminary",
            )
            record_lineage(
                ann, "semantic_ruler", "created",
                detail=f"Semantic match to '{sm.matched_label}' (similarity={sm.similarity:.2f})",
                confidence=sm.similarity,
            )
            semantic_annotations.append(ann)

        if semantic_matches:
            logger.info(
                "SemanticEntityRuler found %d additional matches for job %s",
                len(semantic_matches), job.id,
            )
            # Keep ruler_concepts metadata in sync (now includes semantic matches)
            # and merge the semantic annotations with the committed deterministic
            # set, re-deduping overlaps.
            job.result.metadata["ruler_concepts"] = ruler_concepts
            job.result.annotations = await asyncio.to_thread(
                self._dedupe_annotations, list(job.result.annotations) + semantic_annotations
            )

        # Activity log
        preferred = sum(1 for m in matches if m.match_type == "preferred")
        alternative = len(matches) - preferred
        msg = f"Found {len(ruler_concepts)} matches ({preferred} preferred, {alternative} alternative)"
        if semantic_matches:
            msg += f" + {len(semantic_matches)} semantic"
        log = job.result.metadata.setdefault("activity_log", [])
        log.append({"ts": datetime.now(timezone.utc).isoformat(), "stage": self.name, "msg": msg})

        logger.info("EntityRuler found %d total matches for job %s", len(ruler_concepts), job.id)
        return job

    @staticmethod
    def _dedupe_annotations(annotations: list[Annotation]) -> list[Annotation]:
        """Resolve overlapping spans: allow containment, resolve partial overlaps (longer wins)."""
        annotations = sorted(annotations, key=lambda a: (a.span.start, -(a.span.end - a.span.start)))
        deduped: list[Annotation] = []
        for ann in annotations:
            dominated = False
            for i, kept in enumerate(deduped):
                if ann.span.start >= kept.span.end or ann.span.end <= kept.span.start:
                    continue  # no overlap
                # Identical span — skip
                if ann.span.start == kept.span.start and ann.span.end == kept.span.end:
                    dominated = True
                    break
                # Containment (either direction) — allow both
                if ann.span.start >= kept.span.start and ann.span.end <= kept.span.end:
                    continue
                if kept.span.start >= ann.span.start and kept.span.end <= ann.span.end:
                    continue
                # Partial overlap — longer wins
                ann_len = ann.span.end - ann.span.start
                kept_len = kept.span.end - kept.span.start
                if ann_len > kept_len:
                    deduped[i] = ann
                dominated = True
                break
            if not dominated:
                deduped.append(ann)
        deduped.sort(key=lambda a: (a.span.start, -(a.span.end - a.span.start)))
        return deduped

    def _build_preliminary_annotations(
        self, matches: list[EntityRulerMatch], full_text: str,
        sentence_index: list[tuple[int, int, str]] | None = None,
    ) -> list[Annotation]:
        """Build preliminary Annotation objects from EntityRuler matches."""
        annotations: list[Annotation] = []
        for match in matches:
            confidence = _match_confidence(match)
            branch = self._iri_to_branch.get(match.entity_id, "")
            is_multi = "multi-word" if len(match.text.split()) > 1 else "single-word"
            sent = (
                find_sentence_for_span(sentence_index, match.start_char, match.end_char)
                if sentence_index else None
            )
            fc = self._iri_to_concept.get(match.entity_id)
            ann = Annotation(
                span=Span(
                    start=match.start_char,
                    end=match.end_char,
                    text=full_text[match.start_char:match.end_char],
                    sentence_text=sent,
                ),
                concepts=[ConceptMatch(
                    concept_text=match.text,
                    folio_iri=match.entity_id,
                    folio_label=fc.preferred_label if fc else None,
                    folio_definition=fc.definition if fc else None,
                    folio_alt_labels=fc.alternative_labels if fc and fc.alternative_labels else None,
                    branches=[branch] if branch else [],
                    branch_color=get_branch_color(branch) if branch else None,
                    confidence=confidence,
                    source="entity_ruler",
                    match_type=match.match_type,
                )],
                state="preliminary",
            )
            record_lineage(
                ann, "entity_ruler", "created",
                detail=f"Matched {match.match_type} label '{match.text}' ({is_multi})",
                confidence=confidence,
            )
            annotations.append(ann)
        return annotations
