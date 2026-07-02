"""AC-3: Canon OWL rdfs:label build-gate.

The gate refuses an http-source OWL whose named-class rdfs:label coverage regressed
(folio-python silently drops label-less classes). Tested against tiny synthetic OWL
strings so it stays fast and offline.
"""

from __future__ import annotations

import pytest

from app.services.ontology.ingestion import (
    OWLIngestionError,
    assert_label_coverage,
    label_coverage_stats,
)
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC

_NS = (
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
    'xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" '
    'xmlns:owl="http://www.w3.org/2002/07/owl#"'
)

# Two named classes; one has an rdfs:label, one does not -> 50% coverage. Also one
# anonymous owl:Class (no rdf:about) which must be ignored by the stats.
_HALF_COVERED_OWL = f"""<?xml version="1.0"?>
<rdf:RDF {_NS}>
  <owl:Class rdf:about="https://ex.test/Labeled">
    <rdfs:label>Labeled Class</rdfs:label>
  </owl:Class>
  <owl:Class rdf:about="https://ex.test/NoLabel"></owl:Class>
  <owl:Class></owl:Class>
</rdf:RDF>
""".encode()

_FULLY_COVERED_OWL = f"""<?xml version="1.0"?>
<rdf:RDF {_NS}>
  <owl:Class rdf:about="https://ex.test/A"><rdfs:label>A</rdfs:label></owl:Class>
  <owl:Class rdf:about="https://ex.test/B"><rdfs:label>B</rdfs:label></owl:Class>
</rdf:RDF>
""".encode()


def test_stats_count_named_and_missing() -> None:
    named, missing, offenders = label_coverage_stats(_HALF_COVERED_OWL)
    assert named == 2  # anonymous class ignored
    assert missing == 1
    assert offenders == ["https://ex.test/NoLabel"]


def test_gate_fails_loudly_below_threshold() -> None:
    with pytest.raises(OWLIngestionError) as exc:
        assert_label_coverage(_HALF_COVERED_OWL, 100.0, "canon")
    msg = str(exc.value)
    assert "coverage gate" in msg
    assert "https://ex.test/NoLabel" in msg  # offender named
    assert "50.00%" in msg


def test_gate_passes_above_threshold() -> None:
    # 50% coverage clears a 40% bar; 100% coverage clears the 99% Canon bar.
    assert_label_coverage(_HALF_COVERED_OWL, 40.0, "canon")
    assert_label_coverage(_FULLY_COVERED_OWL, 99.0, "canon")


def test_gate_fails_open_on_unparseable_owl() -> None:
    # Gate-computation error must NOT block the load (the hardened parse already ran).
    assert_label_coverage(b"not xml at all", 99.0, "canon")


def test_spec_gate_wiring() -> None:
    # FOLIO opts out (gate skipped); Canon opts in at 99%.
    assert FOLIO_SPEC.min_label_coverage is None
    assert CANON_SPEC.min_label_coverage == 99.0
