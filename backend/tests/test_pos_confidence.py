"""Tests for POS-powered confidence modulation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.annotation import (
    Annotation,
    ConceptMatch,
    PropertyAnnotation,
    Span,
)
from app.services.nlp.pos_lookup import (
    get_fine_tags_for_span,
    get_majority_pos,
    get_pos_for_span,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sentence_pos(
    text: str,
    tokens: list[str],
    pos_tags: list[str],
    fine_tags: list[str] | None = None,
    start: int = 0,
) -> dict:
    """Build a sentence_pos dict mimicking SentencePOS.model_dump()."""
    return {
        "sentence_index": 0,
        "start": start,
        "end": start + len(text),
        "text": text,
        "tokens": tokens,
        "pos_tags": pos_tags,
        "fine_tags": fine_tags or [""] * len(tokens),
        "dep_labels": [""] * len(tokens),
        "head_indices": list(range(len(tokens))),
    }


# ---------------------------------------------------------------------------
# POS Lookup Utility Tests
# ---------------------------------------------------------------------------

class TestGetPosForSpan:
    def test_single_token(self):
        sent = _make_sentence_pos(
            "The court granted the motion",
            ["The", "court", "granted", "the", "motion"],
            ["DET", "NOUN", "VERB", "DET", "NOUN"],
            start=0,
        )
        # "granted" starts at index 10
        assert get_pos_for_span(10, 17, [sent]) == ["VERB"]

    def test_multi_token(self):
        sent = _make_sentence_pos(
            "legal contract was signed",
            ["legal", "contract", "was", "signed"],
            ["ADJ", "NOUN", "AUX", "VERB"],
            start=0,
        )
        # "legal contract" = 0..14
        assert get_pos_for_span(0, 14, [sent]) == ["ADJ", "NOUN"]

    def test_span_outside_sentences(self):
        sent = _make_sentence_pos("hello world", ["hello", "world"], ["NOUN", "NOUN"], start=0)
        assert get_pos_for_span(100, 110, [sent]) == []

    def test_empty_sentence_pos(self):
        assert get_pos_for_span(0, 5, []) == []


class TestGetMajorityPos:
    def test_returns_most_frequent(self):
        sent = _make_sentence_pos(
            "the big red ball",
            ["the", "big", "red", "ball"],
            ["DET", "ADJ", "ADJ", "NOUN"],
            start=0,
        )
        # "big red ball" = 4..16, pos = ADJ, ADJ, NOUN → majority = ADJ
        assert get_majority_pos(4, 16, [sent]) == "ADJ"

    def test_single_token_returns_that_pos(self):
        sent = _make_sentence_pos("grant", ["grant"], ["VERB"], start=0)
        assert get_majority_pos(0, 5, [sent]) == "VERB"

    def test_no_data_returns_none(self):
        assert get_majority_pos(0, 5, []) is None


class TestGetFineTagsForSpan:
    def test_returns_fine_tags(self):
        sent = _make_sentence_pos(
            "The court granted the motion",
            ["The", "court", "granted", "the", "motion"],
            ["DET", "NOUN", "VERB", "DET", "NOUN"],
            fine_tags=["DT", "NN", "VBD", "DT", "NN"],
            start=0,
        )
        assert get_fine_tags_for_span(10, 17, [sent]) == ["VBD"]


# ---------------------------------------------------------------------------
# Concept POS Penalty Tests (ReconciliationStage)
# ---------------------------------------------------------------------------

class TestConceptPosPenalty:
    def _make_job(self, ann_text, ann_start, pos_tag, match_type="alternative", confidence=0.60):
        """Create a minimal Job-like object for testing."""
        job = MagicMock()
        ann = Annotation(
            span=Span(start=ann_start, end=ann_start + len(ann_text), text=ann_text),
            concepts=[ConceptMatch(
                concept_text=ann_text,
                confidence=confidence,
                match_type=match_type,
                source="entity_ruler",
            )],
            state="confirmed",
        )
        job.result.annotations = [ann]
        sent = _make_sentence_pos(
            f"The {ann_text} was issued",
            ["The", ann_text, "was", "issued"],
            ["DET", pos_tag, "AUX", "VERB"],
            start=0,
        )
        job.result.metadata = {"sentence_pos": [sent]}
        return job, ann

    def test_verb_concept_penalized(self):
        from app.pipeline.stages.reconciliation_stage import ReconciliationStage

        job, ann = self._make_job("grant", 4, "VERB")
        adjusted = ReconciliationStage._apply_pos_penalties(job)
        assert adjusted == 1
        assert ann.concepts[0].confidence < 0.60

    def test_noun_concept_not_penalized(self):
        from app.pipeline.stages.reconciliation_stage import ReconciliationStage

        job, ann = self._make_job("grant", 4, "NOUN")
        adjusted = ReconciliationStage._apply_pos_penalties(job)
        assert adjusted == 0
        assert ann.concepts[0].confidence == 0.60

    def test_multi_word_not_penalized(self):
        from app.pipeline.stages.reconciliation_stage import ReconciliationStage

        job = MagicMock()
        ann = Annotation(
            span=Span(start=4, end=16, text="legal motion"),
            concepts=[ConceptMatch(
                concept_text="legal motion",
                confidence=0.60,
                match_type="alternative",
                source="entity_ruler",
            )],
            state="confirmed",
        )
        job.result.annotations = [ann]
        sent = _make_sentence_pos(
            "The legal motion was filed",
            ["The", "legal", "motion", "was", "filed"],
            ["DET", "ADJ", "NOUN", "AUX", "VERB"],
            start=0,
        )
        job.result.metadata = {"sentence_pos": [sent]}
        adjusted = ReconciliationStage._apply_pos_penalties(job)
        assert adjusted == 0

    def test_penalty_below_threshold_rejects(self):
        from app.pipeline.stages.reconciliation_stage import ReconciliationStage

        job, ann = self._make_job("grant", 4, "VERB", confidence=0.18)
        ReconciliationStage._apply_pos_penalties(job)
        assert ann.state == "rejected"

    def test_pos_disabled_no_change(self):
        from app.pipeline.stages.reconciliation_stage import ReconciliationStage

        job, ann = self._make_job("grant", 4, "VERB")
        with patch("app.config.settings") as mock_settings:
            mock_settings.pos_confidence_enabled = False
            mock_settings.pos_tagging_enabled = True
            adjusted = ReconciliationStage._apply_pos_penalties(job)
        assert adjusted == 0
        assert ann.concepts[0].confidence == 0.60


# ---------------------------------------------------------------------------
# Branch POS Affinity Tests (BranchJudgeStage)
# ---------------------------------------------------------------------------

class TestBranchPosAffinity:
    def test_verb_action_branch_boost(self):
        from app.pipeline.stages.branch_judge_stage import BranchJudgeStage

        affinity = BranchJudgeStage._pos_branch_affinity("VERB", "Legal Process")
        assert affinity > 0

    def test_noun_entity_branch_boost(self):
        from app.pipeline.stages.branch_judge_stage import BranchJudgeStage

        affinity = BranchJudgeStage._pos_branch_affinity("NOUN", "Legal Document")
        assert affinity > 0

    def test_mismatch_penalty(self):
        from app.pipeline.stages.branch_judge_stage import BranchJudgeStage

        affinity = BranchJudgeStage._pos_branch_affinity("VERB", "Legal Document")
        assert affinity < 0


# ---------------------------------------------------------------------------
# Property POS Penalty Tests (LLMPropertyStage)
# ---------------------------------------------------------------------------

class TestPropertyPosPenalty:
    def _make_job_with_props(self, prop_text, pos_tag, source="aho_corasick"):
        job = MagicMock()
        prop = PropertyAnnotation(
            property_text=prop_text,
            folio_label=prop_text,
            span=Span(start=4, end=4 + len(prop_text), text=prop_text),
            confidence=0.70,
            source=source,
        )
        sent = _make_sentence_pos(
            f"The {prop_text} was important",
            ["The", prop_text, "was", "important"],
            ["DET", pos_tag, "AUX", "ADJ"],
            start=0,
        )
        job.result.metadata = {"sentence_pos": [sent]}
        return job, prop

    def test_noun_property_penalized(self):
        from app.pipeline.stages.property_stage import LLMPropertyStage

        job, prop = self._make_job_with_props("filing", "NOUN")
        adjusted = LLMPropertyStage._apply_pos_penalties(job, [prop])
        assert adjusted == 1
        assert prop.confidence < 0.70

    def test_verb_property_not_penalized(self):
        from app.pipeline.stages.property_stage import LLMPropertyStage

        job, prop = self._make_job_with_props("filing", "VERB")
        adjusted = LLMPropertyStage._apply_pos_penalties(job, [prop])
        assert adjusted == 0
        assert prop.confidence == 0.70

    def test_llm_property_skipped(self):
        from app.pipeline.stages.property_stage import LLMPropertyStage

        job, prop = self._make_job_with_props("filing", "NOUN", source="llm")
        adjusted = LLMPropertyStage._apply_pos_penalties(job, [prop])
        assert adjusted == 0


# ---------------------------------------------------------------------------
# Triple Confidence Tests (DependencyParser)
# ---------------------------------------------------------------------------

class TestTripleConfidence:
    def _mock_token(self, pos: str):
        tok = MagicMock()
        tok.pos_ = pos
        return tok

    def test_ideal_triple_high_confidence(self):
        from app.services.dependency.parser import DependencyParser

        parser = DependencyParser()
        conf = parser._compute_triple_confidence(
            self._mock_token("PROPN"),
            self._mock_token("VERB"),
            self._mock_token("NOUN"),
            is_passive=False,
        )
        assert conf == pytest.approx(0.80)

    def test_weak_triple_low_confidence(self):
        from app.services.dependency.parser import DependencyParser

        parser = DependencyParser()
        conf = parser._compute_triple_confidence(
            self._mock_token("ADJ"),
            self._mock_token("AUX"),
            self._mock_token("DET"),
            is_passive=False,
        )
        # base 0.50 + 0.10 (AUX counts) = 0.60
        assert conf == pytest.approx(0.60)

    def test_passive_penalty(self):
        from app.services.dependency.parser import DependencyParser

        parser = DependencyParser()
        active = parser._compute_triple_confidence(
            self._mock_token("NOUN"),
            self._mock_token("VERB"),
            self._mock_token("NOUN"),
            is_passive=False,
        )
        passive = parser._compute_triple_confidence(
            self._mock_token("NOUN"),
            self._mock_token("VERB"),
            self._mock_token("NOUN"),
            is_passive=True,
        )
        assert passive < active
        assert active - passive == pytest.approx(0.05)
