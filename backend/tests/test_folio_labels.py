"""Label provenance regressions using only a tiny in-memory OWL tree."""

from types import SimpleNamespace

from lxml import etree
import pytest

from app.services.folio.labels import norm_label, true_alternative_labels, untagged_alt_labels


@pytest.fixture
def labels_fixture():
    iri = "https://example.org/Claims"
    tree = etree.fromstring(f'''<rdf:RDF
        xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        xmlns:owl="http://www.w3.org/2002/07/owl#"
        xmlns:skos="http://www.w3.org/2004/02/skos/core#">
      <owl:Class rdf:about="{iri}">
        <skos:altLabel>Dependency Claims</skos:altLabel>
        <skos:altLabel xml:lang="en-gb">Dependency Claims</skos:altLabel>
        <skos:altLabel xml:lang="es-mx">Gasto A</skos:altLabel>
        <skos:altLabel xml:lang="es-mx">Gasto B</skos:altLabel>
        <skos:altLabel>Claims Alias</skos:altLabel>
        <skos:hiddenLabel>X1</skos:hiddenLabel>
      </owl:Class>
    </rdf:RDF>''')
    concept = SimpleNamespace(
        iri=iri,
        alternative_labels=["Dependency Claims", "Gasto A", "Gasto B", "Claims Alias", "X1"],
        translations={"en-gb": "Dependency Claims", "es-mx": "Gasto B"},
        hidden_label="X1",
    )
    return SimpleNamespace(tree=tree), concept


def test_tree_keeps_untagged_overlap_and_hidden_label(labels_fixture):
    folio, concept = labels_fixture
    assert untagged_alt_labels(folio) == {concept.iri: {"Dependency Claims", "Claims Alias"}}
    assert true_alternative_labels(folio, concept) == ["Dependency Claims", "Claims Alias", "X1"]
    assert concept.alternative_labels == ["Dependency Claims", "Gasto A", "Gasto B", "Claims Alias", "X1"]


def test_map_is_memoized_per_ontology(labels_fixture):
    folio, _ = labels_fixture
    cached = untagged_alt_labels(folio)
    assert untagged_alt_labels(folio) is cached
    reloaded = SimpleNamespace(tree=folio.tree)
    assert untagged_alt_labels(reloaded) == cached
    assert untagged_alt_labels(reloaded) is not cached


@pytest.mark.parametrize("folio", [SimpleNamespace(), SimpleNamespace(tree=None)])
def test_no_tree_uses_normalized_translation_fallback(folio):
    concept = SimpleNamespace(
        alternative_labels=["Alias", "  GASTO   B ", "X1", "Alias"],
        translations={"es-mx": "Gasto B"}, hidden_label="X1",
    )
    assert untagged_alt_labels(folio) is None
    assert true_alternative_labels(folio, concept) == ["Alias", "X1", "Alias"]
    assert norm_label("  A\t B  ") == "a b"


def test_prompt_also_known_as_uses_true_aliases(labels_fixture, monkeypatch):
    from app.services.folio.folio_service import FolioService
    from app.services.llm.prompts.templates import _build_folio_branch_detail

    folio, concept = labels_fixture
    concept.label = "Claims"
    concept.definition = "A demand for relief."
    folio.get_folio_branches = lambda max_depth: {"SERVICE": [concept]}
    service = SimpleNamespace(_get_folio=lambda: folio)
    monkeypatch.setattr(FolioService, "get_instance", lambda *args: service)

    detail = _build_folio_branch_detail()

    assert "Also known as: Dependency Claims, Claims Alias, X1" in detail
    assert "Gasto" not in detail


def test_legacy_alternative_labels_keep_the_same_order(labels_fixture):
    folio, concept = labels_fixture
    concept.alternative_labels = ["Dependency Claims", "Claims Alias", "X1"]
    assert true_alternative_labels(folio, concept) == concept.alternative_labels
