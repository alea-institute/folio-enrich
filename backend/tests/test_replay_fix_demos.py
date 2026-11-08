"""Replay regression coverage without loading services or the real ontology."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models.annotation import Annotation, Span
from app.models.job import Job, JobStatus
from scripts import replay_fix_demos


class ReplayStatusTest(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_baked_status_when_stages_change_it(self):
        class MatchingStage:
            def __init__(self, **kwargs):
                pass

            async def execute(self, job):
                job.status = JobStatus.MATCHING

        modules = {
            f"app.pipeline.stages.{module}": SimpleNamespace(**{name: MatchingStage})
            for module, name in (
                ("entity_ruler_stage", "EntityRulerStage"),
                ("reconciliation_stage", "ReconciliationStage"),
                ("resolution_stage", "ResolutionStage"),
                ("string_match_stage", "StringMatchStage"),
                ("dependency_stage", "TripleEnrichmentStage"),
            )
        }
        modules["app.pipeline.stages.individual_stage"] = SimpleNamespace(
            _resolve_class_link_iris=lambda *args: None
        )
        modules["scripts.slim_demos"] = SimpleNamespace(slim_demo_cache=lambda raw: None)

        for status in (JobStatus.COMPLETED, JobStatus.FAILED):
            with self.subTest(status=status.value), tempfile.TemporaryDirectory() as directory:
                job = Job(status=status)
                # Clearing this annotation makes replay take the payload/write path.
                job.result.annotations = [Annotation(span=Span(start=0, end=4, text="test"))]
                path = Path(directory) / "sample.json"
                path.write_text(json.dumps({"cache": {"job": job.model_dump(mode="json")}}))

                def build_payload(replayed_job, doc_input):
                    self.assertEqual(replayed_job.status, status)
                    return {"job": replayed_job.model_dump(mode="json")}

                build = Mock(side_effect=build_payload)
                modules["scripts.generate_demos"] = SimpleNamespace(build_cache_payload=build)
                with patch.dict("sys.modules", modules), patch.object(
                    replay_fix_demos, "_demos_dir", return_value=Path(directory)
                ):
                    changed = await replay_fix_demos.replay_one(
                        "sample", folio=None, emb=None, dry_run=False
                    )

                self.assertTrue(changed)
                build.assert_called_once()
                self.assertEqual(json.loads(path.read_text())["cache"]["job"]["status"], status)


if __name__ == "__main__":
    unittest.main()


class ReplayConceptChangeTest(unittest.IsolatedAsyncioTestCase):
    def test_summary_uses_annotation_multiset(self):
        from app.models.annotation import ConceptMatch
        job = Job()
        first = Annotation(span=Span(start=0, end=5, text="Court"),
                           concepts=[ConceptMatch(concept_text="Court", folio_iri="iri:court")])
        second = first.model_copy(deep=True)
        second.span = Span(start=10, end=15, text="Court")
        job.result.annotations = [first, second]
        before = replay_fix_demos._concept_summary(job)["annotation_keys"]
        job.result.annotations.reverse()
        self.assertEqual(before, replay_fix_demos._concept_summary(job)["annotation_keys"])
        job.result.annotations = [first, first.model_copy(deep=True)]
        self.assertNotEqual(before, replay_fix_demos._concept_summary(job)["annotation_keys"])

    async def test_detects_iri_and_state_changes_without_count_or_agreement_change(self):
        from app.models.annotation import ConceptMatch
        for change in ('iri', 'state'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                job = Job(status=JobStatus.COMPLETED)
                job.result.annotations = [Annotation(span=Span(start=0, end=5, text='Court'), concepts=[ConceptMatch(concept_text='Court', folio_iri='iri:old')], state='confirmed')]
                original = job.result.annotations[0].model_copy(deep=True)
                path = Path(directory) / 'sample.json'
                path.write_text(json.dumps({'cache': {'job': job.model_dump(mode='json')}}))

                class Stage:
                    def __init__(self, **kwargs):
                        pass

                    async def execute(self, replayed):
                        annotation = original.model_copy(deep=True)
                        if change == 'iri':
                            annotation.concepts[0].folio_iri = 'iri:new'
                        else:
                            annotation.state = 'rejected'
                        replayed.result.annotations = [annotation]

                modules = {f'app.pipeline.stages.{module}': SimpleNamespace(**{name: Stage}) for module, name in (
                    ('entity_ruler_stage', 'EntityRulerStage'), ('reconciliation_stage', 'ReconciliationStage'),
                    ('resolution_stage', 'ResolutionStage'), ('string_match_stage', 'StringMatchStage'),
                    ('dependency_stage', 'TripleEnrichmentStage'))}
                modules['app.pipeline.stages.individual_stage'] = SimpleNamespace(_resolve_class_link_iris=lambda *args: None)
                with patch.dict('sys.modules', modules), patch.object(replay_fix_demos, '_demos_dir', return_value=Path(directory)), self.assertLogs('replay', level='INFO') as logs:
                    changed = await replay_fix_demos.replay_one('sample', None, None, dry_run=True)
                self.assertTrue(changed)
                self.assertIn(f'IRI-spans changed: {1 if change == "iri" else 0}', '\n'.join(logs.output))
