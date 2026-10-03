from __future__ import annotations

import json
from pathlib import Path

import pytest


GOLD_DIR = Path(__file__).resolve().parents[1] / "eval/gold/propositions"


def _palsgraf():
    manifest = json.loads((GOLD_DIR / "manifest.json").read_text())
    entry = next(e for e in manifest["opinions"] if e["slug"] == "palsgraf-248-ny-339")
    text = (GOLD_DIR / entry["text_file"]).read_bytes().decode("utf-8")
    rows = [json.loads(line) for line in (GOLD_DIR / f"{entry['slug']}.jsonl").read_text().splitlines()]
    return entry, text, [r for r in rows if r["record_type"] == "annotation"]


def _assert_spans(text, rows):
    for row in rows:
        p = row["proposition"]
        start, end = p["start_char"], p["end_char"]
        assert 0 <= start < end <= len(text), f"{row['annotation_id']} [{start}, {end})"
        assert text[start:end] == p["text"], f"{row['annotation_id']} [{start}, {end})"


def test_canonical_text_reproduces_all_annotation_spans():
    _, text, rows = _palsgraf()
    assert len(text) == 31920
    assert len(rows) == 104
    _assert_spans(text, rows)


def test_shifted_text_fails_and_names_the_span():
    _, text, rows = _palsgraf()
    with pytest.raises(AssertionError, match=rows[0]["annotation_id"]):
        _assert_spans(" " + text, rows)


def test_split_ranges_cover_text_without_overlap_and_have_expected_counts():
    entry, text, rows = _palsgraf()
    ranges = sorted(entry["splits"].values())
    assert ranges[0][0] == 0
    assert ranges[-1][1] == len(text)
    assert all(a[1] == b[0] for a, b in zip(ranges, ranges[1:]))
    assert text[13488:].startswith("ANDREWS, J. (dissenting):")
    counts = {}
    for name, (start, end) in entry["splits"].items():
        counts[name] = sum(
            start <= r["proposition"]["start_char"] < r["proposition"]["end_char"] <= end
            for r in rows
        )
    assert counts == {"development": 46, "held-out": 58}


def test_demo_smoke_opts_out_of_benchmark():
    manifest = json.loads((GOLD_DIR / "manifest.json").read_text())
    assert next(e for e in manifest["opinions"] if e["slug"] == "demo-smoke")["benchmark"] is False
