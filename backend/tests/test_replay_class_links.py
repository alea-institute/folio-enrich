"""Class-link remapping after replay, without loading an ontology."""

import pytest

from app.models.annotation import (
    Annotation, ConceptMatch, Individual, IndividualClassLink, Span,
)
from app.models.job import Job
from scripts import replay_fix_demos


def annotation(annotation_id, start, end, iri):
    return Annotation(
        id=annotation_id,
        span=Span(start=start, end=end, text="class"),
        concepts=[ConceptMatch(concept_text="class", folio_iri=iri)],
    )


@pytest.mark.parametrize(
    "replacements, expected_id",
    [
        # Prefer the matching IRI among annotations with the original span.
        ([annotation("other", 10, 15, "urn:other"),
          annotation("exact", 10, 15, "urn:resolved")], "exact"),
        # A same-span annotation wins over an IRI match elsewhere.
        ([annotation("elsewhere", 20, 25, "urn:resolved"),
          annotation("same-span", 10, 15, "urn:other")], "same-span"),
        # With no same-span match, use the closest start among IRI matches.
        ([annotation("far", 40, 45, "urn:resolved"),
          annotation("near", 12, 17, "urn:resolved")], "near"),
        # No surviving span or concept: clear the stale ID.
        ([annotation("unrelated", 20, 25, "urn:other")], None),
    ],
    ids=["span-and-iri", "span-only", "nearest-iri", "no-match"],
)
def test_replay_class_links_resolve_to_new_annotation_ids(replacements, expected_id):
    job = Job()
    old = annotation("old", 10, 15, "urn:old")
    job.result.annotations = [old]
    job.result.individuals = [Individual(
        name="Example", mention_text="Example",
        span=Span(start=0, end=7, text="Example"),
        class_links=[
            IndividualClassLink(annotation_id="old", folio_iri="urn:resolved"),
            IndividualClassLink(folio_iri="urn:resolved"),
        ],
    )]
    old_annotations = {a.id: a.model_copy(deep=True) for a in job.result.annotations}
    job.result.annotations = replacements

    replay_fix_demos._remap_class_link_annotation_ids(job, old_annotations)

    links = job.result.individuals[0].class_links
    assert links[0].annotation_id == expected_id
    assert links[1].annotation_id is None
