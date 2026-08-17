"""Dependency-based, zero-LLM proposition candidate extraction."""

from __future__ import annotations

import re

from folio_propositions import ActorRef, AdjudicatorRef, CitationEdge, Proposition

from app.models.job import Job
from app.services.nlp.spacy_singleton import get_spacy_nlp
from app.services.proposition.lexicon import (
    ARGUENDO_FRAME,
    ARGUENDO_MARKERS,
    REPORTING_VERBS,
    PropositionFrame,
)
from app.services.proposition.identity import proposition_id


_PARTY_ROLES = (
    "plaintiff", "defendant", "appellant", "appellee", "petitioner", "respondent"
)
_COURT_SUBJECTS = {"we", "court", "panel", "judge", "justice"}
_COMPLEMENT_DEPS = {"ccomp", "xcomp", "acl"}


class PropositionExtractor:
    def extract(self, job: Job) -> list[Proposition]:
        canonical = job.result.canonical_text
        if canonical is None or not canonical.full_text:
            return []
        text = canonical.full_text
        doc = get_spacy_nlp()(text)
        results: list[Proposition] = []

        for sentence in doc.sents:
            sentence_lower = sentence.text.lower()
            arguendo = next((m for m in ARGUENDO_MARKERS if m in sentence_lower), None)
            emitted_arguendo = False
            for token in sentence:
                lemma = token.lemma_.lower()
                frame = REPORTING_VERBS.get(lemma)
                if frame is None:
                    continue
                complement = next(
                    (child for child in token.children if child.dep_ in _COMPLEMENT_DEPS),
                    None,
                )
                if complement is None:
                    continue
                active_frame = ARGUENDO_FRAME if arguendo and lemma == "assume" else frame
                if active_frame is ARGUENDO_FRAME:
                    emitted_arguendo = True
                start, end, content = self._content_span(complement, text)
                if not content:
                    continue
                role = self._subject_role(token, active_frame.asserter_role)
                results.append(
                    self._build(job, sentence, start, end, content, active_frame, role)
                )

            # "Even if" often has no reporting verb; treat its subordinate clause
            # as the assumed content while staying conservative to that exact marker.
            if arguendo and not emitted_arguendo and arguendo == "even if":
                marker_at = sentence_lower.find(arguendo)
                start = sentence.start_char + marker_at + len(arguendo)
                end = sentence.end_char
                start, end, content = self._trim_span(text, start, end)
                if content:
                    results.append(
                        self._build(job, sentence, start, end, content, ARGUENDO_FRAME, "court")
                    )

        unique: dict[tuple[int | None, int | None, str], Proposition] = {}
        for proposition in results:
            unique[(proposition.start_char, proposition.end_char, proposition.proposition_type)] = proposition
        return sorted(unique.values(), key=lambda p: (p.start_char or 0, p.end_char or 0))

    @staticmethod
    def _content_span(root, text: str) -> tuple[int, int, str]:
        tokens = sorted(root.subtree, key=lambda item: item.i)
        start = tokens[0].idx
        end = tokens[-1].idx + len(tokens[-1].text)
        return PropositionExtractor._trim_span(text, start, end)

    @staticmethod
    def _trim_span(text: str, start: int, end: int) -> tuple[int, int, str]:
        while start < end and text[start].isspace():
            start += 1
        leading_that = re.match(r"that\s+", text[start:end], flags=re.IGNORECASE)
        if leading_that:
            start += leading_that.end()
        while end > start and (text[end - 1].isspace() or text[end - 1] in ".,;:"):
            end -= 1
        return start, end, text[start:end]

    @staticmethod
    def _subject_role(verb, fallback: str) -> str:
        subjects = [child for child in verb.children if child.dep_ in {"nsubj", "nsubjpass"}]
        subject_words = {
            token.lemma_.lower()
            for subject in subjects
            for token in subject.subtree
        }
        for role in _PARTY_ROLES:
            if role in subject_words:
                return role
        if subject_words & _COURT_SUBJECTS:
            return "court"
        return fallback

    def _build(
        self, job: Job, sentence, start: int, end: int, content: str,
        frame: PropositionFrame, role: str,
    ) -> Proposition:
        identity = proposition_id(job.id, start, end)
        validator = (
            AdjudicatorRef(role="court", mode=frame.validator_mode)
            if frame.validator_mode else None
        )
        edges: list[CitationEdge] = []
        sentence_lower = sentence.text.lower()
        for individual in job.result.individuals:
            mention = individual.mention_text.strip()
            if mention and mention.lower() in sentence_lower:
                edges.append(CitationEdge(
                    edge_type="cites",
                    authority_individual_id=individual.id,
                    authority_text=mention,
                ))
        return Proposition(
            id=identity,
            start_char=start,
            end_char=end,
            text=content,
            proposition_type=frame.proposition_type,
            asserter=ActorRef(
                role=role,
                assumed=frame is ARGUENDO_FRAME,
            ),
            validator=validator,
            disposition=frame.disposition,
            citation_edges=edges,
        )
