"""Span-restricted precision / recall / F1 for the NER eval harness.

Gold is a *curated sample*, so we score only over the gold-labelled spans rather
than treating every un-labelled prediction as a false positive (which would be
meaningless against a sample). This is the standard interpretation for a sampled
gold set and is documented in the plan.

Prediction ⇄ gold matching
--------------------------
A predicted (confirmed) annotation *covers* a gold span when their character spans
overlap: ``pred.start < gold.end and pred.end > gold.start``. Overlap (not exact
equality) is used because the ruler's span boundaries legitimately differ from the
hand-marked gold span (e.g. a pred span ``"This Agreement is"`` covers the gold span
``"Agreement"``). Concept identity is compared by FOLIO IRI *hash suffix* so prefix
variants (folio vs canon host) still match.

Counting (per scored gold entry)
--------------------------------
positive gold:
  - a covering prediction carries ``expected_iri``            → TP
  - covering prediction(s) exist but none carry expected_iri  → FN + FP (wrong label)
  - no covering prediction                                    → FN (miss)
negative gold (span should NOT map to expected_iri):
  - a covering prediction carries ``expected_iri``            → FP
  - otherwise                                                 → TN
"""

from __future__ import annotations

from dataclasses import dataclass

from .gold_schema import GoldEntry


def iri_key(iri: str | None) -> str:
    """Normalize a FOLIO IRI to its hash suffix for host-agnostic comparison."""
    if not iri:
        return ""
    return iri.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True)
class PredSpan:
    """Minimal view of a confirmed prediction: span + winning concept IRI."""

    start: int
    end: int
    iri: str

    def overlaps(self, start: int, end: int) -> bool:
        return self.start < end and self.end > start


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict:
        return {
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "support": self.tp + self.fn,  # positive gold count
        }


@dataclass
class EntryOutcome:
    gold_id: str
    polarity: str
    outcome: str            # "TP" | "FP" | "FN" | "TN" | "FN+FP"
    expected_iri: str
    predicted_iri: str      # the covering prediction's IRI ("" if none)


def score_entry(entry: GoldEntry, preds: list[PredSpan]) -> tuple[str, int, int, int, int, str]:
    """Return (outcome, tp, fp, fn, tn, predicted_iri) for one gold entry."""
    exp = iri_key(entry.expected_iri)
    covering = [p for p in preds if p.overlaps(entry.span.start, entry.span.end)]
    right = next((p for p in covering if iri_key(p.iri) == exp), None)
    pred_iri = (right.iri if right else (covering[0].iri if covering else ""))

    if entry.polarity == "positive":
        if right is not None:
            return "TP", 1, 0, 0, 0, pred_iri
        if covering:
            return "FN+FP", 0, 1, 1, 0, pred_iri  # wrong concept asserted here
        return "FN", 0, 0, 1, 0, ""
    # negative gold
    if right is not None:
        return "FP", 0, 1, 0, 0, pred_iri
    return "TN", 0, 0, 0, 1, pred_iri


def score_set(
    gold: list[GoldEntry], preds: list[PredSpan]
) -> tuple[PRF, list[EntryOutcome]]:
    """Score all *scored* (deterministic|human) gold entries against predictions."""
    prf = PRF()
    outcomes: list[EntryOutcome] = []
    for entry in gold:
        if not entry.is_scored:
            continue
        outcome, tp, fp, fn, tn, pred_iri = score_entry(entry, preds)
        prf.tp += tp
        prf.fp += fp
        prf.fn += fn
        prf.tn += tn
        outcomes.append(
            EntryOutcome(
                gold_id=entry.gold_id, polarity=entry.polarity, outcome=outcome,
                expected_iri=entry.expected_iri, predicted_iri=pred_iri,
            )
        )
    return prf, outcomes
