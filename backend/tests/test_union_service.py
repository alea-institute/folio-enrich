"""Union behavior through the registry's resident services, using offline graphs."""
import gc
import weakref
from types import SimpleNamespace

import pytest

from app.services.folio.folio_service import FolioService
from app.services.ontology.registry import OntologyRegistry, set_registry
from app.services.ontology.spec import CANON_SPEC, FOLIO_SPEC


class Graph:
    def __init__(self, spec):
        keys = ['shared', 'folio'] if spec.id == 'folio' else ['shared', 'canon']
        self.classes = [SimpleNamespace(iri=spec.base_iri + key, label=key,
                       definition='', sub_class_of=[]) for key in keys]
        self.object_properties = [SimpleNamespace(iri=spec.base_iri + 'prop', label='relates')]
        self.lookups = []

    def __getitem__(self, iri):
        self.lookups.append(iri)
        return next(c for c in self.classes if c.iri == iri)

    def get_parents(self, iri):
        return []

    def get_folio_branches(self):
        return {}

    def search_by_label(self, label, **kw):
        return [(c, 1.0) for c in self.classes if c.label == label]


@pytest.fixture
def union_registry(monkeypatch):
    import app.services.ontology.registry as module
    previous = module._registry
    monkeypatch.setattr(FolioService, '_load_folio', lambda self: Graph(self.spec))
    monkeypatch.setattr(FolioService, '_compute_label_lemmas', lambda self: {})
    monkeypatch.setattr(FolioService, '_build_branch_map', lambda self: None)
    registry = OntologyRegistry({'folio': FOLIO_SPEC, 'canon': CANON_SPEC})
    set_registry(registry)
    yield registry
    set_registry(previous)


def test_union_lookup_and_regions(union_registry):
    service = union_registry.get_service('both')
    canon = service.get_concept('canon')
    assert canon.iri == 'https://ontology.catholicos.catholic/canon'
    assert canon.region == 'canon_only'
    assert union_registry.get_service('canon')._get_folio().lookups[-1] == canon.iri
    shared = service.get_concept('shared')
    assert shared.iri == 'https://folio.openlegalstandard.org/shared'
    assert shared.region == 'shared'
    assert service.get_concept('folio').region == 'folio_only'
    assert service.graph_for_iri(canon.iri) is union_registry.get_service('canon')._get_folio()
    assert service.service_for_iri(canon.iri).spec is CANON_SPEC


def test_union_labels_search_and_properties(union_registry):
    service = union_registry.get_service('both')
    labels = service.get_all_labels_multi()
    assert len(labels['shared']) == 1
    assert labels['shared'][0].concept.iri == 'https://folio.openlegalstandard.org/shared'
    assert labels['canon'][0].concept.region == 'canon_only'
    assert service.get_all_labels()['shared'].concept.region == 'shared'
    matches = service.search_by_label('shared')
    assert len(matches) == 1
    assert matches[0][0].iri == 'https://folio.openlegalstandard.org/shared'
    assert service.get_all_property_labels()['relates'].prop.iri == 'https://folio.openlegalstandard.org/prop'


def test_union_does_not_retain_evicted_resident(union_registry, monkeypatch):
    from app.config import settings
    service = union_registry.get_service('both')
    service.get_concept('canon')
    old = weakref.ref(union_registry.get_service('canon'))
    monkeypatch.setattr(settings, 'max_resident_ontologies', 0)
    union_registry._evict_if_needed()
    gc.collect()
    assert old() is None
    assert service.get_concept('canon').region == 'canon_only'
    gc.collect()
    assert 'canon' not in union_registry._services
