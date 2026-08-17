"""Precision-first proposition frames for judicial prose.

Values are initial ledger guesses, not final adjudications. Provenance-driven
tuning belongs in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropositionFrame:
    proposition_type: str
    asserter_role: str
    disposition: str
    validator_mode: str | None = None


PARTY_LAW = PropositionFrame("Legal Proposition", "party", "unresolved")
PARTY_FACT = PropositionFrame("Factual Statement", "party", "unresolved")
COURT_LAW = PropositionFrame("Judicial Legal Conclusion", "court", "accepted", "ruled")
COURT_FACT = PropositionFrame("Judicial Finding of Fact", "court", "accepted", "ruled")
SOURCE = PropositionFrame("secondary-source proposition", "secondary_source", "unresolved")
STIPULATION = PropositionFrame("stipulation", "both_parties", "accepted")


# Lemmas deliberately repeat a semantic frame where surface usage differs. The
# roughly fifty-entry set favors explicit attribution over broad speech verbs.
REPORTING_VERBS: dict[str, PropositionFrame] = {
    "contend": PARTY_LAW, "argue": PARTY_LAW, "assert": PARTY_LAW,
    "allege": PARTY_FACT, "maintain": PARTY_LAW, "claim": PARTY_LAW,
    "urge": PARTY_LAW, "submit": PARTY_LAW, "insist": PARTY_LAW,
    "suggest": PARTY_LAW, "counter": PARTY_LAW, "reply": PARTY_LAW,
    "respond": PARTY_LAW, "aver": PARTY_FACT, "testify": PARTY_FACT,
    "concede": PARTY_LAW, "acknowledge": PARTY_FACT, "admit": PARTY_FACT,
    "deny": PARTY_FACT, "dispute": PARTY_FACT, "contest": PARTY_LAW,
    "object": PARTY_LAW, "move": PARTY_LAW, "request": PARTY_LAW,
    "petition": PARTY_LAW, "appeal": PARTY_LAW,
    "stipulate": STIPULATION, "agree": STIPULATION,
    "hold": COURT_LAW, "conclude": COURT_LAW, "rule": COURT_LAW,
    "determine": COURT_LAW, "reason": COURT_LAW, "declare": COURT_LAW,
    "opine": COURT_LAW, "affirm": COURT_LAW, "reverse": COURT_LAW,
    "remand": COURT_LAW, "vacate": COURT_LAW, "overrule": COURT_LAW,
    "sustain": COURT_LAW, "grant": COURT_LAW, "find": COURT_FACT,
    "note": COURT_FACT, "observe": COURT_FACT, "assume": COURT_LAW,
    "presume": COURT_LAW, "emphasize": COURT_LAW, "reiterate": COURT_LAW,
    "caution": COURT_LAW, "disagree": COURT_LAW,
    "state": SOURCE, "explain": SOURCE, "report": SOURCE,
}


ARGUENDO_MARKERS: tuple[str, ...] = (
    "assume, without deciding",
    "assuming, without deciding",
    "we assume, arguendo",
    "assuming arguendo",
    "even if",
)

ARGUENDO_FRAME = PropositionFrame(
    "arguendo assumption", "court", "assumed-arguendo", "declined"
)
