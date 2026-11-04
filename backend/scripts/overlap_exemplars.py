"""Extract public-domain overlap texts from ``frontend/demos/overlap_samples.js``.

Mirrors the Canon standalone-module pattern: Node evaluates the template literals
and returns the expected slugs as JSON. Bakes use the ``both`` namespace.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OVERLAP_SAMPLES_JS = BACKEND_ROOT.parent / "frontend" / "demos" / "overlap_samples.js"

# The overlap exemplar slugs, in UI order. Keys match overlap_samples.js verbatim;
# demo files are written to frontend/demos/both/<slug>.json.
OVERLAP_EXEMPLAR_SLUGS: list[str] = ['lm_encyclopedia_theft',
 'lm_aquinas_robbery',
 'lm_aquinas_just_price',
 'lm_exodus_restitution',
 'lm_catechism_seventh_eighth']

OVERLAP_META: dict[str, dict[str, str]] = {
    "lm_encyclopedia_theft": {
        "title": "THEFT: OWNERSHIP, NECESSITY, AND RESTITUTION",
        "description": "Catholic Encyclopedia, \"Theft\" (Delany, 1912) — theft, property, restitution, natural law, justice",
        "group": "Encyclopedia",
    },
    "lm_aquinas_robbery": {
        "title": "WHETHER ROBBERY MAY BE COMMITTED WITHOUT SIN",
        "description": "Aquinas, Summa II-II q.66 a.8 (1920 tr.) — robbery, theft, public authority, just war, restitution",
        "group": "Aquinas",
    },
    "lm_aquinas_just_price": {
        "title": "WHETHER IT IS LAWFUL TO SELL A THING FOR MORE THAN ITS WORTH",
        "description": "Aquinas, Summa II-II q.77 a.1 (1920 tr.) — fraud, deceit, contracts of sale, just price, restitution",
        "group": "Aquinas",
    },
    "lm_exodus_restitution": {
        "title": "THE COMMANDMENTS AND THE LAW OF RESTITUTION",
        "description": "Douay-Rheims, Exodus 20:13-17 and 22:1-11, 25-26 — kill, steal, false witness, restitution, deposit, oath, judges, usury",
        "group": "Scripture",
    },
    "lm_catechism_seventh_eighth": {
        "title": "THE SEVENTH AND EIGHTH COMMANDMENTS: THEFT, RESTITUTION, AND FALSE WITNESS",
        "description": "Baltimore Catechism No. 3 (Kinkead, 1921 rev.), Lesson 34 — stealing, fraud, stolen goods, restitution, damage, perjury, slander",
        "group": "Catechism",
    },
}


def extract_overlap_texts() -> dict[str, str]:
    """Return ``{slug: document_text}`` for the overlap exemplars.

    Evaluates ``overlap_samples.js`` via Node (the values are ES template literals, so a
    real JS engine is the robust way to read them). Because the file is a standalone
    module with ``module.exports = OVERLAP_SAMPLES``, the driver just ``require``s it.
    Raises if Node is unavailable or any expected slug is missing/empty.
    """
    node = shutil.which("node")
    if not node:
        raise RuntimeError(
            "Node.js is required to extract overlap exemplar texts from "
            "frontend/demos/overlap_samples.js (template literals). Install Node and retry."
        )
    if not OVERLAP_SAMPLES_JS.is_file():
        raise RuntimeError(f"Overlap samples module not found: {OVERLAP_SAMPLES_JS}")

    wanted = json.dumps(OVERLAP_EXEMPLAR_SLUGS)
    # JSON.stringify of the abs path yields a safe, quote-escaped JS string literal.
    samples_path = json.dumps(str(OVERLAP_SAMPLES_JS))
    script = (
        f"const OVERLAP_SAMPLES = require({samples_path});\n"
        f"const __wanted = {wanted};\n"
        "const __out = {};\n"
        "for (const k of __wanted) {\n"
        "  if (!(k in OVERLAP_SAMPLES)) { console.error('MISSING_SLUG:' + k); process.exit(2); }\n"
        "  __out[k] = OVERLAP_SAMPLES[k];\n"
        "}\n"
        "process.stdout.write(JSON.stringify(__out));\n"
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
    missing = [s for s in OVERLAP_EXEMPLAR_SLUGS if not texts.get(s, "").strip()]
    if missing:
        raise RuntimeError(f"Extracted empty/missing overlap exemplar text for: {missing}")
    return texts


if __name__ == "__main__":
    out = extract_overlap_texts()
    for slug, text in out.items():
        print(f"{slug}: {len(text)} chars")
    print(f"\nOK — extracted {len(out)} overlap exemplar texts from {OVERLAP_SAMPLES_JS}")
