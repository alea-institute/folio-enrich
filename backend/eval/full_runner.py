"""Full-pipeline NER cross-validation eval — flag OFF vs ON, with LLM stages ON.

This is the *authoritative* flip signal that ``runner.py``'s deterministic mode only
proxies: it runs the whole pipeline including every paid LLM candidate stage
(document_type, llm_concept, branch_judge, llm_individual, llm_property, metadata,
area_of_law, doc_type_quality), then scores the confirmed annotations against the gold
set with ``ner_cross_validation_enabled`` OFF and ON.

Cost discipline — one LLM pass per doc
--------------------------------------
The NER flag only modulates the *deterministic* reconciliation stage (post-LLM), so the
LLM candidate stages emit identical output for OFF and ON. To pay for that exactly once,
every LLM call is routed through :class:`CachingLLM`, a transparent memoizing wrapper:

    * flag OFF runs first and populates the cache with real API calls (the one paid pass);
    * flag ON re-runs the same doc — identical prompts hit the cache (zero new tokens),
      so only the free deterministic reconciliation actually differs.

Real token usage is captured from Gemini's ``usageMetadata`` by wrapping the provider's
HTTP path, so the report carries *actual* (not estimated) token counts and proves the ON
replay added ~0 LLM calls. Any downstream prompt that genuinely differs OFF→ON (because
reconciliation changed which concepts survive) is a legitimate cache miss and is counted
honestly — it never silently inflates or hides cost.

Usage
-----
    cd backend
    FOLIO_ENRICH_GOOGLE_API_KEY=$GOOGLE_API_KEY \\
        .venv/bin/python -m eval.runner --mode full --out reports/full_mode_baseline.json
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .demo_source import load_demo_content
from .gold_schema import GoldEntry
from .metrics import PRF, EntryOutcome, PredSpan, score_set

# Flash-class price assumptions (USD per 1M tokens), shared with estimate_spend so the
# actual-token cost is bracketed the same way the pre-run estimate was.
PRICE_LOW = {"input": 0.10, "output": 0.40}
PRICE_HIGH = {"input": 0.30, "output": 2.50}

# Hard safety brake: abort before starting a doc if projected spend would approach the cap.
SPEND_ABORT_USD = 0.75


@dataclass
class LLMUsage:
    """Running tally of real (cache-miss) LLM traffic and cache efficiency."""

    calls: int = 0            # real provider invocations (cache misses)
    cache_hits: int = 0       # served from cache (zero new tokens)
    input_tokens: int = 0     # actual promptTokenCount summed across real calls
    output_tokens: int = 0    # actual candidatesTokenCount summed across real calls

    def snapshot(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    def cost_usd(self, price: dict[str, float]) -> float:
        return (
            self.input_tokens / 1e6 * price["input"]
            + self.output_tokens / 1e6 * price["output"]
        )


class CachingLLM:
    """Memoizing, usage-instrumented wrapper around an ``LLMProvider``.

    Implements the ``complete``/``chat``/``structured`` surface the pipeline stages use.
    Identical calls (same method + arguments) are served from an in-memory cache, so the
    OFF pass pays for each unique prompt once and the ON pass reuses it for free. Real
    calls capture Gemini ``usageMetadata`` for exact token accounting.
    """

    def __init__(self, inner: Any, usage: LLMUsage) -> None:
        self._inner = inner
        self._usage = usage
        self._cache: dict[str, Any] = {}
        self._wrap_usage_capture()

    # --- token capture --------------------------------------------------------
    def _wrap_usage_capture(self) -> None:
        """Wrap the provider's HTTP path so every real call records actual tokens.

        Only cache-miss calls reach the inner provider, so this counts exactly the paid
        traffic. Falls back silently if the provider lacks ``_post_with_retry`` (e.g. a
        non-Google provider) — token counts stay zero but call/hit counts still hold.
        """
        inner = self._inner
        orig = getattr(inner, "_post_with_retry", None)
        if orig is None:
            return
        usage = self._usage

        async def _instrumented(url: str, body: dict, *a: Any, **kw: Any) -> dict:
            data = await orig(url, body, *a, **kw)
            meta = (data or {}).get("usageMetadata") or {}
            usage.input_tokens += int(meta.get("promptTokenCount", 0) or 0)
            usage.output_tokens += int(meta.get("candidatesTokenCount", 0) or 0)
            return data

        inner._post_with_retry = _instrumented  # type: ignore[attr-defined]

    # --- cache key ------------------------------------------------------------
    @staticmethod
    def _key(method: str, *args: Any, **kwargs: Any) -> str:
        payload = json.dumps(
            {"m": method, "a": args, "k": kwargs},
            sort_keys=True, default=str, ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _memoized(self, method: str, coro_factory, *args: Any, **kwargs: Any) -> Any:
        key = self._key(method, *args, **kwargs)
        if key in self._cache:
            self._usage.cache_hits += 1
            return self._cache[key]
        self._usage.calls += 1
        result = await coro_factory()
        self._cache[key] = result
        return result

    # --- LLMProvider surface --------------------------------------------------
    async def complete(self, prompt: str, **kwargs: Any) -> str:
        return await self._memoized(
            "complete", lambda: self._inner.complete(prompt, **kwargs), prompt, **kwargs
        )

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return await self._memoized(
            "chat", lambda: self._inner.chat(messages, **kwargs), messages, **kwargs
        )

    async def structured(self, prompt: str, schema: dict, **kwargs: Any) -> dict:
        return await self._memoized(
            "structured", lambda: self._inner.structured(prompt, schema, **kwargs),
            prompt, schema, **kwargs,
        )

    async def test_connection(self) -> bool:
        return await self._inner.test_connection()

    async def list_models(self):
        return await self._inner.list_models()

    def __getattr__(self, name: str) -> Any:
        # Delegate any other attribute (e.g. .model) to the wrapped provider.
        return getattr(self._inner, name)


def build_llm() -> tuple[CachingLLM, LLMUsage, str]:
    """Build the default-provider LLM wrapped for caching + usage capture.

    Returns (caching_llm, usage_tally, model_id). Raises RuntimeError if no provider
    could be constructed (e.g. missing/unauthenticated API key).
    """
    from app.config import settings
    from app.pipeline.orchestrator import _make_llm

    inner = _make_llm(settings.llm_provider, settings.llm_model)
    if inner is None:
        raise RuntimeError(
            f"No LLM provider for {settings.llm_provider!r} — is the API key set? "
            f"(config env_prefix is FOLIO_ENRICH_, so export FOLIO_ENRICH_GOOGLE_API_KEY)"
        )
    usage = LLMUsage()
    model_id = getattr(inner, "model", None) or settings.llm_model or "(provider-default)"
    return CachingLLM(inner, usage), usage, model_id


async def annotate_full(text: str, ner_flag: bool, llm: CachingLLM) -> list[PredSpan]:
    """Run the full LLM-enabled pipeline once; return confirmed PredSpans.

    Mirrors ``runner.annotate`` but passes a real LLM provider (so the paid candidate
    stages run) and toggles ``ner_cross_validation_enabled`` for the reconciliation pass.
    The single ``llm`` instance is shared across OFF/ON so ON hits its cache.
    """
    from app.config import settings
    from app.models.job import DocumentInput, Job
    from app.pipeline.orchestrator import PipelineOrchestrator
    from app.storage.job_store import JobStore

    prev = settings.ner_cross_validation_enabled
    settings.ner_cross_validation_enabled = ner_flag
    try:
        job = Job(input=DocumentInput(content=text, format="plain_text", filename="eval.txt"))
        # Single shared llm for all tasks (task_llms=None) — faithful because every
        # per-task provider override is empty in the eval environment.
        out = await PipelineOrchestrator(JobStore(), llm=llm).run(job)
    finally:
        settings.ner_cross_validation_enabled = prev

    preds: list[PredSpan] = []
    for ann in (out.result.annotations if out.result else []):
        if ann.state != "confirmed" or not ann.concepts:
            continue
        iri = ann.concepts[0].folio_iri or ""
        preds.append(PredSpan(start=ann.span.start, end=ann.span.end, iri=iri))
    return preds


async def run_full_eval(gold: list[GoldEntry]) -> dict:
    """Full-pipeline OFF-vs-ON evaluation with a single paid LLM pass per doc."""
    by_doc: dict[str, list[GoldEntry]] = defaultdict(list)
    for e in gold:
        by_doc[e.doc_id].append(e)
    doc_sources = {e.doc_id: e.doc_source for e in gold}
    scored_total = sum(1 for e in gold if e.is_scored)

    llm, usage, model_id = build_llm()

    results: dict[str, dict] = {}
    global_prf = {False: PRF(), True: PRF()}
    outcomes: dict[bool, list[EntryOutcome]] = {False: [], True: []}
    per_doc_usage: dict[str, dict] = {}
    # Raw confirmed predictions per doc/flag — lets a gold-set change be re-scored
    # offline (metrics.score_set) without paying for another LLM pass.
    raw_preds: dict[str, dict[str, list[dict]]] = {}
    t0 = time.time()

    for doc_id in sorted(by_doc):
        # Safety brake: stop before spending near the cap.
        projected = usage.cost_usd(PRICE_HIGH)
        if projected >= SPEND_ABORT_USD:
            results[doc_id] = {"skipped": "spend-cap brake tripped"}
            break

        text = load_demo_content(doc_sources[doc_id])
        doc_gold = by_doc[doc_id]
        results[doc_id] = {}

        # --- OFF: the one real LLM pass (populates cache) --------------------
        before_off = usage.snapshot()
        preds_off = await annotate_full(text, False, llm)
        after_off = usage.snapshot()

        # --- ON: reconciliation replay; LLM stages hit cache (~0 new calls) --
        preds_on = await annotate_full(text, True, llm)
        after_on = usage.snapshot()

        per_doc_usage[doc_id] = {
            "off_real_calls": after_off["calls"] - before_off["calls"],
            "off_input_tokens": after_off["input_tokens"] - before_off["input_tokens"],
            "off_output_tokens": after_off["output_tokens"] - before_off["output_tokens"],
            "on_added_real_calls": after_on["calls"] - after_off["calls"],
            "on_added_input_tokens": after_on["input_tokens"] - after_off["input_tokens"],
            "on_added_output_tokens": after_on["output_tokens"] - after_off["output_tokens"],
            "on_cache_hits": after_on["cache_hits"] - after_off["cache_hits"],
        }

        raw_preds[doc_id] = {
            "ner_off": [{"start": p.start, "end": p.end, "iri": p.iri} for p in preds_off],
            "ner_on": [{"start": p.start, "end": p.end, "iri": p.iri} for p in preds_on],
        }

        for flag, preds in ((False, preds_off), (True, preds_on)):
            prf, oc = score_set(doc_gold, preds)
            for k in ("tp", "fp", "fn", "tn"):
                setattr(global_prf[flag], k, getattr(global_prf[flag], k) + getattr(prf, k))
            outcomes[flag].extend(oc)
            results[doc_id][f"ner_{'on' if flag else 'off'}"] = prf.as_dict()

    elapsed = round(time.time() - t0, 1)

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

    off_by_id = {o.gold_id: o for o in outcomes[False]}
    changed = [
        {"gold_id": o.gold_id, "off": off_by_id[o.gold_id].outcome, "on": o.outcome}
        for o in outcomes[True]
        if o.gold_id in off_by_id and off_by_id[o.gold_id].outcome != o.outcome
    ]

    total_on_added_calls = sum(d["on_added_real_calls"] for d in per_doc_usage.values())

    return {
        "mode": "full",
        "fidelity": "authoritative (full pipeline; LLM candidate stages ON)",
        "model": model_id,
        "gold_entries_total": len(gold),
        "gold_entries_scored": scored_total,
        "docs": sorted(by_doc),
        "elapsed_seconds": elapsed,
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
        "llm_usage": {
            "total_real_calls": usage.calls,
            "total_cache_hits": usage.cache_hits,
            "total_input_tokens": usage.input_tokens,
            "total_output_tokens": usage.output_tokens,
            "on_replay_added_calls": total_on_added_calls,
            "on_replay_was_free": total_on_added_calls == 0,
            "estimated_cost_usd": {
                "low": round(usage.cost_usd(PRICE_LOW), 4),
                "high": round(usage.cost_usd(PRICE_HIGH), 4),
            },
            "price_assumption_per_1m": {"low": PRICE_LOW, "high": PRICE_HIGH},
            "per_doc": per_doc_usage,
        },
        "per_doc": results,
        "raw_predictions": raw_preds,
    }
