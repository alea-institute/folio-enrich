#!/usr/bin/env python3
"""Classified-delta comparator for the folio-enrich -> folio-resolve migration.

Given two harness captures (baseline before the swap, candidate after), bucket every
label-resolution / entity-ruler / reconciler delta as intended-fix / regression / neutral,
and run the migration canaries. Mirrors the folio-insights v5/v6/v7 three-column discipline.

Canaries (the migration's acceptance gate):
  * place/agency mis-maps  -> must trend to 0 post-migration (generic terms must stop
    latching onto place/governmental-body labels).
  * named recoveries       -> must NOT drop (the concepts Damien named must still resolve).
  * candidate recall       -> [Stage 2] the ranked candidate set per term must NOT shrink. This
    is the canary that catches "retire search.py by deleting it": on the committed Stage-2
    baseline the library primary is right on 24/24 rows, but the ranked set collapses 120 -> 15
    without the fork's recall gathering.
  * fork parity            -> [Stage 2] the ``search_fork`` seam's top-1 per term must not move
    when the swap is meant to be a pure internals change (pass --expect-changes to allow it).

Usage:
    .venv/bin/python migration/compare.py --baseline baseline --candidate candidate
Writes migration/DELTA-REPORT.md and migration/captures/delta.json. Exit code is non-zero
when a canary fails (named recovery dropped, or a NEW place mis-map introduced).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Minimal stdlib content-word tokenizer (mirrors folio_resolve.scoring stopwords loosely) so the
# comparator can auto-judge recovery better/worse without importing the library.
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "and", "or", "in", "for", "to", "with", "by", "on", "at",
    "is", "are", "law", "legal", "type", "types", "general",
})


def _content_words(text: str) -> set[str]:
    return {w for w in (t.lower() for t in re.findall(r"[a-zA-Z]+", text or "") if len(t) >= 2)
            if w not in _STOPWORDS}

MIGRATION = Path(__file__).resolve().parent
CAPTURES_DIR = MIGRATION / "captures"

# Branches the place/agency gate governs (mirror of folio_resolve.gates._PLACE_BRANCH_MARKERS,
# hardcoded so the comparator runs standalone before/after the library is installed).
_PLACE_BRANCH_MARKERS = (
    "location", "geograph", "country", "jurisdiction", "place", "governmental", "agency",
)
# Categories whose primary resolution should be a place/agency mis-map candidate.
_GENERIC_CATEGORIES = {"place_agency_generic", "homonym_trap"}
_RECOVERY_CATEGORIES = {"exact", "fuzzy", "word_order"}


def _load(name: str) -> dict:
    return json.loads((CAPTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _is_place(branch: str | None) -> bool:
    b = (branch or "").lower()
    return any(marker in b for marker in _PLACE_BRANCH_MARKERS)


def _primary(item: dict) -> dict | None:
    return item.get("primary")


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def classify_label_resolution(base: dict, cand: dict) -> tuple[list[dict], dict]:
    b_by = _by_id(base["label_resolution"])
    c_by = _by_id(cand["label_resolution"])
    deltas: list[dict] = []
    canary = {
        "place_mismaps_baseline": 0,
        "place_mismaps_candidate": 0,
        "new_place_mismaps": [],       # regressions: place introduced where none was
        "named_recoveries_dropped": [],  # regressions: recovery -> NONE
    }

    for iid, b in b_by.items():
        c = c_by.get(iid)
        if c is None:
            continue
        bp, cp = _primary(b), _primary(c)
        b_iri = bp["iri"] if bp else None
        c_iri = cp["iri"] if cp else None
        b_place = bool(bp) and _is_place(bp.get("branch"))
        c_place = bool(cp) and _is_place(cp.get("branch"))
        cat = b["category"]

        if cat in _GENERIC_CATEGORIES:
            if b_place:
                canary["place_mismaps_baseline"] += 1
            if c_place:
                canary["place_mismaps_candidate"] += 1
            if c_place and not b_place:
                canary["new_place_mismaps"].append(iid)
        if cat in _RECOVERY_CATEGORIES and bp and not cp:
            canary["named_recoveries_dropped"].append(iid)

        # ---- bucket the delta ----
        if b_iri == c_iri:
            bucket, why = "neutral", "same resolution"
            if bp and cp and bp.get("confidence_0_1") != cp.get("confidence_0_1"):
                why = f"same IRI, score {bp['confidence_0_1']} -> {cp['confidence_0_1']}"
        elif cat in _GENERIC_CATEGORIES or cat == "proposed_class":
            if cp is None:
                bucket, why = "intended_fix", "generic/nonsense term demoted to no-match"
            elif b_place and not c_place:
                bucket, why = "intended_fix", "place/agency mis-map replaced by non-place concept"
            elif not b_place and c_place:
                bucket, why = "regression", "introduced a place/agency mis-map"
            else:
                bucket, why = "neutral", "resolution changed (both non-place)"
        elif cat in _RECOVERY_CATEGORIES:
            if bp and not cp:
                bucket, why = "regression", "named/expected recovery dropped to no-match"
            elif not bp and cp:
                bucket, why = "intended_fix", "recovery newly resolved"
            else:
                # Auto-judge better/worse by how many of the query's content words the resolved
                # label shares (a recovery should resolve to a label containing the query term).
                q = _content_words(b["text"])
                b_share = len(q & _content_words(bp["label"])) if bp else 0
                c_share = len(q & _content_words(cp["label"])) if cp else 0
                b_empty_branch = bool(bp) and not (bp.get("branch") or "")
                c_empty_branch = bool(cp) and not (cp.get("branch") or "")
                if c_share > b_share:
                    bucket, why = "intended_fix", (
                        f"recovery resolves to a label sharing more query words ({b_share}->{c_share})")
                elif c_share < b_share or (c_empty_branch and not b_empty_branch):
                    detail = f"query-word overlap dropped ({b_share}->{c_share})"
                    if c_empty_branch and not b_empty_branch:
                        detail += "; candidate has empty branch"
                    bucket, why = "regression", "recovery degraded: " + detail
                else:
                    bucket, why = "neutral", "recovery IRI changed, equal query-word overlap"
        elif cat == "compound_multihead":
            b_cand = {x["iri"] for x in b.get("candidates", [])}
            c_cand = {x["iri"] for x in c.get("candidates", [])}
            gained = c_cand - b_cand
            bucket = "intended_fix" if gained else "neutral"
            why = f"compound decomposition candidates gained={len(gained)}" if gained else \
                "compound resolution changed"
        else:
            bucket, why = "neutral", "resolution changed"

        if bucket != "neutral" or b_iri != c_iri:
            deltas.append(
                {
                    "id": iid,
                    "text": b["text"],
                    "category": cat,
                    "bucket": bucket,
                    "why": why,
                    "baseline": _fmt(bp),
                    "candidate": _fmt(cp),
                }
            )
    return deltas, canary


def _fmt(p: dict | None) -> str:
    if not p:
        return "NONE"
    return f"{p['label']!r} [{p.get('branch') or '-'}] conf={p.get('confidence_0_1')}"


def classify_set(base_rows: list[dict], cand_rows: list[dict], key: str, render) -> list[dict]:
    """Generic added/removed diff for entity_ruler matches / reconciler results."""
    b_by = _by_id(base_rows)
    c_by = _by_id(cand_rows)
    deltas: list[dict] = []
    for iid, b in b_by.items():
        c = c_by.get(iid, {})
        b_set = {render(x) for x in b.get(key, [])}
        c_set = {render(x) for x in c.get(key, [])}
        added = sorted(c_set - b_set)
        removed = sorted(b_set - c_set)
        if added or removed:
            deltas.append({"id": iid, "added": added, "removed": removed})
    return deltas


def classify_candidate_recall(base: dict, cand: dict) -> dict:
    """Stage-2 canary: the ranked candidate set per term must not shrink.

    ``label_resolution[].candidates`` is what ConceptResolver.resolve_multi returns — the ranked
    set the UI, the reconciler, and every multi-candidate consumer read. A retirement of the
    recall path shows up here first.
    """
    b = {r["id"]: len(r.get("candidates", [])) for r in base.get("label_resolution", [])}
    c = {r["id"]: len(r.get("candidates", [])) for r in cand.get("label_resolution", [])}
    shrunk = [
        {"id": i, "baseline": b[i], "candidate": c.get(i, 0)}
        for i in b
        if c.get(i, 0) < b[i]
    ]
    return {
        "baseline_total": sum(b.values()),
        "candidate_total": sum(c.values()),
        "terms_shrunk": shrunk,
        "library_only_total": sum(
            len(r.get("candidates", [])) for r in cand.get("library_only", [])
        ),
    }


def classify_fork_parity(base: dict, cand: dict) -> dict:
    """Stage-2 canary: the fork's own top-1 per term (seam 4). Empty unless internals moved."""
    def _top1(capture: dict) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in capture.get("search_fork", []):
            results = row.get("results") or []
            out[row["id"]] = results[0]["iri"] if results else ""
        return out

    b, c = _top1(base), _top1(cand)
    moved = [
        {"id": i, "baseline": b[i], "candidate": c.get(i, "")}
        for i in b
        if c.get(i, "") != b[i]
    ]
    return {"terms_compared": len(b), "top1_moved": moved}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="baseline")
    ap.add_argument("--candidate", default="candidate")
    ap.add_argument(
        "--expect-changes",
        action="store_true",
        help="allow the Stage-2 fork-parity canary to move (a DOCUMENTED deliberate change)",
    )
    args = ap.parse_args()

    base = _load(args.baseline)
    cand = _load(args.candidate)

    hash_match = base["corpus_hash"] == cand["corpus_hash"]

    lr_deltas, canary = classify_label_resolution(base, cand)
    er_deltas = classify_set(
        base["entity_ruler"], cand["entity_ruler"], "matches",
        lambda m: f"{m['text']}@{m['start']}:{m['end']}->{m['iri_hash']}({m['match_type']})",
    )
    rc_deltas = classify_set(
        base["reconciler"], cand["reconciler"], "results",
        lambda r: f"{r['concept_text']}->{r.get('iri','')}/{r['category']}/{r['confidence']}",
    )

    counts = {"intended_fix": 0, "regression": 0, "neutral": 0}
    for d in lr_deltas:
        counts[d["bucket"]] += 1

    recall = classify_candidate_recall(base, cand)
    parity = classify_fork_parity(base, cand)

    canary_pass = (
        not canary["named_recoveries_dropped"]
        and not canary["new_place_mismaps"]
        and canary["place_mismaps_candidate"] <= canary["place_mismaps_baseline"]
        and not recall["terms_shrunk"]
        and (args.expect_changes or not parity["top1_moved"])
    )

    delta = {
        "corpus_hash_match": hash_match,
        "baseline_hash": base["corpus_hash"],
        "candidate_hash": cand["corpus_hash"],
        "environment": {"baseline": base["environment"], "candidate": cand["environment"]},
        "label_resolution_counts": counts,
        "canary": canary,
        "candidate_recall": recall,
        "fork_parity": parity,
        "expect_changes": args.expect_changes,
        "canary_pass": canary_pass,
        "label_resolution_deltas": lr_deltas,
        "entity_ruler_deltas": er_deltas,
        "reconciler_deltas": rc_deltas,
    }
    (CAPTURES_DIR / "delta.json").write_text(json.dumps(delta, indent=2) + "\n", encoding="utf-8")

    _write_markdown(delta)

    print(f"corpus hash match: {hash_match}")
    print(f"label-resolution buckets: {counts}")
    print(f"canary place mis-maps: {canary['place_mismaps_baseline']} -> "
          f"{canary['place_mismaps_candidate']}")
    print(f"canary named recoveries dropped: {canary['named_recoveries_dropped']}")
    print(f"canary new place mis-maps: {canary['new_place_mismaps']}")
    print(f"canary candidate recall: {recall['baseline_total']} -> {recall['candidate_total']} "
          f"(terms shrunk: {len(recall['terms_shrunk'])})")
    print(f"canary fork parity: {len(parity['top1_moved'])} of {parity['terms_compared']} "
          f"top-1 moved{' (allowed)' if args.expect_changes else ''}")
    print(f"CANARY PASS: {canary_pass}")
    print(f"entity_ruler deltas: {len(er_deltas)} docs changed")
    print(f"reconciler deltas: {len(rc_deltas)} cases changed")
    return 0 if canary_pass else 1


def _write_markdown(delta: dict) -> None:
    lines: list[str] = []
    lines.append("# folio-enrich -> folio-resolve: Classified Delta Report\n")
    lines.append(f"- Corpus hash match (baseline vs candidate): **{delta['corpus_hash_match']}**")
    env = delta["environment"]
    lines.append(f"- folio_resolve present: baseline={env['baseline']['folio_resolve_present']}, "
                 f"candidate={env['candidate']['folio_resolve_present']}")
    lines.append(f"- FOLIO concepts: {env['candidate'].get('folio_concept_count')}\n")

    c = delta["label_resolution_counts"]
    lines.append("## Headline (label resolution)\n")
    lines.append(f"- Intended fixes: **{c['intended_fix']}**")
    lines.append(f"- Regressions: **{c['regression']}**")
    lines.append(f"- Neutral changes: **{c['neutral']}**\n")

    can = delta["canary"]
    lines.append("## Canaries\n")
    lines.append(f"- Place/agency mis-maps (generic terms): **{can['place_mismaps_baseline']} -> "
                 f"{can['place_mismaps_candidate']}** (target: -> 0)")
    lines.append(f"- New place mis-maps introduced (must be empty): `{can['new_place_mismaps']}`")
    lines.append(f"- Named recoveries dropped (must be empty): `{can['named_recoveries_dropped']}`")
    rec = delta.get("candidate_recall")
    if rec:
        lines.append(f"- Ranked candidate recall: **{rec['baseline_total']} -> "
                     f"{rec['candidate_total']}** (terms shrunk, must be empty: "
                     f"`{[t['id'] for t in rec['terms_shrunk']]}`); library-only reference: "
                     f"{rec['library_only_total']}")
    par = delta.get("fork_parity")
    if par:
        lines.append(f"- Fork top-1 moved (must be empty unless --expect-changes): "
                     f"`{[t['id'] for t in par['top1_moved']]}`")
    lines.append(f"- **CANARY PASS: {delta['canary_pass']}**\n")

    lines.append("## Label-resolution deltas (before -> after)\n")
    lines.append("| id | category | bucket | why | baseline | candidate |")
    lines.append("|----|----------|--------|-----|----------|-----------|")
    for d in sorted(delta["label_resolution_deltas"], key=lambda x: (x["bucket"], x["id"])):
        lines.append(
            f"| {d['id']} | {d['category']} | **{d['bucket']}** | {d['why']} | "
            f"{d['baseline']} | {d['candidate']} |"
        )
    lines.append("")

    lines.append("## Entity-ruler deltas\n")
    if not delta["entity_ruler_deltas"]:
        lines.append("_No changes._\n")
    for d in delta["entity_ruler_deltas"]:
        lines.append(f"- **{d['id']}**: added={d['added']} removed={d['removed']}")
    lines.append("")

    lines.append("## Reconciler deltas\n")
    if not delta["reconciler_deltas"]:
        lines.append("_No changes._\n")
    for d in delta["reconciler_deltas"]:
        lines.append(f"- **{d['id']}**: added={d['added']} removed={d['removed']}")
    lines.append("")

    (MIGRATION / "DELTA-REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
