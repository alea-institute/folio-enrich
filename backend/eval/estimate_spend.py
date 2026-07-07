"""Full-mode LLM spend estimate for the NER eval — token-grounded, queued not run.

The *authoritative* flip signal ("does NER cross-validation improve F1 without
regressing recall on the PRODUCTION annotation set?") needs the LLM candidate stages
(LLMConcept, DocumentType, LLMIndividual, LLMProperty, Metadata, BranchJudge, and the
post-completion Area-of-Law / doc-type quality checks). Those cost paid API calls, so
per TODAY-2026-07-07 policy we estimate and QUEUE rather than run.

Efficiency note baked into the estimate: the NER flag only modulates *reconciliation*
(a deterministic, post-LLM pass), so the LLM stages produce identical output for
flag OFF and ON. The authoritative run therefore needs **one** LLM pass per doc, then a
free deterministic reconciliation replay OFF vs ON — i.e. cost is 1× full pipeline per
doc, NOT 2×.

Token math is transparent and reproducible (chars→tokens heuristic, explicit per-stage
multipliers). The **price per 1M tokens is the one real assumption** and is surfaced in
the queued question for Damien to confirm; an empirical anchor from Lane-5 folio-mapper
(~$0.50 for ~72 judged items over 4 demos with the same model) is included as a
cross-check.

Usage
-----
    cd backend
    .venv/bin/python -m eval.estimate_spend                 # print estimate
    .venv/bin/python -m eval.estimate_spend --queue         # + append QA question
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .demo_source import load_demo_content
from .gold_schema import load_gold

_HERE = Path(__file__).resolve().parent
DEFAULT_GOLD = _HERE / "gold" / "folio_ner_gold.jsonl"
_QA_QUEUE = _HERE.parent.parent.parent / "briefs" / "qa" / "pending-questions.jsonl"

MODEL = "google/gemini-3-flash-preview"
CHARS_PER_TOKEN = 4.0

# Per-doc LLM stages in the full pipeline and how many times each sends ~the full
# document text as input (transparent, tunable). Output tokens estimated flat/stage.
STAGE_INPUT_MULTIPLIER = {
    "document_type": 1.0,
    "llm_concept": 1.0,
    "llm_individual": 1.0,
    "llm_property": 1.0,
    "metadata_extract": 1.0,
    "branch_judge": 0.5,          # proportional to #concepts, modeled as 0.5x text
    "area_of_law": 0.5,           # post-completion
    "doc_type_quality": 0.5,      # post-completion
}
OUTPUT_TOKENS_PER_STAGE = 900
PROMPT_OVERHEAD_TOKENS = 1200     # scaffolding per stage call

# Explicit price assumption (USD per 1M tokens). Flagged for confirmation.
PRICE_LOW = {"input": 0.10, "output": 0.40}    # optimistic flash-class
PRICE_HIGH = {"input": 0.30, "output": 2.50}   # conservative flash-class


def _gold_counts(gold_path: Path) -> tuple[list[str], int, int]:
    """Return (ordered doc_ids, scored_count, needs_review_count) from the gold."""
    doc_ids: list[str] = []
    scored = 0
    review = 0
    for e in load_gold(gold_path):
        if e.doc_id not in doc_ids:
            doc_ids.append(e.doc_id)
        if e.is_scored:
            scored += 1
        if e.verification == "needs_review":
            review += 1
    return doc_ids, scored, review


def estimate(gold_path: Path) -> dict:
    doc_ids, scored, review = _gold_counts(gold_path)
    n_stages = len(STAGE_INPUT_MULTIPLIER)
    total_in = 0.0
    total_out = 0.0
    per_doc = []
    for doc_id in doc_ids:
        chars = len(load_demo_content(doc_id))
        doc_tokens = chars / CHARS_PER_TOKEN
        in_tokens = sum(
            doc_tokens * m + PROMPT_OVERHEAD_TOKENS
            for m in STAGE_INPUT_MULTIPLIER.values()
        )
        out_tokens = OUTPUT_TOKENS_PER_STAGE * n_stages
        total_in += in_tokens
        total_out += out_tokens
        per_doc.append({"doc_id": doc_id, "chars": chars,
                        "input_tokens": round(in_tokens), "output_tokens": round(out_tokens)})

    def cost(price):
        return total_in / 1e6 * price["input"] + total_out / 1e6 * price["output"]

    lo, hi = cost(PRICE_LOW), cost(PRICE_HIGH)
    return {
        "model": MODEL,
        "docs": doc_ids,
        "n_docs": len(doc_ids),
        "gold_scored": scored,
        "gold_needs_review": review,
        "llm_stages_per_doc": n_stages,
        "passes": "1x per doc (NER flag does not change LLM calls) + free reconciliation replay OFF/ON",
        "total_input_tokens": round(total_in),
        "total_output_tokens": round(total_out),
        "price_assumption_per_1m": {"low": PRICE_LOW, "high": PRICE_HIGH},
        "estimated_cost_usd": {"low": round(lo, 3), "high": round(hi, 3)},
        "empirical_anchor": "Lane-5 folio-mapper: ~$0.50 for ~72 judged items over 4 demos "
                            "(same model, judge-only workload; enrich full-pipeline is heavier).",
        "per_doc": per_doc,
    }


def build_qa_question(est: dict) -> dict:
    lo = est["estimated_cost_usd"]["low"]
    hi = est["estimated_cost_usd"]["high"]
    ctx = (
        f"<p>The free deterministic NER eval ({est['gold_scored']} oracle-verified spans across "
        f"{est['n_docs']} demo docs) shows NER cross-validation is <b>recall-safe</b> on "
        f"unambiguous matches but yields <b>no measured F1 gain</b> there — it does not "
        f"exercise the ambiguous / LLM-sourced concepts where NER's affinity signal would "
        f"actually discriminate. The authoritative flip signal needs a <b>full-pipeline</b> "
        f"run (LLM candidate stages ON) over the gold docs, flag OFF vs ON.</p>"
        f"<p><b>Estimate:</b> {est['model']}, {est['n_docs']} docs, "
        f"{est['llm_stages_per_doc']} LLM stages/doc, "
        f"~{est['total_input_tokens']:,} input + {est['total_output_tokens']:,} output tokens. "
        f"The NER flag doesn't change LLM calls, so this is <b>1 LLM pass per doc</b> plus a "
        f"free reconciliation replay OFF/ON. Estimated cost <b>${lo:.2f}–${hi:.2f}</b> "
        f"(range = flash-class price assumption of "
        f"${PRICE_LOW['input']}–${PRICE_HIGH['input']}/1M in, "
        f"${PRICE_LOW['output']}–${PRICE_HIGH['output']}/1M out — the one figure to confirm). "
        f"Empirical anchor: {est['empirical_anchor']}</p>"
        f"<p>Default stays <code>ner_cross_validation_enabled=False</code> (recall-safe) "
        f"until this runs. A prod flip would still ride the ask-gated deploy.</p>"
    )
    return {
        "from": "lane-5/folio-enrich-ner-eval-harness",
        "topic": f"Approve spend-gated full-pipeline NER eval run (~${lo:.2f}–${hi:.2f})?",
        "context_html": ctx,
        "type": "both",
        "allow_notes": True,
        "options": [
            {"label": f"Approve the full-mode run (~${lo:.2f}–${hi:.2f}, {est['n_docs']} docs)",
             "detail": "Runs 1 LLM pass/doc then replays reconciliation OFF/ON; produces the "
                       "authoritative F1/recall delta that decides the flag flip.",
             "recommended": True},
            {"label": "Expand the gold set / human-verify borderline cases first, then run",
             "detail": f"{est['gold_needs_review']} borderline entries await human verification; "
                       "promoting them sharpens the eval before spending."},
            {"label": "Hold — keep default False, no run now",
             "detail": "Recall-safe status quo; revisit when NER discrimination is needed."},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Estimate full-mode NER eval LLM spend")
    ap.add_argument("--gold", default=str(DEFAULT_GOLD))
    ap.add_argument("--queue", action="store_true",
                    help="append the QA question to briefs/qa/pending-questions.jsonl")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    est = estimate(Path(args.gold))
    if args.json:
        print(json.dumps(est, indent=2))
    else:
        c = est["estimated_cost_usd"]
        print(f"Full-mode NER eval spend estimate ({est['model']})")
        print(f"  docs: {est['n_docs']}  stages/doc: {est['llm_stages_per_doc']}")
        print(f"  tokens: {est['total_input_tokens']:,} in + {est['total_output_tokens']:,} out")
        print(f"  estimated cost: ${c['low']:.2f} – ${c['high']:.2f} USD")
        print(f"  passes: {est['passes']}")

    if args.queue:
        q = build_qa_question(est)
        _QA_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        with _QA_QUEUE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"queued spend question -> {_QA_QUEUE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
