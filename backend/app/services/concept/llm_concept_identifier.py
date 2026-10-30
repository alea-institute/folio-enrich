from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.models.annotation import ConceptMatch
from app.models.document import TextChunk
from app.services.llm.base import LLMProvider
from app.services.llm.prompts.concept_identification import (
    build_concept_identification_prompt,
)

logger = logging.getLogger(__name__)

# Max concept-identification requests in flight per batch. A 1 MB document is
# ~350 chunks; firing them all at once trips provider rate limits (429), and a
# failed chunk silently contributes no concepts.
MAX_CONCURRENT_CHUNK_REQUESTS = 8


class LLMConceptIdentifier:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def identify_concepts(
        self, chunk: TextChunk, ontology_id: str = "folio"
    ) -> list[ConceptMatch]:
        prompt = build_concept_identification_prompt(chunk.text, ontology_id)

        try:
            result = await self.llm.structured(
                prompt,
                schema={
                    "type": "object",
                    "properties": {
                        "concepts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "concept_text": {"type": "string"},
                                    "branch_hints": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "confidence": {"type": "number"},
                                },
                            },
                        }
                    },
                },
            )
        except Exception:
            logger.exception("LLM concept identification failed for chunk %d", chunk.chunk_index)
            return []

        concepts = []
        for item in result.get("concepts", []):
            concepts.append(
                ConceptMatch(
                    concept_text=item.get("concept_text", ""),
                    branches=item.get("branch_hints", []),
                    confidence=item.get("confidence", 0.0),
                    source="llm",
                )
            )
        return concepts

    async def identify_concepts_batch(
        self, chunks: list[TextChunk], ontology_id: str = "folio"
    ) -> dict[int, list[ConceptMatch]]:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHUNK_REQUESTS)

        async def bounded(chunk: TextChunk) -> list[ConceptMatch]:
            async with semaphore:
                return await self.identify_concepts(chunk, ontology_id)

        tasks = [bounded(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output: dict[int, list[ConceptMatch]] = {}
        for chunk, result in zip(chunks, results):
            if isinstance(result, Exception):
                logger.error("Chunk %d failed: %s", chunk.chunk_index, result)
                output[chunk.chunk_index] = []
            else:
                output[chunk.chunk_index] = result
        return output
