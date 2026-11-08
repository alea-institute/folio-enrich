"""The demo scorer runs without loading the application or ontology."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "demo_tag_eval.py"


def load_scorer():
    spec = importlib.util.spec_from_file_location("demo_tag_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def demo_fixture(tmp_path):
    demos = tmp_path / "demos"
    demos.mkdir()

    def annotation(text, iri, stage, **extra):
        return {"span": {"text": text}, "concepts": [{"folio_iri": iri}],
                "lineage": [{"stage": stage}, {"stage": "resolution"}], **extra}

    annotations = [
        annotation("Alpha", "a", "llm_concept"),
        annotation("ALPHA", "a", "llm_concept"),
        annotation("Alpha", "a", "entity_ruler"),
        annotation("Beta", "b", "entity_ruler"),
        annotation("BETA", "b", "entity_ruler"),
        annotation("Gamma", "g", "semantic_ruler"),
        annotation("New", "n", "custom_stage"),
        annotation("Rejected", "r", "llm_concept", state="rejected"),
        {"span": {"text": "Rejected concept"},
         "concepts": [{"folio_iri": "r", "state": "rejected"}]},
    ]
    payload = {"cache": {"job": {"result": {"annotations": annotations}}}}
    (demos / "tiny.json").write_text(json.dumps(payload))
    nested = demos / "nested"
    nested.mkdir()
    (nested / "ignored.json").write_text(json.dumps(payload))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"labels": [
        {"text": "alpha", "iri": "a", "verdict": "correct"},
        {"text": "beta", "iri": "b", "verdict": "wrong"},
        {"text": "gamma", "iri": "g", "verdict": "unsure"},
    ]}))
    return demos, labels


def test_score_unique_pairs_occurrences_and_origins(demo_fixture):
    demos, labels = demo_fixture
    summary = load_scorer().score(demos, labels)
    assert summary["overall"] == {
        "unique_pairs": {"correct": 1, "wrong": 1, "unsure": 1, "unlabeled": 1, "total": 4},
        "precision": 0.5,
        "occurrences": {"correct": 3, "wrong": 2, "unsure": 1, "unlabeled": 1, "total": 7},
    }
    assert set(summary["per_origin"]) == {"llm", "ruler", "semantic", "custom_stage"}
    assert summary["per_origin"]["llm"]["unique_pairs"]["correct"] == 1
    assert summary["per_origin"]["llm"]["occurrences"]["correct"] == 2
    assert summary["per_origin"]["ruler"]["precision"] == 0.5
    assert summary["per_origin"]["semantic"]["precision"] is None
    assert summary["top_wrong_pairs"] == [{"text": "beta", "iri": "b", "occurrences": 2}]
    assert summary["unlabeled_pairs"] == [{"text": "new", "iri": "n", "occurrences": 1}]


@pytest.mark.parametrize("command", [[], ["score"]])
def test_cli_defaults_score_and_writes_same_json(demo_fixture, tmp_path, command):
    demos, labels = demo_fixture
    output = tmp_path / "summary.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *command, "--demos-dir", str(demos),
         "--labels", str(labels), "--json", str(output)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(output.read_text()) == load_scorer().score(demos, labels)
    assert "Overall" in result.stdout
    assert "0.5000" in result.stdout
    assert "Top 30 wrong pairs" in result.stdout
    assert "beta" in result.stdout
    assert "Every unlabeled pair" in result.stdout
    assert "new" in result.stdout


def test_wrong_ranking_is_limited_but_unlabeled_list_is_complete(tmp_path):
    demos = tmp_path / "demos"
    demos.mkdir()
    annotations = []
    labels = []
    for index in range(35):
        labels.append({"text": f"wrong {index}", "iri": str(index), "verdict": "wrong"})
        for _ in range(index + 1):
            annotations.append({"span": {"text": f"Wrong {index}"},
                                "concepts": [{"folio_iri": str(index)}]})
        annotations.append({"span": {"text": f"New {index}"},
                            "concepts": [{"folio_iri": str(index)}]})
    (demos / "many.json").write_text(json.dumps(
        {"cache": {"job": {"result": {"annotations": annotations}}}}))
    label_path = tmp_path / "labels.json"
    label_path.write_text(json.dumps({"labels": labels}))
    summary = load_scorer().score(demos, label_path)
    assert len(summary["top_wrong_pairs"]) == 30
    assert summary["top_wrong_pairs"][0] == {"text": "wrong 34", "iri": "34", "occurrences": 35}
    assert summary["top_wrong_pairs"][-1]["occurrences"] == 6
    assert len(summary["unlabeled_pairs"]) == 35
    assert set(summary["per_origin"]) == {"unknown"}
