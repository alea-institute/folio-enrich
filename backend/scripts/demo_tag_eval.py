#!/usr/bin/env python3
"""Score baked demo tags against the gold labels without importing the pipeline.

Unique (casefolded span text, IRI) precision excludes unsure and unlabeled pairs.
A pair seen under several origins counts once overall and once in each origin.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEMOS = ROOT / "frontend" / "demos"
DEFAULT_LABELS = ROOT / "backend" / "eval" / "demo_tags" / "labels.json"
VERDICTS = ("correct", "wrong", "unsure", "unlabeled")
ORIGINS = {"llm_concept": "llm", "entity_ruler": "ruler", "semantic_ruler": "semantic"}


def _metrics(counts: Counter, verdicts: dict) -> dict:
    unique = dict.fromkeys(VERDICTS, 0)
    occurrences = dict.fromkeys(VERDICTS, 0)
    for pair, count in counts.items():
        verdict = verdicts.get(pair, "unlabeled")
        unique[verdict] += 1
        occurrences[verdict] += count
    judged = unique["correct"] + unique["wrong"]
    precision = unique["correct"] / judged if judged else None
    unique["total"] = sum(unique.values())
    occurrences["total"] = sum(occurrences.values())
    return {"unique_pairs": unique, "precision": precision, "occurrences": occurrences}


def score(demos_dir: Path = DEFAULT_DEMOS, labels_path: Path = DEFAULT_LABELS) -> dict:
    """Return unique-pair and occurrence metrics, wrong pairs, and unlabeled pairs."""
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))["labels"]
    verdicts = {(row["text"], row["iri"]): row["verdict"] for row in labels}
    counts = Counter()
    origins = defaultdict(Counter)
    for path in sorted(Path(demos_dir).glob("*.json")):
        if not path.is_file():
            continue
        demo = json.loads(path.read_text(encoding="utf-8"))
        annotations = demo["cache"]["job"]["result"]["annotations"]
        for annotation in annotations:
            if annotation.get("state") == "rejected":
                continue
            lineage = annotation.get("lineage") or []
            stage = lineage[0].get("stage", "unknown") if lineage else "unknown"
            origin = ORIGINS.get(stage, stage)
            for concept in annotation.get("concepts", []):
                if concept.get("state") == "rejected":
                    continue
                pair = (annotation["span"]["text"].casefold(), concept["folio_iri"])
                counts[pair] += 1
                origins[origin][pair] += 1

    def pairs_with_verdict(verdict):
        return [
            {"text": text, "iri": iri, "occurrences": count}
            for (text, iri), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            if verdicts.get((text, iri), "unlabeled") == verdict
        ]

    return {
        "overall": _metrics(counts, verdicts),
        "per_origin": {origin: _metrics(origins[origin], verdicts) for origin in sorted(origins)},
        "top_wrong_pairs": pairs_with_verdict("wrong")[:30],
        "unlabeled_pairs": pairs_with_verdict("unlabeled"),
    }


def print_summary(summary: dict) -> None:
    for name, metrics in [("Overall", summary["overall"]), *summary["per_origin"].items()]:
        precision = metrics["precision"]
        print(f"{name}: precision={precision:.4f}" if precision is not None
              else f"{name}: precision=n/a (no correct/wrong pairs)")
        for label, key in (("unique pairs", "unique_pairs"), ("occurrences", "occurrences")):
            print(f"  {label}: " + ", ".join(f"{k}={v}" for k, v in metrics[key].items()))
    for heading, key in (("Top 30 wrong pairs by occurrence", "top_wrong_pairs"),
                         ("Every unlabeled pair", "unlabeled_pairs")):
        print(f"\n{heading} ({len(summary[key])}):")
        for row in summary[key]:
            print(f"  {row['occurrences']:>5}  {row['text']!r}  {row['iri']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["score"], default="score")
    parser.add_argument("--demos-dir", type=Path, default=DEFAULT_DEMOS)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--json", type=Path, dest="json_path", help="Write the summary as JSON")
    args = parser.parse_args(argv)
    summary = score(args.demos_dir, args.labels)
    print_summary(summary)
    if args.json_path:
        args.json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
