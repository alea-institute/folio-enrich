"""Court opinion precision regressions."""
import logging
import re
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from app.models.annotation import Annotation, ConceptMatch, Individual, Span
from app.models.document import CanonicalText
from app.models.job import Job
from app.pipeline.stages.entity_ruler_stage import EntityRulerStage
from app.pipeline.stages.string_match_stage import StringMatchStage
from app.services.entity_ruler.ruler import EntityRulerMatch
from app.services.folio.folio_service import FolioService


def test_lemma_keys_preserve_hyphenated_labels():
    # alea opens a home-directory log on import; suppress that test side effect.
    with patch('logging.handlers.RotatingFileHandler', return_value=logging.NullHandler()):
        from folio import FOLIO
        service = FolioService.get_instance('folio')
        with patch.object(FOLIO, 'save_cache'):
            service._get_folio()
    with patch.object(service, '_lemma_map', None), patch.object(service, '_load_lemma_cache', return_value=None), patch.object(service, '_save_lemma_cache'):
        lemmas = service._compute_label_lemmas()
        assert lemmas.get('non-billable', 'non-billable') != 'non'
        assert lemmas.get('call-up', 'call-up') != 'call'
        assert 'civ' not in lemmas.values()
        assert lemmas['agreements'] == 'agreement'
        with patch.object(service, '_labels_multi_cache', None):
            labels = service.get_all_labels_multi()
        assert not {'non', 'call', 'civ'} & labels.keys()
        assert any(x.concept.preferred_label == 'Agreements' for x in labels['agreement'])
        from app.services.nlp.spacy_singleton import get_spacy_tokenizer
        docs = list(get_spacy_tokenizer().pipe(['non-billables', 'call-ups', 'agreements', 'civs']))
        tokenizer = SimpleNamespace(pipe_names=['tagger', 'attribute_ruler'], pipe=lambda *a, **k: docs)
        service._lemma_map = None
        with patch('app.services.nlp.spacy_singleton.get_spacy_tokenizer', return_value=tokenizer):
            compounds = service._compute_label_lemmas()
        assert compounds == {'non-billables': 'non-billable', 'call-ups': 'call-up', 'agreements': 'agreement'}



def test_roman_section_enumerators_are_not_suffixes():
    text = 'III. ANALYSIS\n  IV Heading\nJohn Smith III, Esq.\nSee II) below\nJohn Smith iii'
    matches = [EntityRulerMatch(m.group(), m.start(), m.end(), 'suffix', 'iri:suffix', 'alternative') for m in re.finditer(r'\b(?:III|IV|II|iii)\b', text)]
    stage = EntityRulerStage()
    stage._iri_to_branch = {}
    stage._iri_to_concept = {}
    annotations = stage._build_preliminary_annotations(matches, text)
    expected = [text.index('III, Esq'), text.index('iii')]
    assert [a.span.start for a in annotations] == expected
    with patch.object(stage, '_ensure_patterns_loaded'), patch.object(stage, '_find_matches', return_value=matches):
        filtered, _, concepts, _, annotations = stage._run_deterministic('folio', text)
    assert [m.start_char for m in filtered] == expected
    assert len(concepts) == len(annotations) == 2


def ann(text, surface, *, branch=None, state='confirmed', mt='preferred', source='entity_ruler'):
    start = text.index(surface)
    return Annotation(span=Span(start=start, end=start+len(surface), text=surface), state=state, concepts=[ConceptMatch(concept_text=surface, folio_iri='iri:'+surface, folio_label=surface, branches=[branch] if branch else [], confidence=.8, source=source, match_type=mt)])


async def run(job):
    with patch.object(FolioService, 'get_instance', return_value=SimpleNamespace(get_all_labels=lambda: {})):
        await StringMatchStage().execute(job)


@pytest.mark.asyncio
async def test_fragments_inside_courts_and_case_captions_are_removed():
    text = 'United States District Court; Monell v. Department of Social Services; Other Court; Court'
    job = Job()
    job.result.canonical_text = CanonicalText(full_text=text)
    court = ann(text, 'United States District Court', branch='Governmental Body')
    equal = court.model_copy(deep=True)
    equal.concepts[0].folio_iri = 'iri:equal'
    other = ann(text, 'Other Court', branch='Objectives')
    other_fragment = ann(text, 'Court')
    other_fragment.span.start = text.index('Court', text.index('Other Court'))
    other_fragment.span.end = other_fragment.span.start + 5
    job.result.annotations = [court, ann(text, 'Court'), ann(text, 'Social Services'), equal, other, other_fragment]
    job.result.metadata['resolved_concepts'] = [a.concepts[0].model_dump() for a in job.result.annotations]
    name = 'Monell v. Department of Social Services'
    job.result.individuals = [Individual(name=name, mention_text=name, span=Span(start=text.index(name), end=text.index(name)+len(name), text=name))]
    await run(job)
    assert 'Social Services' not in [a.span.text for a in job.result.annotations]
    assert any(a.concepts[0].folio_iri == 'iri:equal' for a in job.result.annotations)
    assert any(a.span.start == other_fragment.span.start for a in job.result.annotations)
    assert not any(a.span.text == 'Court' and a.span.start < court.span.end for a in job.result.annotations)
    assert any('nested' in e['msg'].lower() and '2' in e['msg'] for e in job.result.metadata['activity_log'])
    assert any(e.action == 'nested_fragments_removed' for e in court.lineage)


@pytest.mark.asyncio
async def test_rejected_single_word_ruler_alternatives_are_dropped():
    text = 'grant claims preferred multi word llm confirmed'
    job = Job()
    job.result.canonical_text = CanonicalText(full_text=text)
    job.result.annotations = [ann(text, 'grant', state='rejected', mt='alternative'), ann(text, 'claims', state='rejected', mt='lemma_alternative'), ann(text, 'preferred', state='rejected'), ann(text, 'multi word', state='rejected', mt='alternative'), ann(text, 'llm', state='rejected', mt='alternative', source='llm'), ann(text, 'confirmed', mt='alternative')]
    job.result.metadata['resolved_concepts'] = [job.result.annotations[-1].concepts[0].model_dump()]
    await run(job)
    assert {a.span.text for a in job.result.annotations} == {'preferred', 'multi word', 'llm', 'confirmed'}
    assert any('rejected' in e['msg'].lower() and '2' in e['msg'] for e in job.result.metadata['activity_log'])
    job.result.metadata['resolved_concepts'] = []
    job.result.annotations = [ann(text, 'grant', state='rejected', mt='alternative')]
    await run(job)
    assert job.result.annotations == []
