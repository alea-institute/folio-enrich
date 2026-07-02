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


class TestSemanticBackupFilter:
    """Semantic-relevance filtering of backup candidates via the embedding pass."""

    def _make_stage(self, sim_map=None, index_size=100):
        """Build a stage whose similarity_batch returns per-pair sims.

        ``sim_map`` maps a substring found in the pair's second element (the
        definition/label being scored) to a similarity; default 0.5 otherwise.
        """
        sim_map = sim_map or {}

        def _batch(pairs):
            out = []
            for _sentence, text in pairs:
                score = 0.5
                for needle, value in sim_map.items():
                    if needle in text:
                        score = value
                        break
                out.append(score)
            return out

        mock_emb = MagicMock()
        mock_emb.index_size = index_size
        mock_emb.similarity_batch.side_effect = _batch
        return ResolutionStage(embedding_service=mock_emb), mock_emb

    def _backup(self, label, definition, confidence=0.9):
        return {
            "concept_text": "Court",
            "folio_iri": f"https://x/{label.replace(' ', '')}",
            "folio_label": label,
            "folio_definition": definition,
            "branches": ["Objectives"],
            "branch_color": "",
            "confidence": confidence,
            "source": "matched",
            "state": "backup",
            "iri_hash": label[:4],
            "folio_alt_labels": None,
        }

    def _concept(self, backups):
        return {
            "concept_text": "Court",
            "folio_definition": "A tribunal that adjudicates legal disputes",
            "confidence": 0.80,
            "_backup_candidates": backups,
        }

    def test_drops_below_threshold_keeps_above(self):
        stage, _ = self._make_stage(sim_map={"forum": 0.8, "costs": 0.2})
        concepts = [self._concept([
            self._backup("Court Forum", "The forum in which a legal action is heard"),
            self._backup("Court Costs", "The costs and fees assessed in litigation"),
        ])]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        labels = [b["folio_label"] for b in concepts[0]["_backup_candidates"]]
        assert labels == ["Court Forum"]  # junk dropped, relevant kept

    def test_survivors_sorted_by_sim_and_capped_at_primary(self):
        stage, _ = self._make_stage(sim_map={"forum": 0.9, "venue": 0.6})
        concepts = [self._concept([
            self._backup("Court Venue", "The venue where a case is tried"),
            self._backup("Court Forum", "The forum in which a legal action is heard"),
        ])]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        backups = concepts[0]["_backup_candidates"]
        # sorted by sim desc: Forum (0.9) before Venue (0.6)
        assert [b["folio_label"] for b in backups] == ["Court Forum", "Court Venue"]
        primary_conf = concepts[0]["confidence"]
        assert all(b["confidence"] <= primary_conf for b in backups)

    def test_all_below_threshold_removes_key(self):
        stage, _ = self._make_stage(sim_map={"costs": 0.1, "county": 0.15})
        concepts = [self._concept([
            self._backup("Court Costs", "The costs and fees assessed in litigation"),
            self._backup("Dade County", "A specific county circuit court"),
        ])]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        assert "_backup_candidates" not in concepts[0]

    def test_falls_back_to_label_when_no_definition(self):
        stage, mock_emb = self._make_stage(sim_map={"Court Forum": 0.8})
        concepts = [self._concept([self._backup("Court Forum", "")])]  # no definition
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        # scored against the label and kept
        assert [b["folio_label"] for b in concepts[0]["_backup_candidates"]] == ["Court Forum"]
        # a pair was queued using the label text
        pairs = mock_emb.similarity_batch.call_args[0][0]
        assert any(text == "Court Forum" for _sent, text in pairs)

    def test_noop_when_no_embedding_service(self):
        stage = ResolutionStage(embedding_service=None)
        backups = [self._backup("Court Costs", "irrelevant")]
        concepts = [self._concept(list(backups))]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        assert concepts[0]["_backup_candidates"] == backups  # unchanged

    def test_noop_when_index_empty(self):
        stage, _ = self._make_stage(index_size=0)
        backups = [self._backup("Court Costs", "irrelevant")]
        concepts = [self._concept(list(backups))]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        assert concepts[0]["_backup_candidates"] == backups  # unchanged

    def test_noop_on_similarity_exception(self):
        stage, mock_emb = self._make_stage()
        mock_emb.similarity_batch.side_effect = Exception("embedding error")
        backups = [self._backup("Court Costs", "irrelevant")]
        concepts = [self._concept(list(backups))]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        assert concepts[0]["_backup_candidates"] == backups  # unchanged

    def test_disabled_leaves_backups_unchanged(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "backup_semantic_filter_enabled", False)
        stage, mock_emb = self._make_stage(sim_map={"costs": 0.1})
        backups = [self._backup("Court Costs", "irrelevant noise")]
        concepts = [self._concept(list(backups))]
        stage._apply_embedding_context_scores(concepts, "The Court shall have jurisdiction.")
        assert concepts[0]["_backup_candidates"] == backups  # unchanged
        # only the primary definition was scored, not the backup
        pairs = mock_emb.similarity_batch.call_args[0][0]
        assert len(pairs) == 1

    def test_concept_without_backups_untouched(self):
        stage, _ = self._make_stage()
        concepts = [{
            "concept_text": "damages",
            "folio_definition": "Monetary compensation",
            "confidence": 0.90,
        }]
        stage._apply_embedding_context_scores(concepts, "The damages were substantial.")
        assert "_backup_candidates" not in concepts[0]
        # primary blend still applied: 0.90 * 0.6 + 0.5 * 0.4 = 0.74
        assert abs(concepts[0]["confidence"] - 0.74) < 1e-4
