"""Early proposition pre-selection for the parallel pipeline phase."""

from __future__ import annotations

import logging
from uuid import NAMESPACE_URL, uuid5

from folio_propositions import ActorRef, AdjudicatorRef, Proposition

from app.models.job import Job
from app.pipeline.stages.base import PipelineStage
from app.services.llm.base import LLMProvider
from app.services.proposition.extractor import PropositionExtractor

logger = logging.getLogger(__name__)


class EarlyPropositionStage(PipelineStage):
    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm
        self._extractor = PropositionExtractor()

    @property
    def name(self) -> str:
        return "early_proposition"

    async def execute(self, job: Job) -> Job:
        from app.config import settings
        if not settings.proposition_extraction_enabled:
            return job

        candidates = self._extractor.extract(job)
        if self.llm is not None and job.result.canonical_text is not None:
            try:
                candidates.extend(await self._assist(job))
            except Exception:
                logger.warning("Proposition LLM assist failed", exc_info=True)

        deduplicated: dict[tuple[int | None, int | None, str], Proposition] = {}
        for candidate in candidates:
            key = (candidate.start_char, candidate.end_char, candidate.proposition_type)
            deduplicated.setdefault(key, candidate)
        job.result.propositions = sorted(
            deduplicated.values(), key=lambda p: (p.start_char or 0, p.end_char or 0)
        )
        return job

    async def _assist(self, job: Job) -> list[Proposition]:
        text = job.result.canonical_text.full_text
        prompt = (
            "Identify explicit proposition content spans in this judicial text. "
            "Return only spans supported verbatim by the text, with start_char, "
            "end_char, proposition_type, asserter_role, validator_mode (or null), "
            "and disposition.\n\n" + text
        )
        result = await self.llm.structured(prompt, schema={
            "type": "object",
            "properties": {
                "propositions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_char": {"type": "integer"},
                            "end_char": {"type": "integer"},
                            "proposition_type": {"type": "string"},
                            "asserter_role": {"type": "string"},
                            "validator_mode": {"type": ["string", "null"]},
                            "disposition": {"type": "string"},
                        },
                        "required": ["start_char", "end_char", "proposition_type"],
                    },
                }
            },
        })
        candidates: list[Proposition] = []
        for item in result.get("propositions", []):
            try:
                start = int(item["start_char"])
                end = int(item["end_char"])
                if not (0 <= start < end <= len(text)):
                    continue
                role = item.get("asserter_role", "party")
                validator_mode = item.get("validator_mode")
                candidates.append(Proposition(
                    id=str(uuid5(NAMESPACE_URL, f"folio-enrich:{job.id}:{start}:{end}")),
                    start_char=start,
                    end_char=end,
                    text=text[start:end],
                    proposition_type=item["proposition_type"],
                    asserter=ActorRef(role=role),
                    validator=(
                        AdjudicatorRef(role="court", mode=validator_mode)
                        if validator_mode else None
                    ),
                    disposition=item.get("disposition", "unresolved"),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return candidates
