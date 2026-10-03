from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from eval.proposition_benchmark import (
    Span,
    candidate_span,
    dice,
    indicative_overfit,
    load_records,
    run_benchmark,
    score_split,
    split_ranges,
    wilson_interval,
)


def span(start, end, kind="Judicial Legal Conclusion", pattern="reporting-verb"):
    return Span(start, end, kind, pattern)


@pytest.mark.parametrize("overlap, matched", [(50, 1), (49, 0)])
def test_dice_threshold_is_inclusive(overlap, matched):
    gold, candidate = span(0, 100), span(100 - overlap, 200 - overlap)
    assert dice(gold, candidate) == overlap / 100
    assert score_split([gold], [candidate])["matched"] == matched


def test_short_contained_fragment_does_not_match():
    result = score_split([span(0, 100)], [span(40, 50)])
    assert result["matched"] == 0
    assert result["precision"] == 0


def test_one_candidate_credits_only_one_gold():
    result = score_split([span(0, 100), span(100, 200)], [span(0, 200)])
    assert result["matched"] == 1
    assert result["recall"] == 0.5


def test_highest_dice_pair_is_assigned_first():
    result = score_split([span(0, 100), span(100, 200)], [span(0, 200), span(0, 100)])
    assert result["matched"] == 2
    assert result["exact"] == 1


def test_duplicate_candidates_do_not_credit_gold_twice():
    result = score_split([span(0, 100)], [span(0, 100), span(0, 100)])
    assert result["matched"] == 1
    assert result["precision"] == 0.5


def test_deleted_candidate_is_false_positive_even_inside_gold():
    result = score_split([span(0, 100)], [span(0, 100)], [span(0, 100)])
    assert result["matched"] == 0
    assert result["audit_false_positives"] == 1
    assert result["precision"] == 0


def test_only_annotations_are_gold_and_audits_support_original(tmp_path):
    proposition = {"start_char": 0, "end_char": 10, "text": "abcdefghij", "proposition_type": "Legal Proposition"}
    rows = [
        {"record_type": "annotation", "proposition": proposition},
        {"record_type": "cycle-learning", "proposition": proposition},
        {"record_type": "blind-segment", "start_char": 0, "end_char": 10},
        {"record_type": "candidate-audit", "original": proposition},
    ]
    path = tmp_path / "gold.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows))
    gold, audits = load_records(path, "abcdefghij")
    assert len(gold) == len(audits) == 1
    assert score_split(gold, [span(0, 10)], audits)["matched"] == 0


def test_integrity_failure_names_annotation(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text(json.dumps({
        "record_type": "annotation", "annotation_id": "shifted-span",
        "proposition": {"start_char": 0, "end_char": 3, "text": "abc", "proposition_type": "Legal Proposition"},
    }))
    with pytest.raises(ValueError, match="shifted-span"):
        load_records(path, " abc")


def test_no_splits_defaults_to_all_held_out():
    assert split_ranges({}, 20) == {"held-out": (0, 20)}


def test_benchmark_skips_fixtures_and_uses_canonical_job(tmp_path, monkeypatch):
    from app.services.proposition.extractor import PropositionExtractor

    text = "Canonical text."
    (tmp_path / "opinion.txt").write_text(text)
    (tmp_path / "opinion.jsonl").write_text(json.dumps({
        "record_type": "annotation", "proposition": {
            "start_char": 0, "end_char": len(text), "text": text,
            "proposition_type": "Judicial Legal Conclusion",
        },
    }))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"opinions": [
        {"slug": "fixture-with-no-files", "benchmark": False},
        {"slug": "opinion", "text_file": "opinion.txt"},
    ]}))
    calls = []

    def extract(self, job):
        calls.append(job)
        return [SimpleNamespace(start_char=0, end_char=len(text), proposition_type="Judicial Legal Conclusion")]

    monkeypatch.setattr(PropositionExtractor, "extract", extract)
    report = run_benchmark(manifest)
    assert len(calls) == 1
    assert calls[0].result.canonical_text.full_text == text
    assert calls[0].result.individuals == []
    assert report["splits"]["held-out"]["matched"] == 1
    assert report["overall"]["gold"] == 1


def test_wilson_interval_known_value_and_empty_denominator():
    assert wilson_interval(5, 10) == pytest.approx((0.2365930905, 0.7634069095))
    assert wilson_interval(0, 0) == (0.0, 1.0)


@pytest.mark.parametrize("held_out, flagged", [(0.64, True), (0.65, False)])
def test_overfit_threshold_is_strict(held_out, flagged):
    assert indicative_overfit(0.8, held_out) is flagged


def test_empty_candidates_do_not_divide_by_zero():
    result = score_split([span(0, 100)], [])
    assert result["recall"] == result["precision"] == result["f1"] == 0
    assert result["precision_ci"] == (0.0, 1.0)


def test_type_recall_pattern_hits_and_type_agreement():
    result = score_split(
        [span(0, 100), span(100, 200, "Legal Proposition")],
        [span(0, 100, "Legal Proposition", "copular")],
    )
    assert result["per_type"]["Judicial Legal Conclusion"]["recall"] == 1
    assert result["per_type"]["Legal Proposition"]["recall"] == 0
    assert result["per_pattern"]["copular"] == {"candidates": 1, "matched": 1, "exact": 1}
    assert result["type_agreement"] == {"matched": 1, "agreed": 0, "rate": 0}


@pytest.mark.parametrize("kind, expected", [("arguendo assumption", "arguendo"), ("Legal Proposition", "reporting-verb")])
def test_pattern_fallback_and_future_frame_attribute(kind, expected):
    candidate = SimpleNamespace(start_char=0, end_char=10, proposition_type=kind)
    assert candidate_span(candidate).pattern == expected
    candidate.frame = SimpleNamespace(pattern_name="modal")
    assert candidate_span(candidate).pattern == "modal"
    candidate.pattern_name = "copular"
    assert candidate_span(candidate).pattern == "copular"


def test_crossing_candidate_is_counted_once_in_start_split(tmp_path, monkeypatch):
    from app.services.proposition.extractor import PropositionExtractor

    (tmp_path / "opinion.txt").write_text("a" * 20)
    (tmp_path / "opinion.jsonl").write_text("")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"opinions": [{
        "slug": "opinion", "text_file": "opinion.txt",
        "splits": {"development": [0, 10], "held-out": [10, 20]},
    }]}))
    monkeypatch.setattr(PropositionExtractor, "extract", lambda self, job: [
        SimpleNamespace(start_char=9, end_char=12, proposition_type="Legal Proposition"),
    ])
    report = run_benchmark(manifest)
    assert report["splits"]["development"]["candidates"] == 1
    assert report["splits"]["held-out"]["candidates"] == 0
    assert report["overall"]["candidates"] == 1


def test_development_only_parses_full_text_without_validating_excluded_gold(tmp_path, monkeypatch):
    from app.services.proposition.extractor import PropositionExtractor

    development = 'The duty is clear.'
    (tmp_path / 'opinion.txt').write_text(development + 'EXCLUDED SENTINEL')
    (tmp_path / 'opinion.jsonl').write_text('\n'.join([
        json.dumps({'record_type': 'annotation', 'proposition': {
            'start_char': 0, 'end_char': len(development), 'text': development,
            'proposition_type': 'Judicial Legal Conclusion',
        }}),
        json.dumps({'record_type': 'annotation', 'proposition': {
            'start_char': len(development), 'end_char': 9999, 'text': 'invalid excluded row',
            'proposition_type': 'Judicial Legal Conclusion',
        }}),
    ]))
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'opinions': [
        {'slug': 'future-held-out-with-no-files', 'text_file': 'missing.txt'},
        {'slug': 'opinion', 'text_file': 'opinion.txt', 'splits': {
            'development': [0, len(development)], 'held-out': [len(development), len(development + 'EXCLUDED SENTINEL')],
        }},
    ]}))

    def extract(self, job):
        assert job.result.canonical_text.full_text == development + 'EXCLUDED SENTINEL'
        return []

    monkeypatch.setattr(PropositionExtractor, 'extract', extract)
    report = run_benchmark(manifest, split='development')
    assert set(report['splits']) == {'development'}
    assert report['overall']['gold'] == 1
    assert report['overfit']['flag'] is None


@pytest.mark.parametrize("kind", ["annotation", "candidate-audit"])
def test_split_filter_uses_scoring_offsets_instead_of_first_raw_offset(tmp_path, kind):
    def proposition(start):
        return {"start_char": start, "end_char": start + 5,
                "text": "abcde", "proposition_type": "Legal Proposition"}

    path = tmp_path / "gold.jsonl"
    path.write_text("\n".join(json.dumps({
        "record_type": kind, "original": proposition(original),
        "proposition": proposition(corrected),
    }) for original, corrected in [(10, 0), (0, 10)]))
    gold, audits = load_records(path, "abcde" * 4, [(0, 10)])
    assert (gold if kind == "annotation" else audits) == [span(0, 5, "Legal Proposition")]


def test_split_only_equals_full_row_with_sentence_crossing_boundary(tmp_path, capsys):
    from eval.proposition_benchmark import print_report

    text = "A carrier must exercise care. A claimant may recover."
    boundary = text.index(" care")
    (tmp_path / "opinion.txt").write_text(text)
    (tmp_path / "opinion.jsonl").write_text(json.dumps({
        "record_type": "annotation", "proposition": {
            "start_char": 0, "end_char": boundary, "text": text[:boundary],
            "proposition_type": "Judicial Legal Conclusion",
        },
    }))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"opinions": [{
        "slug": "opinion", "text_file": "opinion.txt", "splits": {
            "development": [0, boundary], "held-out": [boundary, len(text)],
        },
    }]}))
    full = run_benchmark(manifest)
    selected = run_benchmark(manifest, split="development")
    assert selected["splits"] == {"development": full["splits"]["development"]}
    assert selected["documents"][0]["splits"] == {
        "development": full["documents"][0]["splits"]["development"]}
    print_report(selected)
    output = capsys.readouterr().out
    assert "held-out" not in output
    assert text[boundary:] not in output


def test_benchmark_passes_only_overlapping_audits_to_each_split(tmp_path, monkeypatch):
    import eval.proposition_benchmark as benchmark
    from app.services.proposition.extractor import PropositionExtractor

    (tmp_path / "opinion.txt").write_text("a" * 20)
    audits = [span(0, 5), span(9, 12), span(10, 20)]
    (tmp_path / "opinion.jsonl").write_text("\n".join(json.dumps({
        "record_type": "candidate-audit", "original": {
            "start_char": a.start, "end_char": a.end,
            "proposition_type": a.proposition_type,
        },
    }) for a in audits))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"opinions": [{
        "slug": "opinion", "text_file": "opinion.txt",
        "splits": {"development": [0, 10], "held-out": [10, 20]},
    }]}))
    monkeypatch.setattr(PropositionExtractor, "extract", lambda self, job: [])
    calls = []
    original_score = benchmark.score_split

    def score(gold, candidates, selected_audits):
        calls.append(selected_audits)
        return original_score(gold, candidates, selected_audits)

    monkeypatch.setattr(benchmark, "score_split", score)
    run_benchmark(manifest)
    assert calls == [audits[:2], audits[1:]]
    calls.clear()
    run_benchmark(manifest, split="development")
    assert calls == [audits[:2]]
