#!/usr/bin/env python3
"""Import an exported validation bundle and verify canonical gold text."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "backend/eval/gold/propositions"


def _atomic_write(path: Path, content: str) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def import_bundle(bundle: dict[str, Any], gold_dir: Path, session_id: str) -> dict[str, Any]:
    entry = deepcopy(bundle["manifest_entry"])
    if bundle["session_id"] != session_id or entry["session_id"] != session_id:
        raise ValueError("bundle session id does not match")
    original_slug = entry.get("validation_of", "")
    slug = entry["slug"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", original_slug) or slug != f"{original_slug}-validated":
        raise ValueError("invalid validation slug")
    manifest_path = gold_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = next((item for item in manifest["opinions"] if item["slug"] == original_slug), None)
    if original is None:
        raise ValueError("validated record is absent from the local manifest")
    entry["text_file"] = original["text_file"]
    entry["splits"] = deepcopy(original.get("splits", {}))
    text = (gold_dir / entry["text_file"]).read_bytes().decode("utf-8")
    for line in bundle["jsonl"].splitlines():
        row = json.loads(line)
        if row.get("record_type") != "annotation" or row.get("deleted"):
            continue
        proposition = row["proposition"]
        start, end = proposition["start_char"], proposition["end_char"]
        if not 0 <= start < end <= len(text) or text[start:end] != proposition["text"]:
            raise ValueError(f"gold text span mismatch: {row['annotation_id']} [{start}, {end})")
    manifest["opinions"] = [item for item in manifest["opinions"] if item["slug"] != slug] + [entry]
    _atomic_write(gold_dir / f"{slug}.jsonl", bundle["jsonl"])
    _atomic_write(gold_dir / f"{slug}.ann", bundle["ann"])
    _atomic_write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Bundle JSON file, bundle URL, or host URL")
    parser.add_argument("session_id", help="Exported annotation session id")
    parser.add_argument("--gold-dir", type=Path, default=GOLD_DIR)
    args = parser.parse_args()
    if args.source.startswith(("http://", "https://")):
        url = args.source.rstrip("/")
        if not url.endswith("/bundle"):
            url += f"/gold/sessions/{quote(args.session_id, safe='')}/bundle"
        with urlopen(url, timeout=30) as response:
            bundle = json.load(response)
    else:
        bundle = json.loads(Path(args.source).read_text(encoding="utf-8"))
    entry = import_bundle(bundle, args.gold_dir, args.session_id)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_proposition_gold_text.py", "-q"],
        cwd=ROOT / "backend", check=False,
    )
    if result.returncode == 0:
        print(f"Imported {entry['slug']}; canonical spans verified.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
