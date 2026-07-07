"""Shared loader for demo-document source text (used by curate/runner/estimate).

Gold offsets are defined in the pipeline's *canonical* text space; the deterministic
pipeline reproduces canonical text run-to-run, so feeding the raw ``input.content``
here yields the same canonical_text the curator saw. Centralised so every reader
reports the same doc-named error on a malformed/missing demo.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent          # backend/eval -> repo root
DEMOS_DIR = _REPO_ROOT / "frontend" / "demos"


def demo_path(doc_id_or_source: str) -> Path:
    """Accept a bare doc id ('contract') or a repo-relative demo path."""
    s = doc_id_or_source
    if s.endswith(".json") or "/" in s:
        return (_REPO_ROOT / s).resolve()
    return (DEMOS_DIR / f"{s}.json").resolve()


def load_demo_content(doc_id_or_source: str) -> str:
    """Return ``cache.job.input.content`` for a demo, with a doc-named error."""
    path = demo_path(doc_id_or_source)
    if not path.exists():
        raise FileNotFoundError(f"demo not found for {doc_id_or_source!r}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    content = (((payload.get("cache") or {}).get("job") or {}).get("input") or {}).get("content")
    if content is None:
        raise ValueError(f"{doc_id_or_source}: no cache.job.input.content in {path.name}")
    return content
