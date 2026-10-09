"""Locate a usable Playwright package for the JS-executing browser tests.

Order: ``FOLIO_ENRICH_PLAYWRIGHT_MODULE``, then whatever Node resolves from
the repo, then every ``~/.npm/_npx/*/node_modules/playwright`` (newest
first). A candidate is used only if its Chromium actually launches, so a
stale npx cache whose browser build was never downloaded is skipped instead
of failing the test.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_PROBE = (
    "const {chromium}=require(process.argv[1]);"
    "chromium.launch().then(b=>b.close()).then(()=>process.exit(0),()=>process.exit(1));"
)


def _candidates(node: str) -> list[Path]:
    found: list[Path] = []
    explicit = os.environ.get("FOLIO_ENRICH_PLAYWRIGHT_MODULE")
    if explicit:
        found.append(Path(explicit))
    try:
        probe = subprocess.run(
            [node, "-e", "process.stdout.write(require.resolve('playwright/package.json'))"],
            cwd=REPO, capture_output=True, text=True, timeout=10,
        )
        if probe.returncode == 0 and probe.stdout:
            found.append(Path(probe.stdout).parent)
    except (OSError, subprocess.SubprocessError):
        pass
    npx = sorted(
        Path.home().glob(".npm/_npx/*/node_modules/playwright/package.json"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    found.extend(p.parent for p in npx)
    unique: list[Path] = []
    for path in found:
        if path not in unique and (path / "package.json").is_file():
            unique.append(path)
    return unique


def _launches(node: str, module: Path) -> bool:
    try:
        run = subprocess.run([node, "-e", _PROBE, str(module)], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return run.returncode == 0


@lru_cache(maxsize=None)
def playwright_module(node: str) -> str | None:
    """Path of the first Playwright package whose Chromium launches, or None."""
    for candidate in _candidates(node):
        if _launches(node, candidate):
            return str(candidate)
    return None
