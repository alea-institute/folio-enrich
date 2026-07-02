"""Tests for ResolutionStage embedding context scoring."""

from unittest.mock import MagicMock

from app.pipeline.stages.resolution_stage import ResolutionStage


class TestApplyEmbeddingContextScores:
    def _make_stage(self, similarity_value=0.8, index_size=100):
        mock_emb = MagicMock()
        mock_emb.index_size = index_size
        mock_emb.similarity.return_value = similarity_value
        # Embedding-context scoring is now batched via similarity_batch().
        mock_emb.similarity_batch.side_effect = lambda pairs: [similarity_value] * len(pairs)
        return ResolutionStage(embedding_service=mock_emb), mock_emb

    def test_blends_60_40(self):
        stage, mock_emb = self._make_stage(similarity_value=0.6)
        concepts = [{
            "concept_text": "breach of contract",
            "folio_definition": "Failure to perform contractual obligations",
            "confidence": 0.80,
        }]
        stage._apply_embedding_context_scores(concepts, "The breach of contract was clear.")
        # 0.80 * 0.6 + 0.6 * 0.4 = 0.48 + 0.24 = 0.72
        assert abs(concepts[0]["confidence"] - 0.72) < 1e-4

    def test_records_lineage_event(self):
        stage, _ = self._make_stage(similarity_value=0.7)
        concepts = [{
            "concept_text": "damages",
            "folio_definition": "Monetary compensation",
            "confidence": 0.90,
        }]
        stage._apply_embedding_context_scores(concepts, "The damages were substantial.")
        events = concepts[0].get("_lineage_events", [])
        assert len(events) == 1
        assert events[0]["stage"] == "resolution"
        assert events[0]["action"] == "embedding_context"

    def test_skips_when_no_embedding_service(self):
        stage = ResolutionStage(embedding_service=None)
        concepts = [{"concept_text": "test", "folio_definition": "def", "confidence": 0.80}]
        stage._apply_embedding_context_scores(concepts, "Some text about test.")
        assert concepts[0]["confidence"] == 0.80

    def test_skips_when_index_empty(self):
        stage, _ = self._make_stage(index_size=0)
        concepts = [{"concept_text": "test", "folio_definition": "def", "confidence": 0.80}]
        stage._apply_embedding_context_scores(concepts, "Some text about test.")
        assert concepts[0]["confidence"] == 0.80

    def test_skips_when_no_definition(self):
        stage, mock_emb = self._make_stage()
        concepts = [{"concept_text": "test", "folio_definition": "", "confidence": 0.80}]
        stage._apply_embedding_context_scores(concepts, "Some text about test.")
        assert concepts[0]["confidence"] == 0.80
        mock_emb.similarity_batch.assert_not_called()

    def test_handles_similarity_exception(self):
        stage, mock_emb = self._make_stage()
        mock_emb.similarity_batch.side_effect = Exception("embedding error")
        concepts = [{"concept_text": "test", "folio_definition": "def", "confidence": 0.80}]
        stage._apply_embedding_context_scores(concepts, "Some text about test.")
        # Confidence unchanged on exception
        assert concepts[0]["confidence"] == 0.80

    def test_falls_back_to_concept_text_when_not_in_document(self):
        stage, mock_emb = self._make_stage(similarity_value=0.5)
        concepts = [{
            "concept_text": "habeas corpus",
            "folio_definition": "A writ requiring a person to be brought before a judge",
            "confidence": 0.90,
        }]
        # Concept text not in the document
        stage._apply_embedding_context_scores(concepts, "This document is about something else entirely.")
        # similarity_batch called with the concept_text as the sentence fallback
        mock_emb.similarity_batch.assert_called_once()
        pairs = mock_emb.similarity_batch.call_args[0][0]
        assert pairs[0][0] == "habeas corpus"  # fell back to concept_text

    def test_clamps_similarity_above_1(self):
        stage, mock_emb = self._make_stage(similarity_value=1.5)
        concepts = [{"concept_text": "test", "folio_definition": "def", "confidence": 0.80}]
        stage._apply_embedding_context_scores(concepts, "test context.")
        # Clamped to 1.0: 0.80 * 0.6 + 1.0 * 0.4 = 0.88
        assert abs(concepts[0]["confidence"] - 0.88) < 1e-4


class TestAttachBackupCandidates:
    """Backup/runner-up candidate search (Option A skip + B confidence cap)."""

    def _fake_alt(self, iri, label, conf, branch="Objectives"):
        m = MagicMock()
        fc = MagicMock()
        fc.iri, fc.preferred_label, fc.definition, fc.alternative_labels = iri, label, "d", []
        m.folio_concept = fc
        m.concept_text, m.branches, m.branch_color = label, [branch], ""
        m.confidence, m.iri_hash, m.source = conf, iri.rsplit("/", 1)[-1], "matched"
        return m

    def _stage(self, alternates):
        resolver = MagicMock()
        resolver.resolve_multi.return_value = alternates
        return ResolutionStage(resolver=resolver), resolver

    def test_skips_backup_search_for_exact_iri(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "skip_backups_for_exact_matches", True)
        stage, resolver = self._stage([])
        rd = {"folio_iri": "https://x/R1", "confidence": 0.55, "concept_text": "Agreement"}
        stage._attach_backup_candidates(rd, {"concept_text": "Agreement", "folio_iri": "https://x/R1"})
        resolver.resolve_multi.assert_not_called()  # A: definitive match → no search
        assert "_backup_candidates" not in rd

    def test_runs_backup_search_for_ambiguous_concept(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "skip_backups_for_exact_matches", True)
        alts = [self._fake_alt("https://x/R2", "Alt A", 0.95),
                self._fake_alt("https://x/R3", "Alt B", 0.90)]
        stage, resolver = self._stage(alts)
        rd = {"folio_iri": "", "confidence": 0.50, "concept_text": "vague term"}
        stage._attach_backup_candidates(rd, {"concept_text": "vague term"})  # no exact IRI
        resolver.resolve_multi.assert_called_once()  # ambiguous → search still runs
        assert rd.get("_backup_candidates")

    def test_backup_confidence_capped_at_primary(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "skip_backups_for_exact_matches", False)  # force search
        alts = [self._fake_alt("https://x/R2", "Alt A", 0.95)]
        stage, resolver = self._stage(alts)
        rd = {"folio_iri": "https://x/R1", "confidence": 0.55, "concept_text": "Agreement"}
        stage._attach_backup_candidates(rd, {"concept_text": "Agreement", "folio_iri": "https://x/R1"})
        backups = rd.get("_backup_candidates", [])
        assert backups
        assert all(b["confidence"] <= 0.55 for b in backups)  # B: never above primary
