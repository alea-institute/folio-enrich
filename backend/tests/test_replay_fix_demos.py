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
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
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
