"""Run the talk's synthetic demo document through the FOLIO Enrich pipeline.

Uses the bake path from backend/scripts/generate_demos.py with the Codex CLI
subscription provider (no API key, no spend) and redirects the demo-format JSON
to evidence/enrich-result.json instead of frontend/demos/.

Usage (from backend/):
    .venv/bin/python ../docs/talks/2026-legal-data-ai-ready/tools/run_enrich.py
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from dataclasses import fields
from pathlib import Path

TALK_DIR = Path(__file__).resolve().parent.parent
REPO = TALK_DIR.parent.parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

import scripts.generate_demos as gd  # noqa: E402
from app.pipeline.orchestrator import TaskLLMs  # noqa: E402

DOC = TALK_DIR / "demo-document.md"
OUT = TALK_DIR / "evidence" / "enrich-result.json"
SLUG = "talk_distribution_breach"


def load_text() -> str:
    lines = DOC.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].lstrip().startswith("<!--"):
        lines = lines[1:]
    return "\n".join(lines).strip() + "\n"


async def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gd._demo_path = lambda ontology, slug: OUT  # redirect; never touch frontend/demos
    llm = gd.build_generation_llm("codex-cli", None, None, effort="medium")
    task_llms = TaskLLMs(**{f.name: llm for f in fields(TaskLLMs)})
    doc_info = {
        "text": load_text(),
        "title": "Breach of Exclusive Distribution Agreement",
        "description": "Synthetic memo for the talk 'Legal Data That's AI-Ready'.",
    }
    t0 = time.monotonic()
    await gd.init_services("folio")
    t1 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="folio_talk_") as tmp:
        await gd.generate_demo(SLUG, doc_info, Path(tmp), llm, task_llms,
                               ontology="folio", provider_name="codex-cli")
    t2 = time.monotonic()
    print(f"provider=codex-cli model={llm.model} effort=medium")
    print(f"init_seconds={t1 - t0:.1f} pipeline_seconds={t2 - t1:.1f}")
    print(f"output={OUT} exists={OUT.exists()}")


if __name__ == "__main__":
    asyncio.run(main())
