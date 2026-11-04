"""Extract the Canon exemplar texts from ``frontend/demos/canon_samples.js``.

Mirrors ``extract_exemplars.py`` but for the Catholic Semantic Canon. Unlike the
FOLIO exemplars (whose text lives inline in ``index.html``'s ``SAMPLES`` object),
the Canon demo texts live in a **standalone** JS module,
``frontend/demos/canon_samples.js``, which exports ``CANON_SAMPLES`` via
``module.exports``. That makes extraction simple: a tiny Node driver ``require``s
the module and dumps the wanted slugs as JSON.

Public-domain and synthetic breadth exemplars are pre-baked as Canon demos.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
CANON_SAMPLES_JS = BACKEND_ROOT.parent / "frontend" / "demos" / "canon_samples.js"

# The Canon exemplar slugs, in UI order. Keys match canon_samples.js verbatim;
# demo files are written to frontend/demos/canon/<slug>.json.
CANON_EXEMPLAR_SLUGS: list[str] = [
    "nativity",
    "sacraments",
    "trent_eucharist",
    "rerum_novarum",
    'canon_liturgical_year',
    'canon_diocesan_governance',
    'canon_saints_and_orders',
    'canon_ce_abbot_1907',
]

# Title + description + group per slug, used for the demo JSON's `demo` metadata block.
CANON_META: dict[str, dict[str, str]] = {
    "nativity": {
        "title": "The Nativity & the Magi",
        "description": "Douay-Rheims — Nativity and Adoration of the Magi (persons, places, feasts)",
        "group": "Scripture",
    },
    "sacraments": {
        "title": "The Seven Sacraments",
        "description": "Baltimore Catechism — the seven sacraments and sanctifying grace",
        "group": "Doctrine",
    },
    "trent_eucharist": {
        "title": "Trent: The Eucharist",
        "description": "Council of Trent, Session XIII (1848 tr.) — the Eucharist and Transubstantiation",
        "group": "Councils",
    },
    "rerum_novarum": {
        "title": "Rerum Novarum",
        "description": "Leo XIII, 1891 — the condition of labour, private property, justice",
        "group": "Social Doctrine",
    },
    "canon_liturgical_year": {
        "title": "The Liturgical Year",
        "description": "Synthetic — a parish bulletin on the liturgical year (feasts, sacraments, ministries, places, and teaching)",
        "group": "Breadth",
    },
    "canon_diocesan_governance": {
        "title": "Diocesan Governance",
        "description": "Synthetic — a chancery memo on canon-law governance (appointments, tribunal, marriage nullity, penalties, and property)",
        "group": "Breadth",
    },
    "canon_saints_and_orders": {
        "title": "Saints and Religious Orders",
        "description": "Synthetic — a short history of religious orders and saints (founders, rules, monasteries, councils, and pilgrimage places)",
        "group": "Breadth",
    },
    "canon_ce_abbot_1907": {
        "title": "Abbot (Catholic Encyclopedia, 1907)",
        "description": "Catholic Encyclopedia (1907), \"Abbot\" by Thomas Oestereich: census of abbots nullius and mitred abbeys by country and state.",
        "group": "Breadth",
    },
}


def extract_canon_texts() -> dict[str, str]:
    """Return ``{slug: document_text}`` for the Canon exemplars.

    Evaluates ``canon_samples.js`` via Node (the values are ES template literals, so a
    real JS engine is the robust way to read them). Because the file is a standalone
    module with ``module.exports = CANON_SAMPLES``, the driver just ``require``s it.
    Raises if Node is unavailable or any expected slug is missing/empty.
    """
    node = shutil.which("node")
    if not node:
        raise RuntimeError(
            "Node.js is required to extract Canon exemplar texts from "
            "frontend/demos/canon_samples.js (template literals). Install Node and retry."
        )
    if not CANON_SAMPLES_JS.is_file():
        raise RuntimeError(f"Canon samples module not found: {CANON_SAMPLES_JS}")

    wanted = json.dumps(CANON_EXEMPLAR_SLUGS)
    # JSON.stringify of the abs path yields a safe, quote-escaped JS string literal.
    samples_path = json.dumps(str(CANON_SAMPLES_JS))
    script = (
        f"const CANON_SAMPLES = require({samples_path});\n"
        f"const __wanted = {wanted};\n"
        "const __out = {};\n"
        "for (const k of __wanted) {\n"
        "  if (!(k in CANON_SAMPLES)) { console.error('MISSING_SLUG:' + k); process.exit(2); }\n"
        "  __out[k] = CANON_SAMPLES[k];\n"
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
    missing = [s for s in CANON_EXEMPLAR_SLUGS if not texts.get(s, "").strip()]
    if missing:
        raise RuntimeError(f"Extracted empty/missing Canon exemplar text for: {missing}")
    return texts


if __name__ == "__main__":
    out = extract_canon_texts()
    for slug, text in out.items():
        print(f"{slug}: {len(text)} chars")
    print(f"\nOK — extracted {len(out)} Canon exemplar texts from {CANON_SAMPLES_JS}")
