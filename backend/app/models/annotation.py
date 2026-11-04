from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field, model_serializer, model_validator


UNION_CONCEPT_FIELDS = ("region", "peer_iri", "peer_label", "peer_branches", "drifted")


class StageEvent(BaseModel):
    stage: str  # "entity_ruler", "reconciliation", "resolution", etc.
    action: str  # "created", "confirmed", "rejected", "enriched", "branch_assigned"
    detail: str = ""
    confidence: float | None = None
    timestamp: str = ""
    reasoning: str = ""


class FeedbackItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    rating: str  # "up" or "down"
    stage: str | None = None  # target a specific stage event, or None for whole annotation
    comment: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class Span(BaseModel):
    start: int
    end: int
    text: str
    sentence_text: str | None = None


class ConceptMatch(BaseModel):
    concept_text: str
    folio_iri: str | None = None
    folio_label: str | None = None
    folio_definition: str | None = None
    branches: list[str] = Field(default_factory=list)
    branch_color: str | None = None
    confidence: float = 0.0
    source: str = "llm"  # "llm", "entity_ruler", "semantic_ruler", "reconciled"
    match_type: str | None = None  # "preferred" or "alternative" (from EntityRuler)
    state: str = "preliminary"  # "preliminary", "confirmed", "rejected", "backup"
    hierarchy_path: list[str] | None = None
    iri_hash: str | None = None
    children_count: int | None = None
    translations: dict[str, str] | None = None
    folio_examples: list[str] | None = None
    folio_notes: list[str] | None = None
    folio_see_also: list[str] | None = None
    folio_source: str | None = None
    folio_alt_labels: list[str] | None = None
    folio_editorial_note: str | None = None
    folio_comment: str | None = None
    folio_description: str | None = None
    folio_history_note: str | None = None
    folio_country: str | None = None
    folio_deprecated: bool | None = None

    region: str | None = None
    peer_iri: str | None = None
    peer_label: str | None = None
    peer_branches: list[str] | None = None
    drifted: bool | None = None

    @model_serializer(mode="wrap")
    def _omit_union_defaults(self, handler):
        data = handler(self)
        for key in UNION_CONCEPT_FIELDS:
            if getattr(self, key) is None:
                data.pop(key, None)
        return data

    @model_validator(mode="before")
    @classmethod
    def _migrate_branch(cls, data):
        if isinstance(data, dict) and "branch" in data and "branches" not in data:
            b = data.pop("branch")
            data["branches"] = [b] if b else []
        return data


class Annotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    span: Span
    concepts: list[ConceptMatch] = Field(default_factory=list)
    state: str = "preliminary"  # "preliminary", "confirmed", "rejected"
    dismissed_at: str | None = None  # ISO timestamp when user dismissed
    lineage: list[StageEvent] = Field(default_factory=list)
    feedback: list[FeedbackItem] = Field(default_factory=list)


class IndividualClassLink(BaseModel):
    """Links an Individual to an OWL Class annotation."""

    annotation_id: str | None = None  # ID of the class Annotation
    folio_iri: str | None = None
    folio_label: str | None = None
    branch: str = ""
    relationship: str = "instance_of"
    confidence: float = 0.0


class Individual(BaseModel):
    """An OWL Individual — a named instance of one or more OWL Classes."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str  # Canonical/normalized name
    mention_text: str  # Exact text from document
    individual_type: str = "named_entity"  # "legal_citation" | "named_entity"
    span: Span
    class_links: list[IndividualClassLink] = Field(default_factory=list)
    confidence: float = 0.0
    source: str = "llm"  # "eyecite" | "citeurl" | "regex" | "spacy_ner" | "llm" | "hybrid"
    normalized_form: str | None = None  # Canonical citation form
    url: str | None = None  # URL from CiteURL normalization
    lineage: list[StageEvent] = Field(default_factory=list)
    feedback: list[FeedbackItem] = Field(default_factory=list)


class TripleLink(BaseModel):
    """Links a triple component (subject/predicate/object) to a FOLIO entity."""

    entity_type: str  # "concept" | "individual" | "property"
    entity_id: str | None = None
    folio_iri: str | None = None
    folio_label: str | None = None
    confidence: float = 0.0


class SPOTriple(BaseModel):
    """A first-class subject-predicate-object triple extracted from text."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    subject: str
    predicate: str
    object: str
    sentence: str
    sentence_index: int = 0
    subject_span: Span | None = None
    predicate_span: Span | None = None
    object_span: Span | None = None
    subject_links: list[TripleLink] = Field(default_factory=list)
    predicate_links: list[TripleLink] = Field(default_factory=list)
    object_links: list[TripleLink] = Field(default_factory=list)
    voice: str = "active"  # "active" | "passive"
    normalized: bool = False  # True if passive was restructured
    confidence: float = 0.0
    source: str = "spacy"
    lineage: list[StageEvent] = Field(default_factory=list)


class SentencePOS(BaseModel):
    """Compact per-sentence POS tag storage."""

    sentence_index: int
    start: int
    end: int
    text: str
    tokens: list[str] = Field(default_factory=list)
    pos_tags: list[str] = Field(default_factory=list)  # NOUN, VERB, ADJ, ...
    fine_tags: list[str] = Field(default_factory=list)  # NN, VBD, JJ, ... (Penn Treebank)
    dep_labels: list[str] = Field(default_factory=list)  # nsubj, ROOT, dobj, ...
    head_indices: list[int] = Field(default_factory=list)


class PropertyAnnotation(BaseModel):
    """An OWL ObjectProperty match — a verb/relation found in the text."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    property_text: str  # Exact text from document
    folio_iri: str | None = None
    folio_label: str | None = None
    folio_definition: str | None = None
    folio_examples: list[str] | None = None
    folio_alt_labels: list[str] | None = None
    domain_iris: list[str] = Field(default_factory=list)
    range_iris: list[str] = Field(default_factory=list)
    inverse_of_iri: str | None = None
    inverse_of_label: str | None = None
    span: Span
    confidence: float = 0.0
    source: str = "aho_corasick"  # "aho_corasick" | "llm"
    match_type: str | None = None  # "preferred" or "alternative"
    lineage: list[StageEvent] = Field(default_factory=list)
    feedback: list[FeedbackItem] = Field(default_factory=list)


def stamp_union_concept(concept: ConceptMatch, service, *, cache=None) -> ConceptMatch:
    """Attach overlap metadata only when resolving through the virtual union."""
    if getattr(service, "ontology_id", None) != "both" or not concept.folio_iri:
        return concept
    iri = concept.folio_iri
    if cache is not None and iri in cache:
        for key, value in cache[iri].items():
            setattr(concept, key, value.copy() if isinstance(value, list) else value)
        return concept
    primary = service.get_concept(iri)
    if primary is None:
        if cache is not None:
            cache[iri] = {}
        return concept
    concept.folio_iri = primary.iri
    concept.iri_hash = primary.iri.rsplit("/", 1)[-1]
    concept.region = primary.region
    concept.peer_iri = primary.peer_iri
    concept.peer_label = primary.peer_label
    concept.drifted = primary.drifted
    keys = ("folio_iri", "iri_hash", "region", "peer_iri", "peer_label", "drifted")
    if concept.peer_iri:
        peer = service.service_for_iri(concept.peer_iri).get_concept(concept.peer_iri)
        concept.peer_branches = [peer.branch] if peer and peer.branch else []
        keys += ("peer_branches",)
    if cache is not None:
        fields = {}
        for key in keys:
            value = getattr(concept, key)
            fields[key] = value.copy() if isinstance(value, list) else value
        cache[iri] = fields
    return concept


def stamp_union_dict(d: dict, service, *, cache=None) -> dict:
    """Return the stamped model fields, retaining extra dictionary metadata."""
    return dict(d, **stamp_union_concept(ConceptMatch(**d), service, cache=cache).model_dump())


def stamp_union_annotations(annotations, service) -> None:
    for annotation in annotations:
        for concept in annotation.concepts:
            stamp_union_concept(concept, service)
