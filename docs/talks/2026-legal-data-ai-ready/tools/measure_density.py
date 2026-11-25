"""Measure FOLIO Enrich tag density for a demo-format JSON.

coverage = share of [A-Za-z]{3,} words in cache.normalizedText that overlap any
character covered by a cache.job.result.annotations span (span.start/span.end).
Also lists the longest runs of untagged words (3+ consecutive) for revision.

Usage: python measure_density.py <demo.json> [--top N]
"""
from __future__ import annotations

import json
import re
import sys


def measure(path: str, top: int = 15) -> dict:
    data = json.load(open(path, encoding="utf-8"))
    cache = data["cache"]
    text = cache["normalizedText"]
    result = cache["job"]["result"]
    anns = result.get("annotations", [])
    covered = bytearray(len(text))
    for a in anns:
        s, e = a["span"]["start"], a["span"]["end"]
        for i in range(max(0, s), min(len(text), e)):
            covered[i] = 1
    words = [(m.start(), m.end(), any(covered[m.start():m.end()]))
             for m in re.finditer(r"[A-Za-z]{3,}", text)]
    n_cov = sum(1 for w in words if w[2])
    runs, cur = [], []
    for w in words:
        if w[2]:
            if len(cur) >= 3:
                runs.append(cur)
            cur = []
        else:
            cur.append(w)
    if len(cur) >= 3:
        runs.append(cur)
    runs.sort(key=len, reverse=True)
    stretches = [(len(r), " ".join(text[r[0][0]:r[-1][1]].split())) for r in runs[:top]]
    iris = set()
    for a in anns:
        for c in a.get("concepts", []) or []:
            if c.get("folio_iri"):
                iris.add(c["folio_iri"])
    return {
        "coverage": n_cov / len(words) if words else 0.0,
        "words": len(words), "covered_words": n_cov,
        "annotations": len(anns), "distinct_concept_iris": len(iris),
        "individuals": len(result.get("individuals", []) or []),
        "properties": len(result.get("properties", []) or []),
        "triples": len(result.get("triples", []) or []),
        "stretches": stretches,
    }


if __name__ == "__main__":
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 15
    r = measure(sys.argv[1], top)
    print(f"coverage={r['coverage']:.4f} ({r['covered_words']}/{r['words']} words)")
    for k in ("annotations", "distinct_concept_iris", "individuals", "properties", "triples"):
        print(f"{k}={r[k]}")
    print(f"top {len(r['stretches'])} untagged stretches (3+ words):")
    for n, s in r["stretches"]:
        print(f"  [{n}] {s}")
