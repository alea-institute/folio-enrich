import pytest

from app.services.matching.aho_corasick import AhoCorasickMatcher


class TestAhoCorasickMatcher:
    def test_basic_search(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("breach of contract", {"iri": "iri1"})
        matcher.add_pattern("damages", {"iri": "iri2"})
        matcher.build()

        results = matcher.search("The breach of contract resulted in damages to the plaintiff.")
        assert len(results) == 2
        assert results[0].pattern == "breach of contract"
        assert results[0].value == {"iri": "iri1"}
        assert results[1].pattern == "damages"

    def test_case_insensitive(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("Motion to Dismiss", {"iri": "iri1"})
        matcher.build()

        results = matcher.search("The motion to dismiss was granted.")
        assert len(results) == 1
        assert results[0].pattern == "Motion to Dismiss"

    def test_word_boundary_check(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("contract", {"iri": "iri1"})
        matcher.build()

        # Should NOT match "contractual" — no word boundary at end
        results = matcher.search("The contractual obligation was clear.")
        assert len(results) == 0

        # Should match standalone "contract"
        results = matcher.search("The contract was signed.")
        assert len(results) == 1

    def test_contained_spans_both_kept(self):
        """Contained spans should both survive (breach inside breach of contract)."""
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("breach", {"iri": "short"})
        matcher.add_pattern("breach of contract", {"iri": "long"})
        matcher.build()

        results = matcher.search("The breach of contract was evident.")
        assert len(results) == 2
        patterns = {r.pattern for r in results}
        assert "breach of contract" in patterns
        assert "breach" in patterns

    def test_multiple_occurrences(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("damages", {"iri": "iri1"})
        matcher.build()

        results = matcher.search("The damages were severe. Additional damages were found.")
        assert len(results) == 2

    def test_no_matches(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("habeas corpus", {})
        matcher.build()

        results = matcher.search("This text has no legal terms.")
        assert len(results) == 0

    def test_correct_offsets(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("court", {})
        matcher.build()

        text = "The court ruled."
        results = matcher.search(text)
        assert len(results) == 1
        assert results[0].start == 4
        assert results[0].end == 9
        assert text[results[0].start : results[0].end] == "court"

    def test_add_patterns_bulk(self):
        matcher = AhoCorasickMatcher()
        matcher.add_patterns({
            "tort": {"iri": "1"},
            "negligence": {"iri": "2"},
            "duty of care": {"iri": "3"},
        })
        matcher.build()
        assert matcher.pattern_count == 3

    def test_partial_overlap_longer_wins(self):
        """Partial overlaps (crossing boundaries) should resolve to the longer match."""
        matcher = AhoCorasickMatcher()
        # These would partially overlap if they both appeared at overlapping positions
        matcher.add_pattern("new york", {"iri": "ny"})
        matcher.add_pattern("york county", {"iri": "yc"})
        matcher.build()

        # "new york county" — "new york" starts at 4, "york county" starts at 8
        # These partially overlap (york is shared), so longer one wins or first
        results = matcher.search("The new york county case.")
        # Both patterns match at different positions but overlap on "york"
        # new york = (4,12), york county = (8,20) — partial overlap → one wins
        assert len(results) == 1

    def test_identical_spans_deduplicated(self):
        """Identical spans should be deduplicated."""
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("contract", {"iri": "1"})
        matcher.build()

        results = matcher.search("The contract was signed.")
        assert len(results) == 1

    def test_contained_inner_span_kept(self):
        """Inner span fully contained within outer span should be kept."""
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("contract", {"iri": "inner"})
        matcher.add_pattern("breach of contract", {"iri": "outer"})
        matcher.build()

        results = matcher.search("The breach of contract was clear.")
        assert len(results) == 2
        iris = {r.value["iri"] for r in results}
        assert "inner" in iris
        assert "outer" in iris
        # Outer span should come first (earlier start)
        assert results[0].pattern == "breach of contract"
        assert results[1].pattern == "contract"

    def test_auto_build_on_search(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("test", {})
        # Don't call build() — should auto-build
        results = matcher.search("This is a test.")
        assert len(results) == 1


class TestCaseSensitiveSearch:
    """`case_sensitive=True` was silently inverted until 2026-08-05.

    Patterns are keyed lowercase by `add_pattern`, but the flag used to walk the
    *original*-cased text against that lowercase trie, so it matched only text that
    happened already to be lowercase — the opposite of what the name promises. There were
    zero call sites, so this was a latent trap rather than a live defect; these tests keep
    it shut. Semantics now match folio-resolve's matcher (the shootout's `py` engine).
    """

    TEXT = "The Court ruled. the court adjourned. THE COURT reconvened."

    def _matcher(self):
        matcher = AhoCorasickMatcher()
        matcher.add_patterns({"Court": {"iri": "c"}, "ruled": {"iri": "r"}})
        matcher.build()
        return matcher

    def test_case_sensitive_keeps_only_the_registered_casing(self):
        results = self._matcher().search(self.TEXT, case_sensitive=True)
        assert [(r.start, r.end, r.pattern) for r in results] == [
            (4, 9, "Court"),
            (10, 15, "ruled"),
        ]

    def test_case_sensitive_slice_equals_the_pattern(self):
        """The regression's signature: a hit whose text is not the pattern it claims."""
        for r in self._matcher().search(self.TEXT, case_sensitive=True):
            assert self.TEXT[r.start : r.end] == r.pattern

    def test_case_sensitive_rejects_other_casings(self):
        spans = {(r.start, r.end) for r in self._matcher().search(self.TEXT, case_sensitive=True)}
        assert (21, 26) not in spans, "lowercase 'court' must not match pattern 'Court'"
        assert (42, 47) not in spans, "uppercase 'COURT' must not match pattern 'Court'"

    def test_case_insensitive_still_finds_every_casing(self):
        """The production path is unchanged — all three casings still match."""
        results = self._matcher().search(self.TEXT, case_sensitive=False)
        assert [(r.start, r.end, r.pattern) for r in results] == [
            (4, 9, "Court"),
            (10, 15, "ruled"),
            (21, 26, "Court"),
            (42, 47, "Court"),
        ]

    def test_case_sensitive_lowercase_pattern_matches_only_lowercase(self):
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("court", {"iri": "c"})
        matcher.build()
        results = matcher.search(self.TEXT, case_sensitive=True)
        assert [(r.start, r.end) for r in results] == [(21, 26)]

    def test_case_sensitive_default_is_false(self):
        """Nothing on the production path passes the flag; the default must stay lenient."""
        matcher = AhoCorasickMatcher()
        matcher.add_pattern("Motion to Dismiss", {"iri": "m"})
        matcher.build()
        assert len(matcher.search("The motion to dismiss was granted.")) == 1

    def test_matches_folio_resolve_semantics(self):
        """Pin the library as the oracle — this is the contract the port aligns to."""
        pytest.importorskip("folio_resolve")
        from folio_resolve.matching.aho_corasick import AhoCorasickMatcher as LibMatcher

        lib = LibMatcher()
        lib.add_patterns({"Court": {"iri": "c"}, "ruled": {"iri": "r"}})
        lib.build()
        for flag in (True, False):
            ours = [(r.start, r.end, r.pattern) for r in self._matcher().search(self.TEXT, case_sensitive=flag)]
            theirs = [(r.start, r.end, r.pattern) for r in lib.search(self.TEXT, case_sensitive=flag)]
            assert ours == theirs, f"diverged from folio-resolve at case_sensitive={flag}"
