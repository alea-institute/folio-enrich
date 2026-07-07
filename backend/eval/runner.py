"""NER cross-validation eval runner — flag OFF vs ON, precision/recall/F1.

Deterministic mode (default, **free**, CI-invokable): runs ``PipelineOrchestrator``
with ``llm=None`` — the fully rule-based ruler→NER→reconcile→resolve→string-match
pipeline — once per document with ``ner_cross_validation_enabled`` False, then True,
and scores each run's confirmed annotations against the curated gold set. It reports
the delta and a flip recommendation.

Because ``llm=None`` skips every paid stage and spaCy/FOLIO are deterministic, the
whole run is reproducible and costs $0. It measures the NER flag's effect on the
*deterministic* annotation subset — a free, lower-fidelity proxy for the production
flip decision. The authoritative full-pipeline comparison (LLM-sourced concepts
included) is spend-gated: see ``estimate_spend.py`` and the QA queue.

Usage
-----
    cd backend
    .venv/bin/python -m eval.runner                       # deterministic, default gold
    .venv/bin/python -m eval.runner --out report.json     # write JSON report
    .venv/bin/python -m eval.runner --gold path/to.jsonl  # custom gold
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from .demo_source import load_demo_content
from .gold_schema import GoldEntry, load_gold
from .metrics import PRF, EntryOutcome, PredSpan, score_set

_HERE = Path(__file__).resolve().parent
DEFAULT_GOLD = _HERE / "gold" / "folio_ner_gold.jsonl"


# ── pipeline invocation ──────────────────────────────────────────────────── #
async def annotate(text: str, ner_flag: bool) -> tuple[list[PredSpan], str]:
    """Run the deterministic pipeline; return (confirmed PredSpans, canonical_text).

    LLM is None → every paid stage self-skips. Toggling the module-level setting is
    how production and every existing test flip the flag.

    Concurrency note (M3): this mutates the process-global
    ``settings.ner_cross_validation_enabled`` and restores it in ``finally``. That is
    correct only because ``run_eval`` awaits docs strictly sequentially. Do NOT
    parallelize the eval loop or run it while another pipeline call is in flight — two
    coroutines would interleave OFF/ON and corrupt the global flag.
    """
    from app.config import settings
    from app.models.job import DocumentInput, Job
    from app.pipeline.orchestrator import PipelineOrchestrator
    from app.storage.job_store import JobStore

    prev = settings.ner_cross_validation_enabled
    settings.ner_cross_validation_enabled = ner_flag
    try:
        job = Job(input=DocumentInput(content=text, format="plain_text", filename="eval.txt"))
        out = await PipelineOrchestrator(JobStore()).run(job)
    finally:
        settings.ner_cross_validation_enabled = prev

    canonical = ""
    if out.result and out.result.canonical_text:
        canonical = out.result.canonical_text.full_text or ""

    preds: list[PredSpan] = []
    for ann in (out.result.annotations if out.result else []):
        if ann.state != "confirmed" or not ann.concepts:
            continue
        iri = ann.concepts[0].folio_iri or ""
        preds.append(PredSpan(start=ann.span.start, end=ann.span.end, iri=iri))
    return preds, canonical


# ── evaluation ───────────────────────────────────────────────────────────── #
async def run_eval(gold: list[GoldEntry]) -> dict:
    by_doc: dict[str, list[GoldEntry]] = defaultdict(list)
    for e in gold:
        by_doc[e.doc_id].append(e)

    doc_sources = {e.doc_id: e.doc_source for e in gold}
    scored_total = sum(1 for e in gold if e.is_scored)

    results: dict[str, dict] = {}
    global_prf = {False: PRF(), True: PRF()}
    outcomes: dict[bool, list[EntryOutcome]] = {False: [], True: []}
    canon_hash: dict[str, str] = {}

    for doc_id in sorted(by_doc):
        text = load_demo_content(doc_sources[doc_id])
        doc_gold = by_doc[doc_id]
        results[doc_id] = {}
        for flag in (False, True):
            preds, canonical = await annotate(text, flag)
            if flag is False:
                canon_hash[doc_id] = hashlib.sha256(canonical.encode()).hexdigest()[:12]
            prf, oc = score_set(doc_gold, preds)
            for k in ("tp", "fp", "fn", "tn"):
                setattr(global_prf[flag], k, getattr(global_prf[flag], k) + getattr(prf, k))
            outcomes[flag].extend(oc)
            results[doc_id][f"ner_{'on' if flag else 'off'}"] = prf.as_dict()

    off, on = global_prf[False], global_prf[True]
    recall_regression = on.recall < off.recall - 1e-9
    f1_improved = on.f1 > off.f1 + 1e-9
    if not scored_total:
        recommendation = "INSUFFICIENT_GOLD"
    elif f1_improved and not recall_regression:
        recommendation = "FLIP_SUPPORTED"
    elif recall_regression:
        recommendation = "HOLD_recall_regression"
    else:
        recommendation = "HOLD_no_f1_gain"

    # entries whose outcome CHANGED between OFF and ON (the interesting cases)
    off_by_id = {o.gold_id: o for o in outcomes[False]}
    changed = [
        {"gold_id": o.gold_id, "off": off_by_id[o.gold_id].outcome, "on": o.outcome}
        for o in outcomes[True]
        if o.gold_id in off_by_id and off_by_id[o.gold_id].outcome != o.outcome
    ]

    return {
        "mode": "deterministic",
        "fidelity": "proxy (deterministic subset; LLM-sourced concepts excluded)",
        "gold_entries_total": len(gold),
        "gold_entries_scored": scored_total,
        "docs": sorted(by_doc),
        "canonical_hash": canon_hash,
        "ner_off": off.as_dict(),
        "ner_on": on.as_dict(),
        "delta": {
            "precision": round(on.precision - off.precision, 4),
            "recall": round(on.recall - off.recall, 4),
            "f1": round(on.f1 - off.f1, 4),
        },
        "recall_regression": recall_regression,
        "f1_improved": f1_improved,
        "recommendation": recommendation,
        "changed_outcomes": changed,
        "per_doc": results,
    }


def _print_report(rep: dict) -> None:
    off, on, d = rep["ner_off"], rep["ner_on"], rep["delta"]
    print("=" * 68)
    print("NER cross-validation eval — deterministic (free) mode")
    print(f"  gold: {rep['gold_entries_scored']} scored / {rep['gold_entries_total']} total"
          f"  across {len(rep['docs'])} docs")
    print(f"  fidelity: {rep['fidelity']}")
    print("-" * 68)
    print(f"  {'':10}{'P':>8}{'R':>8}{'F1':>8}{'TP':>6}{'FP':>6}{'FN':>6}")
    print(f"  {'NER off':10}{off['precision']:>8.3f}{off['recall']:>8.3f}{off['f1']:>8.3f}"
          f"{off['tp']:>6}{off['fp']:>6}{off['fn']:>6}")
    print(f"  {'NER on':10}{on['precision']:>8.3f}{on['recall']:>8.3f}{on['f1']:>8.3f}"
          f"{on['tp']:>6}{on['fp']:>6}{on['fn']:>6}")
    print(f"  {'delta':10}{d['precision']:>+8.3f}{d['recall']:>+8.3f}{d['f1']:>+8.3f}")
    print("-" * 68)
    print(f"  recommendation: {rep['recommendation']}")
    if rep["changed_outcomes"]:
        print(f"  outcome changes (OFF→ON): {len(rep['changed_outcomes'])}")
        for c in rep["changed_outcomes"][:10]:
            print(f"    {c['gold_id']}: {c['off']} -> {c['on']}")
    print("=" * 68)


def main() -> int:
    ap = argparse.ArgumentParser(description="NER cross-validation gold-set eval")
    ap.add_argument("--gold", default=str(DEFAULT_GOLD), help="path to gold JSONL")
    ap.add_argument("--mode", default="deterministic",
                    choices=["deterministic", "full"], help="eval mode")
    ap.add_argument("--out", default="", help="write JSON report to this path")
    ap.add_argument("--json", action="store_true", help="print JSON report to stdout")
    args = ap.parse_args()

    if args.mode == "full":
        print("full mode is spend-gated (LLM candidate stages cost paid API calls).\n"
              "Run:  .venv/bin/python -m eval.estimate_spend --gold <gold>\n"
              "to compute the cost estimate; it is queued to the QA portal, not run here.")
        return 2

    gold = load_gold(args.gold)
    if not gold:
        print(f"no gold entries found at {args.gold}")
        return 1

    rep = asyncio.run(run_eval(gold))
    if args.out:
        Path(args.out).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        _print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
