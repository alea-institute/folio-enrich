"""Tests for spaCy NER cross-validation (per-ontology, default-off).

Covers:
- NER entities harvested from the existing spaCy parse (no extra pass).
- Default-off is a complete no-op (byte-neutral): no metadata written, no
  confidence change, no lineage.
- Flag-on FOLIO agreement (+boost) and contradiction (-penalty).
- Flag-on Canon GPE→Place agreement.
- No NER overlap → no change (recall preserved).
- Unknown ontology → no-op.
"""
from __future__ import annotations

import pytest

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.document import CanonicalText, DocumentFormat, DocumentInput, TextChunk
from app.models.job import Job, JobResult, JobStatus
from app.pipeline.stages.reconciliation_stage import (
    ReconciliationStage,
    _find_overlapping_ner,
)
from app.services.dependency.parser import DependencyParser


def _make_annotation(text: str, start: int, end: int, branch: str, conf: float = 0.5):
    return Annotation(
        span=Span(start=start, end=end, text=text),
        concepts=[ConceptMatch(concept_text=text, branches=[branch], confidence=conf)],
        state="preliminary",
    )


def _make_job(
    annotations: list[Annotation],
    ner_entities: list[dict],
    ontology: str = "folio",
    text: str = "placeholder text",
) -> Job:
    result = JobResult()
    result.canonical_text = CanonicalText(
        full_text=text,
        chunks=[TextChunk(text=text, start_offset=0, end_offset=len(text), chunk_index=0)],
    )
    result.annotations = annotations
    result.metadata["spacy_ner_entities"] = ner_entities
    return Job(
        input=DocumentInput(content=text, format=DocumentFormat.PLAIN_TEXT, ontology=ontology),
        status=JobStatus.COMPLETED,
        result=result,
    )


# ── Parser: NER harvested from the existing parse ────────────────────


def test_parser_returns_ner_entities_from_existing_parse():
    parser = DependencyParser()
    text = "Barack Obama visited Microsoft in California."
    triples, pos_data, ner_entities = parser.extract_triples_and_pos(text)
    assert isinstance(ner_entities, list)
    # spaCy en_core_web_sm reliably tags at least one entity here.
    assert len(ner_entities) >= 1
    for ent in ner_entities:
        assert set(ent.keys()) == {"text", "start", "end", "label"}
        assert isinstance(ent["start"], int)
        assert isinstance(ent["end"], int)
        assert text[ent["start"]:ent["end"]] == ent["text"]


# ── Overlap helper ────────────────────────────────────────────────────


def test_find_overlapping_ner_returns_label_on_overlap():
    ents = [{"text": "Obama", "start": 0, "end": 5, "label": "PERSON"}]
    assert _find_overlapping_ner(0, 5, ents) == "PERSON"
    assert _find_overlapping_ner(3, 10, ents) == "PERSON"  # partial overlap
    assert _find_overlapping_ner(6, 12, ents) is None       # no overlap


# ── Default-off: complete no-op ───────────────────────────────────────


def test_default_off_is_noop(monkeypatch):
    # A PERSON span landing on "Industry" WOULD be penalized if enabled.
    ann = _make_annotation("Acme", 0, 4, "Industry", conf=0.5)
    job = _make_job([ann], [{"text": "Acme", "start": 0, "end": 4, "label": "PERSON"}])

    # Default setting is False; assert the pass is a total no-op.
    import app.config
    assert app.config.settings.ner_cross_validation_enabled is False

    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (0, 0)
    assert ann.concepts[0].confidence == 0.5
    assert ann.lineage == []  # no lineage recorded


def test_triple_stage_writes_no_ner_metadata_when_off():
    """With the flag off, EarlyTripleStage must NOT add the NER metadata key."""
    import asyncio

    from app.pipeline.stages.triple_stage import EarlyTripleStage

    text = "Barack Obama visited Microsoft."
    result = JobResult()
    result.canonical_text = CanonicalText(
        full_text=text,
        chunks=[TextChunk(text=text, start_offset=0, end_offset=len(text), chunk_index=0)],
    )
    job = Job(
        input=DocumentInput(content=text, format=DocumentFormat.PLAIN_TEXT),
        status=JobStatus.COMPLETED,
        result=result,
    )
    asyncio.run(EarlyTripleStage().execute(job))
    # Byte-neutral: nothing new in metadata when the feature is off (default).
    assert "spacy_ner_entities" not in job.result.metadata


# ── Flag-on FOLIO ─────────────────────────────────────────────────────


def test_folio_agreement_boost(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    ann = _make_annotation("Jane Doe", 0, 8, "Actor / Player", conf=0.5)
    job = _make_job([ann], [{"text": "Jane Doe", "start": 0, "end": 8, "label": "PERSON"}])

    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (1, 0)
    assert ann.concepts[0].confidence == pytest.approx(0.54)  # +0.04
    assert any(e.action == "ner_boosted" for e in ann.lineage)


def test_folio_contradiction_penalty(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    # PERSON span landing on an "Industry" concept → contradiction.
    ann = _make_annotation("Acme", 0, 4, "Industry", conf=0.5)
    job = _make_job([ann], [{"text": "Acme", "start": 0, "end": 4, "label": "PERSON"}])

    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (0, 1)
    assert ann.concepts[0].confidence == pytest.approx(0.42)  # -0.08
    assert any(e.action == "ner_penalized" for e in ann.lineage)


# ── Flag-on Canon: GPE → Place ───────────────────────────────────────


def test_canon_gpe_place_agreement(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    ann = _make_annotation("Jerusalem", 0, 9, "Place", conf=0.5)
    job = _make_job(
        [ann],
        [{"text": "Jerusalem", "start": 0, "end": 9, "label": "GPE"}],
        ontology="canon",
    )

    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (1, 0)
    assert ann.concepts[0].confidence == pytest.approx(0.54)
    assert any(e.action == "ner_boosted" for e in ann.lineage)


def test_canon_contradiction_penalty(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    # PERSON span landing on a "Place" concept → contradiction (Canon map).
    ann = _make_annotation("Peter", 0, 5, "Place", conf=0.5)
    job = _make_job(
        [ann],
        [{"text": "Peter", "start": 0, "end": 5, "label": "PERSON"}],
        ontology="canon",
    )
    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (0, 1)
    assert ann.concepts[0].confidence == pytest.approx(0.42)


# ── Recall preserved: no NER overlap ─────────────────────────────────


def test_no_ner_overlap_is_noop(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    ann = _make_annotation("motion", 20, 26, "Industry", conf=0.5)
    # NER entity is elsewhere (no overlap with span 20-26).
    job = _make_job([ann], [{"text": "Acme", "start": 0, "end": 4, "label": "PERSON"}])

    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (0, 0)
    assert ann.concepts[0].confidence == 0.5  # unchanged — recall preserved
    assert ann.lineage == []


def test_unmapped_ner_label_is_noop(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    # ORDINAL is not in the FOLIO affinity map → no change.
    ann = _make_annotation("first", 0, 5, "Industry", conf=0.5)
    job = _make_job([ann], [{"text": "first", "start": 0, "end": 5, "label": "ORDINAL"}])
    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (0, 0)
    assert ann.concepts[0].confidence == 0.5


# ── Unknown ontology → no-op ─────────────────────────────────────────


def test_unknown_ontology_is_noop(monkeypatch):
    monkeypatch.setattr("app.config.settings.ner_cross_validation_enabled", True)
    ann = _make_annotation("Acme", 0, 4, "Industry", conf=0.5)
    job = _make_job(
        [ann],
        [{"text": "Acme", "start": 0, "end": 4, "label": "PERSON"}],
        ontology="mystery",
    )
    boosted, penalized = ReconciliationStage._apply_ner_adjustments(job)
    assert (boosted, penalized) == (0, 0)
    assert ann.concepts[0].confidence == 0.5
