"""WS-3 (3d): verify FOLIO and Canon OWL disk caches cannot collide.

owl_cache.py is FOLIO-specific by design (GitHub source, ``github/`` subdir). Canon
(and any http source) loads through FolioService's hardened ingestion into the
separate ``http/`` subdir, keyed on the OWL URL. Different directory AND different
hash input => the filenames cannot collide, so a FOLIO update/rollback can never
touch a Canon file (no phantom rollback). This test pins that invariant.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.folio.owl_cache import _CACHE_FILE
from app.services.ontology.spec import CANON_SPEC


def _canon_cache_file() -> Path:
    # Mirror FolioService._load_http_via_hardened_ingestion's cache scheme exactly.
    cache_hash = hashlib.blake2b(CANON_SPEC.coords.owl_url.encode()).hexdigest()
    return Path.home() / ".folio" / "cache" / "http" / f"{cache_hash}.owl"


def test_folio_and_canon_cache_dirs_are_disjoint():
    folio_dir = _CACHE_FILE.parent
    canon_dir = _canon_cache_file().parent
    assert folio_dir.name == "github"
    assert canon_dir.name == "http"
    assert folio_dir != canon_dir


def test_folio_and_canon_cache_files_do_not_collide():
    folio_file = _CACHE_FILE
    canon_file = _canon_cache_file()
    assert folio_file != canon_file
    # Even the bare filenames differ (different hash inputs), so no cross-dir alias.
    assert folio_file.name != canon_file.name
