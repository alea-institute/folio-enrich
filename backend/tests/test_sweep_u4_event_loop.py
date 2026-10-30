"""U4: CPU-bound stage work must not stall the event loop.

Before the fix, EarlyTripleStage ran the full spaCy parse and EntityRulerStage
ran the spaCy EntityRuler synchronously inside ``async def execute``; on a
65 KB document the loop stalled for 15.5 s and /health took 7.65 s. These tests
run the real stages on a large synthetic document while a ticker coroutine wakes
every 50 ms, and assert the longest gap between ticks stays far below that.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.models.document import CanonicalText, TextChunk
from app.models.job import Job
from app.pipeline.stages.entity_ruler_stage import EntityRulerStage
from app.pipeline.stages.triple_stage import EarlyTripleStage
from app.services.entity_ruler.ruler import FOLIOEntityRuler
from app.services.folio.folio_service import FOLIOConcept, LabelInfo

TICK = 0.05
MAX_GAP = 1.0  # seconds; pre-fix stalls on this document were several seconds

_SENTENCES = [
    "The plaintiff filed a motion to dismiss the breach of contract claim in the district court.",
    "Defendant Acme Corporation argued that the lease agreement was terminated before the alleged breach.",
    "The court granted summary judgment because the indemnification clause did not apply to negligence.",
    "On appeal, the parties disputed whether the arbitration provision covered the employment dispute.",
    "The tenant paid rent late, and the landlord sent a notice of default under the lease agreement.",
    "Counsel for the respondent stipulated that the confidential information had been disclosed in error.",
]


def _large_text(target_chars: int = 250_000) -> str:
    parts: list[str] = []
    size = i = 0
    while size < target_chars:
        sentence = _SENTENCES[i % len(_SENTENCES)].replace("The ", f"In matter {i}, the ", 1)
        parts.append(sentence)
        size += len(sentence) + 1
        i += 1
    return " ".join(parts)


def _job(text: str) -> Job:
    job = Job()
    job.result.canonical_text = CanonicalText(
        full_text=text,
        chunks=[TextChunk(text=text, start_offset=0, end_offset=len(text), chunk_index=0)],
    )
    return job


async def _max_tick_gap(work) -> float:
    """Run *work* while a ticker sleeps TICK in a loop; return the longest gap."""
    done = asyncio.Event()
    gaps: list[float] = []

    async def ticker() -> None:
        last = time.perf_counter()
        while not done.is_set():
            await asyncio.sleep(TICK)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    tick_task = asyncio.create_task(ticker())
    await asyncio.sleep(0)  # let the ticker start before the work begins
    try:
        await work
    finally:
        done.set()
        await tick_task
    return max(gaps) if gaps else float("inf")


def _loaded_ruler() -> FOLIOEntityRuler:
    labels = {}
    for i, label in enumerate([
        "breach of contract", "motion to dismiss", "lease agreement", "summary judgment",
        "district court", "arbitration", "indemnification", "negligence", "landlord",
        "tenant", "confidential information", "employment", "notice of default",
    ]):
        concept = FOLIOConcept(
            iri=f"https://example.org/R{i}", preferred_label=label.title(),
            alternative_labels=[], definition="", branch="Area of Law", parent_iris=[],
        )
        labels[label] = LabelInfo(concept=concept, label_type="preferred", matched_label=label)
    ruler = FOLIOEntityRuler()
    ruler.load_patterns(labels)
    return ruler


@pytest.mark.asyncio
async def test_parallel_phase_stages_keep_event_loop_responsive():
    text = _large_text()
    triple_job, ruler_job = _job(text), _job(text)

    ruler_stage = EntityRulerStage(ruler=_loaded_ruler())
    ruler_stage._patterns_loaded = True  # injected ruler; no FOLIO load

    start = time.perf_counter()
    gap = await _max_tick_gap(asyncio.gather(
        EarlyTripleStage().execute(triple_job),
        ruler_stage.execute(ruler_job),
    ))
    elapsed = time.perf_counter() - start

    # The work really happened (and took long enough to matter)...
    assert triple_job.result.triples
    assert len(ruler_job.result.annotations) > 100
    assert elapsed > 2 * MAX_GAP, f"document too small to prove anything ({elapsed:.2f}s)"
    # ...yet the loop kept ticking throughout.
    assert gap < MAX_GAP, f"event loop stalled for {gap:.2f}s (total work {elapsed:.2f}s)"
