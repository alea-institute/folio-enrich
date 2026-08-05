"""Regression tests for the _resolve_overlaps active-interval sweep.

The 2026-08-05 AC-engine shootout (folio-resolve `bench/AC-ENGINE-RESULTS.md`) measured this
matcher's previous full-rescan resolver as O(m^2) in match count: on the 156,876-char demo
corpus it burned 0.364 s of a 0.373 s end-to-end search, leaving the pyahocorasick automaton
walk at ~6% of the time. The sweep ported from folio-resolve must (a) make byte-identical
decisions -- pinned here by fuzzing against a verbatim copy of the rescan, which is the
semantics oracle -- and (b) scale near-linearly on disjoint-region inputs, pinned by a
generous wall-clock bound the rescan misses by more than an order of magnitude.

Parity is the gate, not speed: downstream consumers and the committed migration captures
under `migration/captures/` depend on exact spans, so a faster resolver that moves one span
is a failure, not a win.
"""

from __future__ import annotations

import random
import time

from app.services.matching.aho_corasick import AhoCorasickMatcher, MatchResult


def _reference_resolve(matches: list[MatchResult]) -> list[MatchResult]:
    """Verbatim copy of the pre-sweep full-rescan implementation (the semantics oracle)."""
    if not matches:
        return []
    matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
    resolved: list[MatchResult] = []
    for match in matches:
        dominated = False
        for i, kept in enumerate(resolved):
            if match.start >= kept.end or match.end <= kept.start:
                continue
            if match.start == kept.start and match.end == kept.end:
                dominated = True
                break
            if match.start >= kept.start and match.end <= kept.end:
                continue
            if kept.start >= match.start and kept.end <= match.end:
                continue
            match_len = match.end - match.start
            kept_len = kept.end - kept.start
            if match_len > kept_len:
                resolved[i] = match
                dominated = True
                break
            else:
                dominated = True
                break
        if not dominated:
            resolved.append(match)
    resolved.sort(key=lambda m: (m.start, -(m.end - m.start)))
    return resolved


def _mk(start: int, end: int, tag: str = "") -> MatchResult:
    return MatchResult(pattern=tag or f"p{start}-{end}", start=start, end=end, value={})


def _as_tuples(matches: list[MatchResult]) -> list[tuple[int, int, str]]:
    return [(m.start, m.end, m.pattern) for m in matches]


class TestSweepEquivalence:
    def test_fuzz_matches_reference_semantics(self):
        """10k random cases: sweep output == old rescan output, span for span, in order."""
        matcher = AhoCorasickMatcher()
        rng = random.Random(42)
        for _ in range(10_000):
            n = rng.randint(0, 12)
            case = []
            for j in range(n):
                start = rng.randint(0, 30)
                end = start + rng.randint(1, 12)
                case.append(_mk(start, end, tag=f"t{j}"))
            expected = _as_tuples(
                _reference_resolve([_mk(m.start, m.end, m.pattern) for m in case])
            )
            actual = _as_tuples(matcher._resolve_overlaps(list(case)))
            assert actual == expected, f"divergence on case {_as_tuples(case)}"

    def test_fuzz_dense_clusters_match_reference(self):
        """Dense same-start / same-length clusters — the tie-breaking corners."""
        matcher = AhoCorasickMatcher()
        rng = random.Random(1337)
        for _ in range(5_000):
            case = []
            for j in range(rng.randint(0, 10)):
                start = rng.randint(0, 6)
                end = start + rng.randint(1, 4)
                case.append(_mk(start, end, tag=f"t{j}"))
            expected = _as_tuples(
                _reference_resolve([_mk(m.start, m.end, m.pattern) for m in case])
            )
            actual = _as_tuples(matcher._resolve_overlaps(list(case)))
            assert actual == expected, f"divergence on case {_as_tuples(case)}"

    def test_known_semantics_pinned(self):
        matcher = AhoCorasickMatcher()
        # duplicate span deduped — first wins
        out = matcher._resolve_overlaps([_mk(0, 5, "a"), _mk(0, 5, "b")])
        assert _as_tuples(out) == [(0, 5, "a")]
        # contained spans both survive
        out = matcher._resolve_overlaps([_mk(0, 10, "outer"), _mk(2, 6, "inner")])
        assert _as_tuples(out) == [(0, 10, "outer"), (2, 6, "inner")]
        # partial overlap: longer wins
        out = matcher._resolve_overlaps([_mk(0, 6, "short"), _mk(3, 12, "longer")])
        assert _as_tuples(out) == [(3, 12, "longer")]
        # partial overlap: shorter loses, kept span survives
        out = matcher._resolve_overlaps([_mk(0, 12, "longer"), _mk(3, 9, "short")])
        assert _as_tuples(out) == [(0, 12, "longer"), (3, 9, "short")]
        # disjoint spans untouched, output sorted by start
        out = matcher._resolve_overlaps([_mk(10, 15, "b"), _mk(0, 5, "a")])
        assert _as_tuples(out) == [(0, 5, "a"), (10, 15, "b")]

    def test_retired_span_cannot_be_revived(self):
        """A span retired from the active window must stay in the output untouched.

        The sweep's whole risk is retiring a kept span too early. Here the first span ends
        before the last one starts, so it leaves the window and must survive verbatim.
        """
        matcher = AhoCorasickMatcher()
        case = [_mk(0, 10, "a"), _mk(5, 20, "b"), _mk(40, 50, "c")]
        assert _as_tuples(matcher._resolve_overlaps(case)) == _as_tuples(
            _reference_resolve([_mk(0, 10, "a"), _mk(5, 20, "b"), _mk(40, 50, "c")])
        )

    def test_end_to_end_search_unchanged(self):
        """The public search() output is identical through the sweep (nested + overlaps)."""
        matcher = AhoCorasickMatcher()
        matcher.add_patterns(
            {
                "summary judgment": {"id": "1"},
                "judgment": {"id": "2"},
                "motion for summary judgment": {"id": "3"},
            }
        )
        matcher.build()
        got = [
            (m.pattern, m.start, m.end)
            for m in matcher.search("The Motion for Summary Judgment was denied.")
        ]
        assert got == [
            ("motion for summary judgment", 4, 31),
            ("summary judgment", 15, 31),
            ("judgment", 23, 31),
        ]

    def test_search_output_matches_reference_resolver_on_prose(self):
        """End-to-end: real matcher output == what the old rescan would have produced.

        This is the corpus-shaped guard. It re-resolves the same raw matches with the oracle
        and asserts span-for-span equality, so a resolver change that moved any span fails
        here even if no unit fixture happened to cover it.
        """
        matcher = AhoCorasickMatcher()
        matcher.add_patterns(
            {
                "court": {"id": "1"},
                "district court": {"id": "2"},
                "court of appeals": {"id": "3"},
                "appeals": {"id": "4"},
                "summary judgment": {"id": "5"},
                "judgment": {"id": "6"},
                "motion": {"id": "7"},
                "motion for summary judgment": {"id": "8"},
                "breach": {"id": "9"},
                "breach of contract": {"id": "10"},
                "contract": {"id": "11"},
                # Partial overlaps — different lengths (longer wins) and equal lengths
                # (keep-first). Real prose is almost all containment: on the 156,876-char
                # demo corpus only 14 of 4,928 raw matches lose to a partial overlap, so
                # these have to be planted deliberately or this guard is vacuous.
                "new york": {"id": "12"},
                "york county": {"id": "13"},
                "state court": {"id": "14"},
                "court order": {"id": "15"},
            }
        )
        matcher.build()
        text = (
            "The district court denied the motion for summary judgment. "
            "On appeal, the court of appeals reversed, holding that the breach of "
            "contract claim survived. The court entered judgment accordingly, and a "
            "later motion for summary judgment on the contract count was denied. "
            "The new york county clerk docketed the state court order the same day."
        ) * 6

        actual = [(m.start, m.end, m.pattern) for m in matcher.search(text)]

        # Re-derive the raw (pre-resolution) matches and run the oracle over them.
        original = AhoCorasickMatcher._resolve_overlaps
        try:
            AhoCorasickMatcher._resolve_overlaps = lambda self, matches: matches
            raw = matcher.search(text)
        finally:
            AhoCorasickMatcher._resolve_overlaps = original
        expected = [(m.start, m.end, m.pattern) for m in _reference_resolve(raw)]

        assert actual == expected
        assert actual, "fixture produced no matches — the guard would be vacuous"
        # The fixture must actually exercise partial-overlap resolution, or it only proves
        # that containment works. Two distinct branches are pinned: "york county" (11 chars)
        # displaces the shorter "new york" (8), and "court order" loses to "state court" on
        # an *equal*-length tie, where the rule is keep-first.
        assert len(raw) > len(actual), "no span was dropped — no overlap conflict exercised"
        kept_patterns = {p for _, _, p in actual}
        assert "york county" in kept_patterns and "new york" not in kept_patterns
        assert "state court" in kept_patterns and "court order" not in kept_patterns


class TestSweepScaling:
    def test_disjoint_regions_scale_near_linearly(self):
        """40k matches over disjoint regions (the repeated-document shape from the shootout).

        The rescan needs ~800M span comparisons here (minutes); the sweep retires each region
        as the scan passes it and finishes well inside the bound. The bound is deliberately
        generous (CI-safe) — it exists to catch a reintroduced O(m^2) rescan, which overshoots
        it by more than an order of magnitude.
        """
        matcher = AhoCorasickMatcher()
        matches = []
        for region in range(10_000):
            base = region * 50  # disjoint 50-char regions, 4 nested/overlapping spans each
            matches.append(_mk(base, base + 30))
            matches.append(_mk(base + 2, base + 12))
            matches.append(_mk(base + 4, base + 8))
            matches.append(_mk(base + 20, base + 40))
        t0 = time.perf_counter()
        out = matcher._resolve_overlaps(matches)
        elapsed = time.perf_counter() - t0
        assert len(out) == 30_000  # per region: 30-span keeps its 2 nested; 20-40 overlap loses
        assert elapsed < 5.0, f"overlap resolution took {elapsed:.1f}s — quadratic regression?"
