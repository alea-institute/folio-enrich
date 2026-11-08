"""Class-link remapping after replay, without loading an ontology."""

import pytest

from app.models.annotation import (
    Annotation, ConceptMatch, Individual, IndividualClassLink, Span,
)
from app.models.job import Job
from scripts import replay_fix_demos


def annotation(annotation_id, start, end, iri, branches=None):
    return Annotation(
        id=annotation_id,
        span=Span(start=start, end=end, text="class"),
        concepts=[ConceptMatch(
            concept_text="class", folio_iri=iri, folio_label=iri,
            branches=branches or [],
        )],
    )


def remap(links, replacements, old_annotations=None):
    job = Job()
    job.result.annotations = replacements
    job.result.individuals = [Individual(
        name="Example", mention_text="Example",
        span=Span(start=0, end=7, text="Example"), class_links=links,
    )]
    if old_annotations is None:
        old_annotations = {"old": annotation("old", 10, 15, "urn:old")}
    replay_fix_demos._remap_class_link_annotation_ids(job, old_annotations)
    return job.result.individuals[0].class_links


@pytest.mark.parametrize(
    "replacements, expected_id, expected_iri, expected_branch",
    [
        # Prefer the matching top IRI among annotations with the original span.
        ([annotation("other", 10, 15, "urn:other"),
          annotation("exact", 10, 15, "urn:resolved")],
         "exact", "urn:resolved", ""),
        # A changed same-span top concept wins over the old IRI elsewhere.
        ([annotation("elsewhere", 20, 25, "urn:resolved"),
          annotation("same-span", 10, 15, "urn:new", ["Place", "Other"])],
         "same-span", "urn:new", "Place"),
        # With no same-span match, use the closest start among top IRI matches.
        ([annotation("far", 40, 45, "urn:resolved"),
          annotation("near", 12, 17, "urn:resolved")],
         "near", "urn:resolved", ""),
    ],
    ids=["span-and-iri", "changed-top-concept", "nearest-iri"],
)
def test_replay_class_links_rederive_top_concept(
    replacements, expected_id, expected_iri, expected_branch,
):
    link = IndividualClassLink(
        annotation_id="old", folio_iri="urn:resolved", folio_label="Stale",
        branch="Language", confidence=0.8, relationship="instance_of",
    )
    links = remap([link], replacements)
    assert len(links) == 1
    assert links[0].annotation_id == expected_id
    assert links[0].folio_iri == expected_iri
    assert links[0].folio_label == expected_iri
    assert links[0].branch == expected_branch
    assert links[0].confidence == 0.8
    assert links[0].relationship == "instance_of"


@pytest.mark.parametrize("replacement_kind", ["gone", "empty", "backup", "missing-old"])
def test_replay_drops_links_without_surviving_annotation(replacement_kind):
    replacement = annotation("new", 20, 25, "urn:other")
    old_annotations = None
    if replacement_kind == "empty":
        replacement.span = Span(start=10, end=15, text="class")
        replacement.concepts = []
    elif replacement_kind == "backup":
        replacement.concepts.append(ConceptMatch(concept_text="old", folio_iri="urn:old"))
    elif replacement_kind == "missing-old":
        old_annotations = {}
    links = remap(
        [IndividualClassLink(annotation_id="old", folio_iri="urn:old")],
        [replacement], old_annotations,
    )
    assert links == []


@pytest.mark.parametrize("iri", [None, "urn:label-only"])
def test_label_only_links_are_untouched(iri):
    link = IndividualClassLink(
        folio_iri=iri, folio_label="Label", branch="Branch", confidence=0.7,
    )
    before = link.model_dump()
    links = remap([link], [])
    assert len(links) == 1
    assert links[0].model_dump() == before


def test_duplicate_iris_collapse_after_rederivation():
    links = remap(
        [IndividualClassLink(annotation_id="old", folio_iri="urn:old"),
         IndividualClassLink(annotation_id="second", folio_iri="urn:other"),
         IndividualClassLink(folio_iri="urn:new", folio_label="New")],
        [annotation("new", 10, 15, "urn:new")],
        {"old": annotation("old", 10, 15, "urn:old"),
         "second": annotation("second", 10, 15, "urn:other")},
    )
    assert len(links) == 1
    assert links[0].folio_iri == "urn:new"
    assert links[0].annotation_id == "new"


def test_distinct_unresolved_label_links_are_kept():
    links = remap(
        [IndividualClassLink(folio_label="First"), IndividualClassLink(folio_label="Second")],
        [],
    )
    assert [link.folio_label for link in links] == ["First", "Second"]


@pytest.mark.parametrize("field, value", [
    ("folio_iri", "urn:new"),
    ("folio_label", "New label"),
    ("branch", "New branch"),
    ("relationship", "has_role"),
])
def test_concept_summary_detects_class_link_only_change(field, value):
    job = Job()
    job.result.annotations = [annotation("class", 10, 15, "urn:old")]
    link = IndividualClassLink(
        folio_iri="urn:old", folio_label="Old label", branch="Old branch",
    )
    job.result.individuals = [Individual(
        name="Example", mention_text="Example",
        span=Span(start=0, end=7, text="Example"), class_links=[link],
    )]
    before = replay_fix_demos._concept_summary(job)
    setattr(job.result.individuals[0].class_links[0], field, value)
    after = replay_fix_demos._concept_summary(job)

    assert before["annotation_keys"] == after["annotation_keys"]
    assert before["class_links"] == (
        ("Example", 0, "urn:old", "Old label", "Old branch", "instance_of"),
    )
    assert before["class_links"] != after["class_links"]
