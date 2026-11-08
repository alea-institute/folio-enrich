"""Court opinion precision regressions, exercised against cached real FOLIO."""
import pytest

from app.services.folio.folio_service import FolioService
from app.services.folio.resolver import ConceptResolver


@pytest.fixture(scope="module")
def folio():
    return FolioService.get_instance("folio")


@pytest.fixture
def resolver(folio):
    return ConceptResolver(folio)


def test_exact_alternative_labels_pass_place_gate(resolver):
    for text, label in [
        ("COURT OF APPEALS FOR THE SEVENTH CIRCUIT", "U.S. Ct. App. - 7th Circuit"),
        ("Central District of Illinois", "U.S. District Court - C.D. Illinois"),
    ]:
        matches = resolver._library_resolve_all(text, "")
        assert matches and matches[0][0].preferred_label == label


@pytest.mark.parametrize("text,label", [
    ("UNITED STATES COURT OF APPEALS FOR THE SEVENTH CIRCUIT", "U.S. Ct. App. - 7th Circuit"),
    ("Seventh Circuit", "U.S. Ct. App. - 7th Circuit"),
    ("the 7th Cir.", "U.S. Ct. App. - 7th Circuit"),
    ("United States District Court for the Central District of Illinois", "U.S. District Court - C.D. Illinois"),
    ("United States District Court for the Eastern District of Louisiana", "U.S. District Court - E.D. Louisiana."),
])
def test_federal_canonical_resolution(resolver, text, label):
    result = resolver.resolve(text)
    assert result and result.folio_concept.preferred_label == label
    assert result.confidence == 1.0
    assert resolver.resolve_multi(text)[0].folio_concept.iri == result.folio_concept.iri


def test_generic_court_has_no_invented_jurisdiction(resolver):
    assert resolver.resolve("district court") is None
    assert resolver.resolve_multi("district court") == []


@pytest.mark.parametrize("text", ["Monell v. Department of Social Services", "Graham v. Connor"])
def test_case_caption_exact_only(resolver, text):
    assert resolver.resolve(text) is None
    assert resolver.resolve_multi(text) == []


def test_fallback_floor(resolver):
    assert resolver.resolve("domestic disturbance call") is None
    assert resolver.resolve_multi("domestic disturbance call") == []


def test_excessive_force_kept(resolver):
    result = resolver.resolve("excessive force")
    assert result and result.folio_concept.preferred_label == "Excessive Force Claim"


def test_canonical_court_keys():
    from app.services.folio.court_names import canonical_court_keys
    for ordinal, numeric in [("first", "1st"), ("eleventh", "11th"), ("d.c.", "D.C."), ("federal", "Federal")]:
        keys = canonical_court_keys(f"The United States Court of Appeals for the {ordinal} Circuit")
        assert f"court of appeals for the {ordinal} circuit" in keys
        assert f"u.s. ct. app. - {numeric.lower()} circuit" in keys
    assert "u.s. district court - c.d. illinois" in canonical_court_keys("US District Court for the Central District of Illinois")
    assert "district court, d. alaska" in canonical_court_keys("U.S. District Court for the District of Alaska")
    assert "u.s. bankruptcy court - e.d. louisiana" in canonical_court_keys("United States Bankruptcy Court for the Eastern District of Louisiana")
    assert "u.s. bankruptcy court - d. alaska" in canonical_court_keys("Bankruptcy Court for the District of Alaska")


def test_jurisdiction_mismatch():
    from app.services.folio.court_names import jurisdiction_mismatch
    assert jurisdiction_mismatch("district court", "Texas District Court")
    assert jurisdiction_mismatch("district court", "Massachusetts District Court")
    assert jurisdiction_mismatch("court", "U.S. District Court")
    assert jurisdiction_mismatch("court", "Cook County Circuit Court")
    assert jurisdiction_mismatch("court", "D.C. Court of Appeals")
    assert not jurisdiction_mismatch("Texas district court", "Texas District Court")
    assert jurisdiction_mismatch("Texastown court", "Texas District Court")
    assert not jurisdiction_mismatch("court", "Court")
    assert not jurisdiction_mismatch("contract", "Texas Contract")


@pytest.mark.parametrize("query,label", [
    ("United States District Court for Illinois", "U.S. District Court - Illinois"),
    ("U.S. District Court for Illinois", "United States District Court - Illinois"),
    ("District of Columbia Court of Appeals", "D.C. Court of Appeals"),
    ("D.C. Court of Appeals", "District of Columbia Court of Appeals"),
])
def test_jurisdiction_aliases_are_equivalent(query, label):
    from app.services.folio.court_names import jurisdiction_mismatch
    assert not jurisdiction_mismatch(query, label)


@pytest.mark.parametrize("query,label", [
    ("court", "United States District Court"),
    ("court", "District of Columbia Court of Appeals"),
    ("US District Court", "U.S. District Court"),
    ("Federal District Court", "United States District Court"),
    ("United States District Court", "Federal District Court"),
    ("United States District Court for Texas", "U.S. District Court - Illinois"),
])
def test_jurisdiction_aliases_preserve_veto(query, label):
    from app.services.folio.court_names import jurisdiction_mismatch
    assert jurisdiction_mismatch(query, label)


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["llm", "reconciled"])
@pytest.mark.parametrize("specifics,expected", [
    (["U.S. District Court - C.D. Illinois"], True),
    ([], False),
    (["U.S. District Court - C.D. Illinois", "U.S. District Court - E.D. Louisiana."], False),
])
async def test_document_court_coreference(folio, source, specifics, expected):
    from app.models.job import Job
    from app.pipeline.stages.resolution_stage import ResolutionStage
    job = Job()
    concepts = [{"concept_text": "district court", "source": source}]
    concepts += [{"concept_text": label, "source": source} for label in specifics]
    job.result.metadata[f"{source}_concepts"] = concepts if source == "reconciled" else {"0": concepts}
    await ResolutionStage(ConceptResolver(folio)).execute(job)
    generic = [c for c in job.result.metadata["resolved_concepts"] if c["concept_text"] == "district court"]
    assert bool(generic) == expected
    if expected:
        assert generic[0]["folio_label"] == specifics[0]
        assert generic[0]["source"] == source
        assert generic[0]["_lineage_events"][-1]["action"] == "coreference"


@pytest.mark.asyncio
async def test_coreference_does_not_leak_across_jobs(folio):
    from app.models.job import Job
    from app.pipeline.stages.resolution_stage import ResolutionStage
    stage = ResolutionStage(ConceptResolver(folio))
    first = Job()
    first.result.metadata["llm_concepts"] = {"0": [
        {"concept_text": "district court"},
        {"concept_text": "U.S. District Court - C.D. Illinois"},
    ]}
    await stage.execute(first)
    assert len(first.result.metadata["resolved_concepts"]) == 2
    second = Job()
    second.result.metadata["llm_concepts"] = {"0": [{"concept_text": "district court"}]}
    await stage.execute(second)
    assert second.result.metadata["resolved_concepts"] == []


@pytest.mark.parametrize("text,branches,forbidden", [
    ("Florida", ["Location"], "Department of Uruguay"),
    ("Georgia", ["Location"], "Asian Country"),
    ("District", [], "Prosecutor"),
    ("LA", [], "Lao People's Democratic Republic"),
])
def test_single_word_homonym_alias_stays_gated(resolver, text, branches, forbidden):
    result = resolver.resolve(text, branches)
    assert result is None or forbidden.casefold() not in result.folio_concept.preferred_label.casefold()


@pytest.mark.parametrize("text,label", [
    ("S.D. Fla.", "U.S. District Court - S.D. Florida"),
    ("S.D.N.Y.", "U.S. District Court - S.D. New York"),
    ("E.D. La.", "U.S. District Court - E.D. Louisiana."),
])
def test_bluebook_court_resolution(resolver, text, label):
    result = resolver.resolve(text)
    assert result and result.folio_concept.preferred_label == label
    assert result.confidence == 1.0
    assert resolver.resolve_multi(text)[0].folio_concept.iri == result.folio_concept.iri


@pytest.mark.parametrize("preferred,aliases,query,exempt", [
    (["Florida"], [], "Florida", True),
    (["Court", "Seventh Circuit"], [], "SEVENTH CIRCUIT", True),
    (["Other"], ["Florida"], "Florida", False),
    (["Other"], ["LA"], "LA", False),
    (["Other"], ["District"], "District", False),
    (["Other"], ["Central District of Illinois"], "Central  District of Illinois", True),
    (["Other"], ["The District"], "The District", True),
])
def test_gate_label_eligibility(preferred, aliases, query, exempt):
    from app.services.folio.court_names import exact_label
    assert exact_label(query, preferred, aliases) == exempt


@pytest.mark.parametrize("text,key", [
    ("N.D. Ill.", "n.d. illinois"),
    ("C.D. Cal.", "c.d. california"),
    ("D. Mass.", "d. massachusetts"),
    ("W.D. Wash.", "w.d. washington"),
    ("D.N.J.", "d. new jersey"),
    ("D. N.D.", "d. north dakota"),
    ("D. S.D.", "d. south dakota"),
    ("D. D.C.", "d. district of columbia"),
    ("D. P.R.", "d. puerto rico"),
    ("S.D. W. Va.", "s.d. west virginia"),
])
def test_bluebook_district_keys(text, key):
    from app.services.folio.court_names import canonical_court_keys
    assert f"u.s. district court - {key}" in canonical_court_keys(text)
    assert f"u.s. bankruptcy court - {key}" in canonical_court_keys(text + " Bankr.")


def test_nonexistent_bluebook_court_not_exactly_resolved(resolver):
    assert resolver._exact_court_or_caption("N.D. Haw.") is None


@pytest.mark.parametrize("skos,alias,expected", [
    ("", "Tribunal", True),
    ("Tribunal", "", False),
    ("", "The Tribunal", False),
])
def test_jurisdiction_veto_uses_label_eligibility(skos, alias, expected):
    from app.services.folio.folio_service import FOLIOConcept
    concept = FOLIOConcept(
        iri="test", preferred_label="Texas Court", folio_pref_label=skos,
        alternative_labels=[alias], definition="", branch="", parent_iris=[],
    )
    assert ConceptResolver._jurisdiction_veto(skos or alias, concept) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["ruler", "reconciled"])
@pytest.mark.parametrize("members,expected", [
    ([("Florida", "Florida", "Location", "state"),
      ("FLORIDA", "Florida (Department of Uruguay)", "Location", "department")], ["state"]),
    ([("New  York", " new\tYORK ", "Location", "state"),
      ("new  york", "New York (Other)", "Location", "other")], ["state"]),
    ([("Florida", "Florida", "Location", "state"),
      ("Florida", "Florida (Other)", "Governmental Body", "body")], ["state", "body"]),
    ([("Florida", "Florida (One)", "Location", "one"),
      ("Florida", "Florida (Two)", "Location", "two")], ["one", "two"]),
    ([("Florida", "Florida", "Location", "one"),
      ("Florida", "FLORIDA", "Location", "two"),
      ("Florida", "Florida (Other)", "Location", "other")], ["one", "two", "other"]),
    ([("Florida", "Florida", "Location", "same"),
      ("Florida", "Florida (Other)", "Location", "same")], ["same", "same"]),
], ids=["exact-label", "normalized-label", "different-branches", "no-exact-label",
        "multiple-exact-labels", "single-iri"])
async def test_same_branch_homonym_tiebreak(monkeypatch, source, members, expected):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.models.job import Job
    from app.pipeline.stages.resolution_stage import ResolutionStage
    from app.services.folio.folio_service import FOLIOConcept
    from app.services.folio.resolver import ResolvedConcept

    service = SimpleNamespace(ontology_id="folio")
    monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)
    stub = MagicMock()
    stub.folio = service
    stub.resolve.side_effect = [
        ResolvedConcept(
            concept_text=text,
            folio_concept=FOLIOConcept(
                iri=iri, preferred_label=label, alternative_labels=[],
                definition="", branch=branch, parent_iris=[],
            ),
            confidence=1.0, branches=[branch], source="entity_ruler",
        )
        for text, label, branch, iri in members
    ]
    stub.resolve_multi.return_value = []
    job = Job()
    job.result.metadata[f"{source}_concepts"] = [
        {"concept_text": text, "branches": [branch], "folio_iri": iri}
        for text, _, branch, iri in members
    ]

    await ResolutionStage(stub).execute(job)

    resolved = job.result.metadata["resolved_concepts"]
    assert [c["folio_iri"] for c in resolved] == expected
    dropped = len(members) - len(expected)
    assert f"dropped {dropped} same-branch homonyms" in job.result.metadata["activity_log"][-1]["msg"]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["ruler", "reconciled"])
async def test_same_branch_homonym_tiebreak_keeps_duplicate_exact_iri(monkeypatch, source):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.models.job import Job
    from app.pipeline.stages.resolution_stage import ResolutionStage
    from app.services.folio.folio_service import FOLIOConcept
    from app.services.folio.resolver import ResolvedConcept

    members = [
        ("Florida", "state"),
        ("Florida (Department of Uruguay)", "department"),
        ("Florida", "state"),
        ("Florida (Other label)", "state"),
    ]
    service = SimpleNamespace(ontology_id="folio")
    monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)
    stub = MagicMock()
    stub.folio = service
    stub.resolve.side_effect = [
        ResolvedConcept(
            concept_text="Florida",
            folio_concept=FOLIOConcept(
                iri=iri, preferred_label=label, alternative_labels=[],
                definition="", branch="Location", parent_iris=[],
            ),
            confidence=1.0, branches=["Location"], source="entity_ruler",
        )
        for label, iri in members
    ]
    stub.resolve_multi.return_value = []
    job = Job()
    job.result.metadata[f"{source}_concepts"] = [
        {"concept_text": "Florida", "branches": ["Location"], "folio_iri": iri}
        for _, iri in members
    ]

    await ResolutionStage(stub).execute(job)

    resolved = job.result.metadata["resolved_concepts"]
    assert [c["folio_iri"] for c in resolved] == ["state", "state", "state"]
    assert [c["folio_label"] for c in resolved] == [
        "Florida", "Florida", "Florida (Other label)",
    ]
    assert "dropped 1 same-branch homonyms" in job.result.metadata["activity_log"][-1]["msg"]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["ruler", "reconciled"])
@pytest.mark.parametrize("text", ["distribution agreement", "  DISTRIBUTION\t Agreement  "])
@pytest.mark.parametrize("lookup_missing", [False, True])
async def test_same_branch_homonym_tiebreak_uses_skos_preferred_label(
    monkeypatch, source, text, lookup_missing,
):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.models.job import Job
    from app.pipeline.stages.resolution_stage import ResolutionStage
    from app.services.folio.folio_service import FOLIOConcept
    from app.services.folio.resolver import ResolvedConcept

    concepts = [
        FOLIOConcept(
            iri="distributor", preferred_label="Distributor Agreement",
            folio_pref_label="Distribution Agreement", alternative_labels=[],
            definition="", branch="Document Artifact", parent_iris=[],
        ),
        FOLIOConcept(
            iri="placement", preferred_label="Placement Agent Agreement",
            alternative_labels=["Distribution Agreement"],
            definition="", branch="Document Artifact", parent_iris=[],
        ),
    ]
    by_iri = {} if lookup_missing else {c.iri: c for c in concepts}
    service = SimpleNamespace(ontology_id="folio", get_concept=by_iri.get)
    monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)
    stub = MagicMock()
    stub.folio = service
    stub.resolve.side_effect = [
        ResolvedConcept(
            concept_text=text, folio_concept=concept, confidence=1.0,
            branches=[concept.branch], source="entity_ruler",
        )
        for concept in concepts
    ]
    stub.resolve_multi.return_value = []
    job = Job()
    job.result.metadata[f"{source}_concepts"] = [
        {"concept_text": text, "branches": [c.branch], "folio_iri": c.iri}
        for c in concepts
    ]

    await ResolutionStage(stub).execute(job)

    resolved = job.result.metadata["resolved_concepts"]
    expected = ["distributor", "placement"] if lookup_missing else ["distributor"]
    assert [c["folio_iri"] for c in resolved] == expected
    assert resolved[0]["folio_label"] == "Distributor Agreement"
    dropped = len(concepts) - len(expected)
    assert f"dropped {dropped} same-branch homonyms" in job.result.metadata["activity_log"][-1]["msg"]


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["ruler", "reconciled"])
@pytest.mark.parametrize("text,iris,labels,skos_labels,stub_skos", [
    (
        "Florida",
        ["R2909d38D76fc77Adea35e7b", "RDD1970019575A7Ed5cA8b06"],
        ["Florida", "Florida (Department of Uruguay)"],
        ["", "Florida"], False,
    ),
    (
        "economic damages",
        ["RouKBMqFNMZxi21EPh6JJ6", "R8f7kbL1Ep39TZSZDDl8rg"],
        ["Economic Damages", "Compensatory Damages"],
        ["Consequential Damages", ""], False,
    ),
    (
        "economic damages",
        ["RouKBMqFNMZxi21EPh6JJ6", "R8f7kbL1Ep39TZSZDDl8rg"],
        ["Economic Damages", "Compensatory Damages"],
        ["Consequential Damages", ""], True,
    ),
    (
        "distribution agreement",
        ["RxvDJ1zl0ikIMMjfefcuyp", "R0C588aozYVJs38c1QJXf5"],
        ["Distributor Agreement", "Placement Agent Agreement"],
        ["Distribution Agreement", "Placement Agreement"], False,
    ),
], ids=["florida", "economic-damages", "economic-damages-skos-stub", "distribution"])
async def test_same_branch_homonym_tiebreak_prefers_rdfs_before_skos(
    monkeypatch, folio, source, text, iris, labels, skos_labels, stub_skos,
):
    from dataclasses import replace
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.models.job import Job
    from app.pipeline.stages.resolution_stage import ResolutionStage
    from app.services.folio.resolver import ResolvedConcept

    concepts = [folio.get_concept(f"https://folio.openlegalstandard.org/{iri}") for iri in iris]
    assert all(concepts)
    assert [c.preferred_label for c in concepts] == labels
    assert [c.folio_pref_label for c in concepts] == skos_labels
    assert concepts[0].branch == concepts[1].branch
    if text == "economic damages":
        # The cached ontology has this as an altLabel, not a skos:prefLabel.
        assert "Economic Damages" in concepts[1].alternative_labels
    if stub_skos:
        concepts[1] = replace(concepts[1], folio_pref_label="Economic Damages")
        by_iri = {c.iri: c for c in concepts}
        service = SimpleNamespace(ontology_id="folio", get_concept=by_iri.get)
        monkeypatch.setattr(FolioService, "get_instance", lambda *_: service)

    stub = MagicMock()
    stub.folio = folio
    stub.resolve.side_effect = [
        ResolvedConcept(
            concept_text=text, folio_concept=c, confidence=1.0,
            branches=[c.branch], source="entity_ruler",
        )
        for c in concepts
    ]
    stub.resolve_multi.return_value = []
    job = Job()
    job.result.metadata[f"{source}_concepts"] = [
        {"concept_text": text, "branches": [c.branch], "folio_iri": c.iri}
        for c in concepts
    ]

    await ResolutionStage(stub).execute(job)

    resolved = job.result.metadata["resolved_concepts"]
    assert [c["folio_iri"] for c in resolved] == [concepts[0].iri]
    assert "dropped 1 same-branch homonyms" in job.result.metadata["activity_log"][-1]["msg"]
