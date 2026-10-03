"""Offline proposition scoring against exhaustive gold annotations.

Run from backend/: .venv/bin/python -m eval.proposition_benchmark [--write]
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from uuid import NAMESPACE_URL, UUID, uuid5


_HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = _HERE / "gold/propositions/manifest.json"
REPORT_DIR = _HERE / "reports/propositions"


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    proposition_type: str
    pattern: str = "reporting-verb"

    def __post_init__(self):
        if not 0 <= self.start < self.end:
            raise ValueError(f"invalid span [{self.start}, {self.end})")


def candidate_span(candidate) -> Span:
    """Use named patterns when available, otherwise identify Phase A frames."""
    frame = getattr(candidate, "frame", None)
    pattern = getattr(candidate, "pattern_name", None) or getattr(frame, "pattern_name", None)
    if pattern is None:
        pattern = "arguendo" if candidate.proposition_type == "arguendo assumption" else "reporting-verb"
    return Span(candidate.start_char, candidate.end_char, candidate.proposition_type, pattern)


def dice(left: Span, right: Span) -> float:
    overlap = max(0, min(left.end, right.end) - max(left.start, right.start))
    return 2 * overlap / (left.end - left.start + right.end - right.start)


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """95% Wilson score interval; no observations gives the full interval."""
    if not total:
        return 0.0, 1.0
    z = NormalDist().inv_cdf(0.975)
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def indicative_overfit(development_recall: float, held_out_recall: float) -> bool:
    gap = development_recall - held_out_recall
    return gap > 0.15 and not math.isclose(gap, 0.15, abs_tol=1e-12)


def _metrics(counts: dict) -> dict:
    gold, candidates, matched = counts["gold"], counts["candidates"], counts["matched"]
    recall = matched / gold if gold else 0.0
    precision = matched / candidates if candidates else 0.0
    return {
        **counts,
        "recall": recall,
        "recall_ci": wilson_interval(matched, gold),
        "precision": precision,
        "precision_ci": wilson_interval(matched, candidates),
        "f1": 2 * recall * precision / (recall + precision) if recall + precision else 0.0,
    }


def score_split(gold: list[Span], candidates: list[Span], audits: Sequence[Span] = ()) -> dict:
    """Greedy one-to-one Dice matching, with deleted candidates vetoed first."""
    blocked = {i for i, c in enumerate(candidates) if any(dice(c, a) >= 0.5 for a in audits)}
    pairs = []
    for ci, candidate in enumerate(candidates):
        if ci in blocked:
            continue
        for gi, target in enumerate(gold):
            overlap = dice(candidate, target)
            if overlap >= 0.5:
                pairs.append((-overlap, ci, gi))
    pairs.sort()
    used_candidates, used_gold = set(), set()
    matches = []
    for _, ci, gi in pairs:
        if ci not in used_candidates and gi not in used_gold:
            used_candidates.add(ci)
            used_gold.add(gi)
            matches.append((ci, gi))

    per_type = {}
    for kind in sorted({g.proposition_type for g in gold}):
        support = sum(g.proposition_type == kind for g in gold)
        hits = sum(gold[gi].proposition_type == kind for _, gi in matches)
        per_type[kind] = {"gold": support, "matched": hits, "recall": hits / support}
    per_pattern = {}
    for pattern in sorted({c.pattern for c in candidates}):
        per_pattern[pattern] = {
            "candidates": sum(c.pattern == pattern for c in candidates),
            "matched": sum(candidates[ci].pattern == pattern for ci, _ in matches),
            "exact": sum(
                candidates[ci].pattern == pattern
                and (candidates[ci].start, candidates[ci].end) == (gold[gi].start, gold[gi].end)
                for ci, gi in matches
            ),
        }
    agreed = sum(candidates[ci].proposition_type == gold[gi].proposition_type for ci, gi in matches)
    return _metrics({
        "gold": len(gold), "candidates": len(candidates), "matched": len(matches),
        "exact": sum((candidates[ci].start, candidates[ci].end) == (gold[gi].start, gold[gi].end) for ci, gi in matches),
        "audit_false_positives": len(blocked),
        "per_type": per_type, "per_pattern": per_pattern,
        "type_agreement": {"matched": len(matches), "agreed": agreed, "rate": agreed / len(matches) if matches else 0.0},
    })


def combine_scores(scores: list[dict]) -> dict:
    """Pool counts across opinions without matching spans across documents."""
    counts = {key: sum(s[key] for s in scores) for key in (
        "gold", "candidates", "matched", "exact", "audit_false_positives",
    )}
    per_type, per_pattern = {}, {}
    for score in scores:
        for kind, values in score["per_type"].items():
            pooled = per_type.setdefault(kind, {"gold": 0, "matched": 0})
            for key in ("gold", "matched"):
                pooled[key] += values[key]
        for pattern, values in score["per_pattern"].items():
            pooled = per_pattern.setdefault(pattern, {"candidates": 0, "matched": 0, "exact": 0})
            for key in pooled:
                pooled[key] += values[key]
    for values in per_type.values():
        values["recall"] = values["matched"] / values["gold"]
    agreed = sum(s["type_agreement"]["agreed"] for s in scores)
    return _metrics({
        **counts, "per_type": dict(sorted(per_type.items())),
        "per_pattern": dict(sorted(per_pattern.items())),
        "type_agreement": {"matched": counts["matched"], "agreed": agreed, "rate": agreed / counts["matched"] if counts["matched"] else 0.0},
    })


def load_records(path: Path, text: str, ranges: Sequence[tuple[int, int]] | None = None) -> tuple[list[Span], list[Span]]:
    gold, audits = [], []
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        kind = row.get("record_type")
        if kind not in {"annotation", "candidate-audit"}:
            continue
        p = row.get("proposition") or row["original"]
        if ranges is not None:
            # Gold belongs to its start split; audits can veto candidates in
            # either split they overlap. Filter before validating row contents.
            if kind == "annotation":
                selected = any(start <= p["start_char"] < end for start, end in ranges)
            else:
                selected = any(p["start_char"] < end and p["end_char"] > start
                               for start, end in ranges)
            if not selected:
                continue
        span = Span(p["start_char"], p["end_char"], p["proposition_type"])
        if kind == "annotation" and text[span.start:span.end] != p["text"]:
            raise ValueError(f"{path.name}: {row.get('annotation_id', p.get('id'))} [{span.start}, {span.end}) does not reproduce gold text")
        if span.end > len(text):
            raise ValueError(f"{path.name}: span ends beyond canonical text")
        (gold if kind == "annotation" else audits).append(span)
    return gold, audits


def split_ranges(entry: dict, text_length: int) -> dict[str, tuple[int, int]]:
    ranges = {name: tuple(bounds) for name, bounds in entry.get("splits", {"held-out": [0, text_length]}).items()}
    ordered = sorted(ranges.values())
    if (
        not ordered or ordered[0][0] != 0 or ordered[-1][1] != text_length
        or any(not 0 <= start < end <= text_length for start, end in ordered)
        or any(left[1] != right[0] for left, right in zip(ordered, ordered[1:]))
    ):
        raise ValueError("split ranges must cover canonical text without gaps or overlap")
    return ranges


def run_benchmark(manifest_path: Path = DEFAULT_MANIFEST, *, split: str | None = None) -> dict:
    from app.models.document import CanonicalText
    from app.models.job import Job, JobResult
    from app.services.proposition.extractor import PropositionExtractor
    from app.services.proposition.lexicon import LEXICON_VERSION

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = []
    by_split = defaultdict(list)
    for entry in manifest["opinions"]:
        if entry.get("benchmark") is False:
            continue
        slug = entry["slug"]
        if split is not None and split not in entry.get("splits", {}):
            continue
        # Parse the identical canonical document for both full and split-only
        # runs: truncation changes sentence segmentation at the split boundary.
        text = (manifest_path.parent / entry["text_file"]).read_bytes().decode("utf-8")
        ranges = split_ranges(entry, len(text))
        if split is not None:
            ranges = {split: ranges[split]}
        gold, audits = load_records(manifest_path.parent / f"{slug}.jsonl", text,
                                   list(ranges.values()) if split else None)
        job = Job(
            id=UUID(entry["job_id"]) if entry.get("job_id") else uuid5(NAMESPACE_URL, slug),
            result=JobResult(canonical_text=CanonicalText(full_text=text)),
        )
        candidates = [candidate_span(p) for p in PropositionExtractor().extract(job)]
        split_scores = {}
        for name, (start, end) in ranges.items():
            split_gold = [g for g in gold if start <= g.start < end]
            if any(g.end > end for g in split_gold):
                raise ValueError(f"{slug}: gold span crosses {name} split boundary")
            # Candidates crossing a split boundary belong to their start split.
            split_candidates = [c for c in candidates if start <= c.start < end]
            split_audits = [a for a in audits if a.start < end and a.end > start]
            score = score_split(split_gold, split_candidates, split_audits)
            split_scores[name] = score
            by_split[name].append(score)
        documents.append({"slug": slug, "text_file": entry["text_file"], "ranges": ranges, "splits": split_scores})
    splits = {name: combine_scores(scores) for name, scores in by_split.items()}
    dev, held_out = splits.get("development"), splits.get("held-out")
    return {
        "lexicon_version": LEXICON_VERSION,
        "matching": {"method": "greedy Dice", "threshold": 0.5, "candidate_audit_veto": True},
        "confidence_level": 0.95,
        "candidate_split_assignment": "start_char",
        "documents": documents, "splits": splits,
        "overall": combine_scores(list(splits.values())),
        "overfit": {
            "indicative": True, "recall_gap_threshold": 0.15,
            "flag": indicative_overfit(dev["recall"], held_out["recall"]) if dev and held_out else None,
        },
    }


def print_report(report: dict) -> None:
    print(f"Lexicon: {report['lexicon_version']}")
    print("Split        Gold Candidates Matched Exact Recall [95% CI]       Precision [95% CI]    F1")
    for name, score in report["splits"].items():
        def interval(metric):
            low, high = score[f"{metric}_ci"]
            return f"{score[metric]:.3f} [{low:.3f}, {high:.3f}]"

        print(f"{name:<12} {score['gold']:>4} {score['candidates']:>10} {score['matched']:>7} {score['exact']:>5} {interval('recall'):<21} {interval('precision'):<21} {score['f1']:.3f}")
        print("  Pattern                      Candidates Hits Exact")
        for pattern, values in score["per_pattern"].items():
            print(f"  {pattern:<28} {values['candidates']:>10} {values['matched']:>4} {values['exact']:>5}")
    if report["overfit"]["flag"]:
        print("Indicative overfit flag: held-out recall is more than 0.15 below development recall.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write eval/reports/propositions/<lexicon_version>.json")
    parser.add_argument("--split", choices=["development"], help="extract full canonical text, then score and report only development")
    args = parser.parse_args()
    if args.split and args.write:
        parser.error("--write requires the complete benchmark; split-only runs are for iteration")
    report = run_benchmark(split=args.split)
    print_report(report)
    if args.write:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORT_DIR / f"{report['lexicon_version']}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {path.relative_to(_HERE.parent)}")


if __name__ == "__main__":
    main()
