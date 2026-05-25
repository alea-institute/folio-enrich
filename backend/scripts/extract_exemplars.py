"""Extract the 22 exemplar texts from the frontend ``SAMPLES`` object.

The frontend's inline ``const SAMPLES = {...}`` (in ``frontend/index.html``) is the
**single source of truth** for exemplar document text. Both lean-mode prefill (the
browser) and demo generation (this backend) use the same texts. Rather than duplicate
~276 KB of legal text into a second file, the generator extracts the values directly
from ``index.html`` at generation time using Node (the values are ES template literals,
so a real JS engine is the robust way to parse them).

Only the 22 "Rich Enrichment" + "Quick Start" exemplars are pre-baked as demos; the
"Narratives" and "Debug" buttons are intentionally out of scope.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = BACKEND_ROOT.parent / "frontend" / "index.html"

# The 22 exemplar slugs to pre-bake, in UI order (Rich Enrichment, then Quick Start).
# Keys match the inline SAMPLES keys verbatim — demo files are <slug>.json.
EXEMPLAR_SLUGS: list[str] = [
    # Rich Enrichment (7)
    "rich_lit_timekeeping",
    "rich_ma_timekeeping",
    "rich_re_timekeeping",
    "rich_motion",
    "rich_order",
    "rich_contract",
    "rich_advisory",
    # Quick Start (15)
    "motion",
    "complaint",
    "opinion",
    "appellate",
    "injunction",
    "settlement",
    "contract",
    "nda",
    "lease",
    "employment",
    "merger",
    "advice_litigation",
    "advice_regulatory",
    "regulatory",
    "patent",
]

# Title + description per slug, mirroring the exemplar button labels/tooltips in
# index.html. Used for the demo JSON's `demo` metadata block.
EXEMPLAR_META: dict[str, dict[str, str]] = {
    "rich_lit_timekeeping": {"title": "Litigation Timekeeping", "description": "Dense litigation timekeeping narrative — 245+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "rich_ma_timekeeping": {"title": "M&A Timekeeping", "description": "Dense M&A timekeeping narrative — 230+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "rich_re_timekeeping": {"title": "Real Estate Timekeeping", "description": "Dense real estate timekeeping narrative — 210+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "rich_motion": {"title": "Motion to Compel", "description": "Motion to Compel — 181+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "rich_order": {"title": "Order on Summary Judgment", "description": "Order on Summary Judgment — 233+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "rich_contract": {"title": "Services Agreement", "description": "Services Agreement — 301+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "rich_advisory": {"title": "Advisory Memo on Fiduciary Duty", "description": "Advisory Memo on Fiduciary Duty — 392+ FOLIO labels, nested spans", "group": "Rich Enrichment"},
    "motion": {"title": "Motion to Dismiss", "description": "Litigation — motion to dismiss", "group": "Quick Start"},
    "complaint": {"title": "Complaint", "description": "Litigation — class action complaint", "group": "Quick Start"},
    "opinion": {"title": "Court Opinion", "description": "Litigation — court opinion", "group": "Quick Start"},
    "appellate": {"title": "Appellate Brief", "description": "Litigation — appellate brief", "group": "Quick Start"},
    "injunction": {"title": "TRO/Injunction", "description": "Litigation — temporary restraining order / injunction", "group": "Quick Start"},
    "settlement": {"title": "Settlement", "description": "Litigation — settlement agreement", "group": "Quick Start"},
    "contract": {"title": "Contract Clause", "description": "Transactional — force majeure / termination clause", "group": "Quick Start"},
    "nda": {"title": "NDA", "description": "Transactional — mutual non-disclosure agreement", "group": "Quick Start"},
    "lease": {"title": "Commercial Lease", "description": "Transactional — commercial lease agreement", "group": "Quick Start"},
    "employment": {"title": "Employment Agreement", "description": "Transactional — employment agreement", "group": "Quick Start"},
    "merger": {"title": "Merger Agreement", "description": "Transactional — merger agreement", "group": "Quick Start"},
    "advice_litigation": {"title": "Litigation Advice Memo", "description": "Advisory — litigation advice memo", "group": "Quick Start"},
    "advice_regulatory": {"title": "Regulatory Advice Memo", "description": "Advisory — regulatory advice memo", "group": "Quick Start"},
    "regulatory": {"title": "Regulatory Filing", "description": "Regulatory — agency filing", "group": "Quick Start"},
    "patent": {"title": "Patent Application", "description": "Regulatory — patent application", "group": "Quick Start"},
}


def _extract_samples_block(html: str) -> str:
    """Slice the `const SAMPLES = { ... };` object literal out of the HTML.

    SAMPLES values are single-line template literals using ``\\n`` escapes (not real
    newlines), so the first real ``\\n};`` after the declaration reliably terminates
    the object.
    """
    marker = "const SAMPLES = {"
    start = html.find(marker)
    if start == -1:
        raise RuntimeError(f"Could not find '{marker}' in {INDEX_HTML}")
    end = html.find("\n};", start)
    if end == -1:
        raise RuntimeError("Could not find terminating '};' for SAMPLES object")
    return html[start : end + 3]  # include the closing "\n};"


def extract_exemplar_texts() -> dict[str, str]:
    """Return ``{slug: document_text}`` for the 22 exemplars, read from SAMPLES.

    Uses Node to evaluate the SAMPLES object literal (robust against template-literal
    quoting). Raises if Node is unavailable or any expected slug is missing.
    """
    node = shutil.which("node")
    if not node:
        raise RuntimeError(
            "Node.js is required to extract exemplar texts from frontend/index.html "
            "(SAMPLES uses JS template literals). Install Node and retry."
        )

    block = _extract_samples_block(INDEX_HTML.read_text(encoding="utf-8"))
    wanted = json.dumps(EXEMPLAR_SLUGS)
    script = (
        block
        + "\n"
        + f"const __wanted = {wanted};\n"
        + "const __out = {};\n"
        + "for (const k of __wanted) {\n"
        + "  if (!(k in SAMPLES)) { console.error('MISSING_SLUG:' + k); process.exit(2); }\n"
        + "  __out[k] = SAMPLES[k];\n"
        + "}\n"
        + "process.stdout.write(JSON.stringify(__out));\n"
    )

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(script)
        tmp_path = Path(fh.name)
    try:
        proc = subprocess.run(
            [node, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Node extraction failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    texts: dict[str, str] = json.loads(proc.stdout)
    missing = [s for s in EXEMPLAR_SLUGS if not texts.get(s, "").strip()]
    if missing:
        raise RuntimeError(f"Extracted empty/missing exemplar text for: {missing}")
    return texts


if __name__ == "__main__":
    out = extract_exemplar_texts()
    for slug, text in out.items():
        print(f"{slug}: {len(text)} chars")
    print(f"\nOK — extracted {len(out)} exemplar texts from {INDEX_HTML}")
