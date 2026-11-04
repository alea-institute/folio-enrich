"""List new Canon-only concepts awaiting a model bridge pass after a pin bump.

Run from backend: .venv/bin/python scripts/bridge_queue.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Support direct script execution as well as module imports.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ontology.bridges import load_bridges
from app.services.ontology.overlap import get_overlap_index


def main() -> int:
    index = get_overlap_index()
    evaluated = set(load_bridges()["evaluated_canon_only"])
    queued = [record for key, record in sorted(index.entries.items())
              if record.region == "canon_only" and key not in evaluated]
    for record in queued:
        print(f"{record.iri_hash}\t{record.canon_label or ''}")
    print(f"{len(queued)} Canon-only concepts queued")
    return 0


if __name__ == "__main__":
    sys.exit(main())
