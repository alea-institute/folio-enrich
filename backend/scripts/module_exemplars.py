"""Extract exemplar text from a standalone JavaScript samples module."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_module_texts(samples_js, slugs, binding, title, kind, node_error):
    node = shutil.which("node")
    if not node:
        raise RuntimeError(node_error)
    if not samples_js.is_file():
        raise RuntimeError(f"{title} samples module not found: {samples_js}")

    wanted = json.dumps(slugs)
    samples_path = json.dumps(str(samples_js))
    script = (
        f"const {binding} = require({samples_path});\n"
        f"const __wanted = {wanted};\n"
        "const __out = {};\n"
        "for (const k of __wanted) {\n"
        f"  if (!(k in {binding})) {{ console.error('MISSING_SLUG:' + k); process.exit(2); }}\n"
        f"  __out[k] = {binding}[k];\n"
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
    missing = [s for s in slugs if not texts.get(s, "").strip()]
    if missing:
        raise RuntimeError(f"Extracted empty/missing {kind} exemplar text for: {missing}")
    return texts

