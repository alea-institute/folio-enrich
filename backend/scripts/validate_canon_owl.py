"""Phase 0 feasibility + security spike for the Catholic Semantic Canon ontology.

Throwaway validation script (see docs/plans/2026-07-01-002-feat-multi-ontology-catholic-canon-plan.md).
Validates that folio-python can load the Canon OWL, measures the rdfs:label silent-drop
gate, auto-derives top-level branch roots, and checks OWL-cache path parity.

Run:  cd backend && .venv/bin/python scripts/validate_canon_owl.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import httpx
from lxml import etree

CANON_URL = "https://raw.githubusercontent.com/CatholicOS/ontology-semantic-canon/main/sources/ontology-semantic-canon.owl"
MAX_BYTES = 48 * 1024 * 1024  # generous cap for the spike (~14MB expected)

OWL = "{http://www.w3.org/2002/07/owl#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
OWL_THING = "http://www.w3.org/2002/07/owl#Thing"


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def guarded_download(url: str) -> bytes:
    """HTTPS-only, size-capped, streamed download; returns raw bytes."""
    if not url.lower().startswith("https://"):
        raise ValueError("refusing non-HTTPS URL")
    total = 0
    chunks: list[bytes] = []
    h = hashlib.sha256()
    with httpx.Client(follow_redirects=False, timeout=30.0) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_bytes(64 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError(f"stream exceeded {MAX_BYTES} bytes")
                h.update(chunk)
                chunks.append(chunk)
    data = b"".join(chunks)
    print(f"downloaded  : {total:,} bytes ({total / 1024 / 1024:.1f} MB)")
    print(f"sha256      : {h.hexdigest()}")
    return data


def security_gate(data: bytes) -> etree._Element:
    """DOCTYPE reject + hardened lxml parse (P0 security controls)."""
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!doctype" in data.lower():
        raise ValueError("SECURITY: OWL contains a DOCTYPE declaration -> rejected")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        remove_comments=True,
    )
    root = etree.fromstring(data, parser=parser)
    print("DOCTYPE     : none (ok)")
    print("parser      : hardened (resolve_entities=False, no_network=True, huge_tree=False)")
    return root


def raw_class_stats(root: etree._Element) -> tuple[int, int, int]:
    """Count named owl:Class, how many lack rdfs:label, and named object properties."""
    named_classes = 0
    missing_label = 0
    for cls in root.iter(f"{OWL}Class"):
        about = cls.get(f"{RDF}about")
        if not about:
            continue  # anonymous restriction / blank node
        named_classes += 1
        if cls.find(f"{RDFS}label") is None:
            missing_label += 1
    obj_props = sum(
        1 for p in root.iter(f"{OWL}ObjectProperty") if p.get(f"{RDF}about")
    )
    return named_classes, missing_label, obj_props


def main() -> int:
    section("1. GUARDED DOWNLOAD + SECURITY GATE")
    data = guarded_download(CANON_URL)
    root = security_gate(data)

    section("2. RAW OWL STATS (before folio-python)")
    named, missing, obj_props = raw_class_stats(root)
    print(f"named owl:Class      : {named:,}")
    print(f"  missing rdfs:label : {missing:,}  <-- silently DROPPED by folio-python is_valid()")
    print(f"named ObjectProperty : {obj_props:,}")
    label_retention = (named - missing) / named * 100 if named else 0
    print(f"label retention      : {label_retention:.2f}%")

    section("3. LOAD VIA folio-python (FOLIO source_type=http)")
    from folio import FOLIO

    folio = FOLIO(source_type="http", http_url=CANON_URL, use_cache=True)
    n_classes = len(folio.classes)
    n_props = len(folio.object_properties)
    print(f"folio.classes          : {n_classes:,}")
    print(f"folio.object_properties: {n_props:,}")
    dropped = named - n_classes
    print(f"delta vs raw named     : {dropped:,} dropped "
          f"({'MATCH raw-missing' if dropped == missing else 'DIFFERS from raw-missing'})")

    section("4. AUTO-DERIVE TOP-LEVEL BRANCH ROOTS")
    # A root = a class whose sub_class_of is empty or only owl:Thing.
    roots = []
    for cls in folio.classes:
        parents = [p for p in (getattr(cls, "sub_class_of", None) or []) if p != OWL_THING]
        if not parents:
            roots.append(cls)
    print(f"derived top-level roots: {len(roots)}")
    print("(FOLIO has ~24 hand-curated branches; Canon count drives palette overflow design)")
    for r in roots[:25]:
        label = getattr(r, "label", None) or "(no label)"
        print(f"  - {label}  <{getattr(r, 'iri', '?')}>")
    if len(roots) > 25:
        print(f"  ... and {len(roots) - 25} more")

    section("5. SAMPLE IRI ROUND-TRIP (folio[iri] / get_parents)")
    sample = next((c for c in folio.classes if getattr(c, "sub_class_of", None)), folio.classes[0])
    iri = sample.iri
    got = folio[iri]
    parents = folio.get_parents(iri)
    print(f"iri          : {iri}")
    print(f"folio[iri]   : {'ok' if got is not None else 'FAILED'} "
          f"(label={getattr(got, 'label', None)})")
    print(f"get_parents  : {len(parents)} parent(s) -> "
          f"{[getattr(p, 'label', '?') for p in parents[:5]]}")

    section("6. OWL-CACHE PATH PARITY (github-scheme vs http-scheme)")
    cache_root = Path.home() / ".folio" / "cache"
    on_disk = sorted(cache_root.rglob("*.owl")) if cache_root.exists() else []
    print(f"cache root   : {cache_root}")
    for p in on_disk:
        print(f"  actual file: {p}  ({p.stat().st_size:,} bytes)")
    print("app owl_cache.py currently writes the GITHUB scheme "
          "(~/.folio/cache/github/{blake2b(owner/name/branch)}.owl);")
    print("folio-python HTTP load reads the HTTP scheme (shown above). "
          "=> updater and loader must be pointed at the SAME path (plan Phase 0/2).")

    section("VERDICT")
    ok = (
        label_retention >= 99.0
        and n_classes > 5000
        and n_props > 100
        and got is not None
        and 2 <= len(roots) <= 200
    )
    print(f"label retention >= 99%        : {label_retention >= 99.0}  ({label_retention:.2f}%)")
    print(f"classes loaded > 5000         : {n_classes > 5000}  ({n_classes:,})")
    print(f"object properties > 100       : {n_props > 100}  ({n_props:,})")
    print(f"iri round-trip ok             : {got is not None}")
    print(f"root count sane (2..200)      : {2 <= len(roots) <= 200}  ({len(roots)})")
    print(f"\nPHASE 0 GATE: {'PASS -> reuse folio-python, no rdflib fallback needed' if ok else 'FAIL -> see above; may need rdflib loader'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
