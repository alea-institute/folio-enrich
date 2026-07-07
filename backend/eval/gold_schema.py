"""Gold-set data model + JSONL persistence for the NER eval harness.

A *gold entry* is one human-verifiable judgment about a single text span in a
source document:

    - ``positive`` polarity: the span SHOULD be annotated with ``expected_iri``.
    - ``negative`` polarity: the span should NOT map to ``expected_iri`` (a known
      false-positive / collision case). ``expected_iri`` names the wrong concept.

Gold is a *curated sample*, not an exhaustive labelling of the document, so the
metrics module scores span-restricted precision/recall over exactly these entries
(see ``metrics.py``). Every entry records how it was verified so a reader can trust
or re-check it:

    verification = "deterministic"  -> confirmed by the FOLIO label oracle (exact,
                                       unambiguous preferred-label match); safe to trust.
                 = "human"           -> a person reviewed and set the label. NEVER
                                       overwritten by the curator.
                 = "needs_review"    -> seeded but ambiguous; awaiting a human. Excluded
                                       from scoring until promoted (see metrics.score_set).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

VERIFICATION_VALUES = ("deterministic", "human", "needs_review")
POLARITY_VALUES = ("positive", "negative")
DIFFICULTY_VALUES = ("clear", "borderline")


@dataclass
class GoldSpan:
    """Character span into the document's canonical ``full_text`` (half-open)."""

    start: int
    end: int
    text: str


@dataclass
class GoldCandidate:
    """A competing concept for a borderline span (surfaced in the evidence pack)."""

    folio_iri: str
    folio_label: str
    branch: str = ""
    note: str = ""


@dataclass
class GoldEntry:
    gold_id: str
    doc_id: str
    doc_source: str
    span: GoldSpan
    expected_iri: str
    expected_label: str
    branch: str = ""
    polarity: str = "positive"
    verification: str = "needs_review"
    verified_by: str = ""
    difficulty: str = "clear"
    rationale: str = ""
    candidates: list[GoldCandidate] = field(default_factory=list)

    # ---- validation ------------------------------------------------------- #
    def validate(self) -> None:
        if self.polarity not in POLARITY_VALUES:
            raise ValueError(f"{self.gold_id}: bad polarity {self.polarity!r}")
        if self.verification not in VERIFICATION_VALUES:
            raise ValueError(f"{self.gold_id}: bad verification {self.verification!r}")
        if self.difficulty not in DIFFICULTY_VALUES:
            raise ValueError(f"{self.gold_id}: bad difficulty {self.difficulty!r}")
        if self.span.end <= self.span.start:
            raise ValueError(f"{self.gold_id}: empty/negative span {self.span}")
        if not self.expected_iri:
            raise ValueError(f"{self.gold_id}: missing expected_iri")

    @property
    def is_scored(self) -> bool:
        """Only deterministic + human entries count toward metrics."""
        return self.verification in ("deterministic", "human")

    # ---- (de)serialization ------------------------------------------------ #
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GoldEntry":
        # Tolerate unknown keys (forward-compat with a newer writer) by keeping only
        # this dataclass's own fields.
        known = {f.name for f in fields(cls)}
        span = GoldSpan(**{k: v for k, v in d["span"].items()
                           if k in {f.name for f in fields(GoldSpan)}})
        cands = [
            GoldCandidate(**{k: v for k, v in c.items()
                             if k in {f.name for f in fields(GoldCandidate)}})
            for c in d.get("candidates", [])
        ]
        rest = {k: v for k, v in d.items() if k in known and k not in ("span", "candidates")}
        return cls(span=span, candidates=cands, **rest)


def load_gold(path: str | Path) -> list[GoldEntry]:
    """Load a JSONL gold file (one entry per line). Empty/comment lines ignored."""
    path = Path(path)
    entries: list[GoldEntry] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entry = GoldEntry.from_dict(json.loads(line))
        entry.validate()
        entries.append(entry)
    return entries


def save_gold(entries: list[GoldEntry], path: str | Path) -> None:
    """Write entries as JSONL, sorted by gold_id for stable diffs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(entries, key=lambda e: e.gold_id)
    lines = [json.dumps(e.to_dict(), ensure_ascii=False, sort_keys=True) for e in ordered]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
