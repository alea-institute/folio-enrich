"""Dependency-based, zero-LLM proposition candidate extraction."""

from __future__ import annotations

import re

from folio_propositions import ActorRef, AdjudicatorRef, CitationEdge, Proposition

from app.models.job import Job
from app.services.nlp.spacy_singleton import get_spacy_nlp
from app.services.proposition.lexicon import (
    ASSERTION_FRAMES,
    MODAL_LEMMAS,
    QUOTED_AUTHORITY_FRAME,
    QUOTED_COURT_FRAME,
    ARGUENDO_FRAME,
    ARGUENDO_MARKERS,
    REPORTING_VERBS,
    PropositionFrame,
)
from app.services.proposition.identity import proposition_id
from app.services.proposition.source import job_source_uri, proposition_content_iri


_PARTY_ROLES = (
    "plaintiff", "defendant", "appellant", "appellee", "petitioner", "respondent"
)
_COURT_SUBJECTS = {"we", "court", "panel", "judge", "justice"}
_COMPLEMENT_DEPS = {"ccomp", "xcomp", "acl"}
_OPINION_HEADING = re.compile(
    r"^([A-Z][A-Z .'-]*),\s*(?:Ch\.\s*)?J\.\s*\(([^)\n]*)\):", re.MULTILINE
)


class PropositionExtractor:
    def extract(self, job: Job) -> list[Proposition]:
        canonical = job.result.canonical_text
        if canonical is None or not canonical.full_text:
            return []
        text = canonical.full_text
        # Resolved once per extraction; every proposition's content IRI shares it.
        source_uri = job_source_uri(job)
        doc = get_spacy_nlp()(text)
        results: list[Proposition] = []

        quote_ranges = self._quote_ranges(text, doc)
        attributed_quotes = set()
        for sentence in doc.sents:
            sentence_lower = sentence.text.lower()
            arguendo = next((m for m in ARGUENDO_MARKERS if m in sentence_lower), None)
            emitted_arguendo = False
            emitted_reporting = False
            for token in sentence:
                lemma = token.lemma_.lower()
                if any(start <= token.idx < end for start, end in quote_ranges):
                    continue
                frame = REPORTING_VERBS.get(lemma)
                if frame is None:
                    continue
                complement = next(
                    (child for child in token.children if child.dep_ in _COMPLEMENT_DEPS),
                    None,
                )
                if complement is None:
                    continue
                # Source-attributed quotes keep their quoted-authority frame;
                # party/court reporting complements retain explicit attribution.
                if frame.asserter_role == "secondary_source" and any(
                    start <= complement.idx < end for start, end in quote_ranges
                ):
                    continue
                active_frame = ARGUENDO_FRAME if arguendo and lemma == "assume" else frame
                if active_frame is ARGUENDO_FRAME:
                    emitted_arguendo = True
                span = self._negation_safe_span(token, self._content_span(complement, text), text)
                if span is None:
                    continue
                start, end, content = span
                if not content:
                    continue
                role = self._subject_role(token, active_frame.asserter_role)
                results.append(
                    self._build(job, sentence, start, end, content, active_frame, role, source_uri)
                )
                emitted_reporting = True
                attributed_quotes.update(
                    (qs, qe) for qs, qe in quote_ranges if qs <= complement.idx < qe
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
                        self._build(job, sentence, start, end, content, ARGUENDO_FRAME, "court", source_uri)
                    )

            # Do not promote attributed complements, questions, or quoted
            # predicates into direct assertions of the opinion's court.
            if not emitted_reporting and not arguendo:
                root = sentence.root
                quoted = any(start <= root.idx < end for start, end in quote_ranges)
                if not quoted and "?" not in sentence.text and root.lemma_ not in REPORTING_VERBS:
                    frame = self._assertion_frame(sentence)
                    if frame:
                        span = self._trim_span(text, sentence.start_char, sentence.end_char)
                        span = self._negation_safe_span(root, span, text)
                        if span and span[2]:
                            results.append(self._build(job, sentence, *span, frame, "court", source_uri))

        for start, end in quote_ranges:
            if (start, end) in attributed_quotes:
                continue
            quoted_tokens = [t for t in doc.char_span(start, end, alignment_mode="expand")
                             if start <= t.idx < end]
            finite = [t for t in quoted_tokens if t.pos_ in {"VERB", "AUX"}
                      and ("Fin" in t.morph.get("VerbForm") or t.tag_ == "MD")]
            if not finite:
                continue
            # Choose the governing quoted predicate (including a finite modal's
            # lexical head) from the existing parse; never parse a quote again.
            predicates = [t.head if t.dep_ in {"aux", "auxpass"} and t.head in quoted_tokens else t
                          for t in finite]
            governor = min(predicates, key=lambda t: len(list(t.ancestors)))
            span = self._negation_safe_span(governor, self._trim_span(text, start, end), text)
            if span is None or not span[2]:
                continue
            frame = QUOTED_AUTHORITY_FRAME if self._authority_anchor(doc, start, end, text) else QUOTED_COURT_FRAME
            results.append(self._build(job, governor.sent, *span, frame, frame.asserter_role, source_uri))

        unique: dict[tuple[int | None, int | None, str], Proposition] = {}
        for proposition in results:
            unique[(proposition.start_char, proposition.end_char, proposition.proposition_type)] = proposition
        return sorted(unique.values(), key=lambda p: (p.start_char or 0, p.end_char or 0))

    @staticmethod
    def _quote_ranges(text, doc):
        # Straight quotes are ambiguous (inches, unclosed quotation). Permit
        # the opening/closing sentences and at most one intervening sentence;
        # never join paragraphs. Reuse the existing parse for this bound.
        sentence_starts = [sentence.start_char for sentence in doc.sents]
        ranges = [(m.start() + 1, m.end() - 1) for m in re.finditer(r'“[^”]+”', text)]
        consumed_until = -1
        # Lookahead lets a rejected pair's closing mark open a later valid pair.
        for match in re.finditer(r'(?=(?<!\d)"([^"]+)")', text):
            start, end = match.span(1)
            if start <= consumed_until:
                continue
            content = text[start:end]
            if not content or re.search(r"\n[ \t\r]*\n", content):
                continue
            if sum(start < boundary < end for boundary in sentence_starts) > 2:
                continue
            ranges.append((start, end))
            consumed_until = end + 1
        return sorted(ranges)

    @staticmethod
    def _authority_anchor(doc, start, end, text):
        # Citation parentheses may span several spaCy sentences because of
        # reporter abbreviations. Follow the adjacent balanced parentheses.
        following = text[end + 1:].lstrip()
        citation = ""
        if following.startswith("("):
            depth = 0
            for index, char in enumerate(following):
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        citation = following[1:index]
                        break
        reporter = re.search(r"\b\d+\s+(?:[A-Z][A-Za-z.]*\s*){1,6}\d+\b", citation)
        judicial_attribution = re.search(r"\bJ\.,\s*in\b", citation)
        treatise = re.search(r"\b(?:Restatement|Treatise|Torts|Negligence|Jurisprudence)\b", citation, re.I)
        if reporter or judicial_attribution or treatise:
            return True
        quote = doc.char_span(start, end, alignment_mode="expand")
        before = [t for t in quote[0].sent if t.idx < start]
        return any(t.lemma_ in {"say", "state", "explain", "write"} for t in before) or any(
            t.lower_ in {"restatement", "treatise"} for t in before
        )

    @staticmethod
    def _assertion_frame(sentence):
        root = sentence.root
        children = list(root.children)
        subjects = [t for t in children if t.dep_ in {"nsubj", "nsubjpass", "csubj"}]
        modals = {t.lemma_ for t in children if t.dep_ == "aux"} & MODAL_LEMMAS
        existential = any(t.dep_ == "expl" and t.lower_ == "there" for t in children)
        if existential and "must" in modals and root.lemma_ == "be":
            return ASSERTION_FRAMES["existential-obligation"]
        one_who = any(
            subject.lower_ in {"one", "anyone", "whoever"}
            and any(t.dep_ == "relcl" for t in subject.children)
            for subject in subjects
        )
        conditions = [t for t in sentence if t.dep_ in {"advcl", "ccomp"}
                      and any(c.dep_ == "mark" and c.lower_ in {"if", "where"} for c in t.children)]
        # General subjects are common nouns or anaphoric pronouns, not named
        # people. Require the condition itself to have a general subject too.
        general_condition = any(
            any(c.dep_ in {"nsubj", "nsubjpass", "expl"} and c.pos_ != "PROPN" for c in condition.children)
            for condition in conditions
        )
        if one_who or (general_condition and (existential or any(t.pos_ != "PROPN" for t in subjects))):
            return ASSERTION_FRAMES["generic-rule"]
        predicates = [root] + [t for t in children if t.dep_ == "conj"]
        for predicate in predicates:
            attrs = [t for t in predicate.children if t.dep_ in {"attr", "acomp"}]
            if (
                any(t.dep_ == "aux" and t.lemma_ in MODAL_LEMMAS for t in predicate.children)
                or (predicate.lemma_ == "be" and any(t.lemma_ == "liable" for t in attrs))
                or (predicate.lemma_ == "bind" and any(t.dep_ == "xcomp" for t in predicate.children))
                or (predicate.lemma_ == "owe" and any(t.dep_ == "dobj" and t.lemma_ == "duty" for t in predicate.children))
            ):
                return ASSERTION_FRAMES["modal-deontic"]
        if root.lemma_ == "be" and subjects and any(t.pos_ != "PRON" for t in subjects):
            if any(t.dep_ in {"attr", "acomp", "xcomp"} for t in children):
                return ASSERTION_FRAMES["copular-definition"]
        if any(t.lemma_ == "define" and any(c.dep_ in {"nsubj", "nsubjpass"} for c in t.children)
               for t in predicates + [t for t in children if t.dep_ == "ccomp"]):
            return ASSERTION_FRAMES["copular-definition"]
        return None

    @staticmethod
    def _clause_negators(root):
        """Negation attached to this predicate or its subject/object, not a
        subordinate assertion with its own polarity.
        """
        negatives = {"no", "never", "nothing", "nobody", "neither", "none"}
        found = []
        for child in root.children:
            if child.dep_ == "neg" or child.lower_ in negatives:
                found.append(child)
            if child.dep_ in {"nsubj", "nsubjpass", "dobj", "obj", "attr"}:
                for token in child.subtree:
                    if token.lower_ not in negatives:
                        continue
                    path = list(token.ancestors)
                    if root in path and not any(
                        ancestor.dep_ in {"ccomp", "xcomp", "acl", "relcl", "advcl"}
                        for ancestor in path[:path.index(root)]
                    ):
                        found.append(token)
        return found

    def _negation_safe_span(self, governor, span, text):
        # Nominal reporting frames ("has no claim that...") belong to the
        # enclosing predicate, including the determiner on its object.
        clause = governor.head if governor.pos_ == "NOUN" else governor
        start, end, _ = span
        for outer in clause.ancestors:
            if self._clause_negators(outer) or outer.lemma_ in {"deny", "dispute", "contest"}:
                # Widen only within the governing clause's own subtree.
                # An outer negation would swallow a separate assertion.
                return None
        negators = self._clause_negators(clause)
        if negators and all(start <= t.idx < end for t in negators):
            return span
        if negators or governor.lemma_ in {"deny", "dispute", "contest"}:
            subtree = list(clause.subtree)
            if any(negator not in subtree for negator in negators):
                return None
            widened = self._content_span(clause, text)
            if widened[0] > start or widened[1] < end:
                return None
            return widened
        return span

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
        heading = _OPINION_HEADING.match(text, start, end)
        if heading:
            start = heading.end()
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
        frame: PropositionFrame, role: str, source_uri: str,
    ) -> Proposition:
        identity = proposition_id(job.id, start, end, frame.proposition_type)
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
        court_name = None
        if role == "court":
            headings = list(_OPINION_HEADING.finditer(job.result.canonical_text.full_text, 0, end))
            if headings and "dissent" in headings[-1][2].lower():
                court_name = f"{headings[-1][1].strip()} (dissenting)"
        proposition = Proposition(
            id=identity,
            start_char=start,
            end_char=end,
            text=content,
            proposition_type=frame.proposition_type,
            asserter=ActorRef(
                role=role,
                name=court_name,
                assumed=frame is ARGUENDO_FRAME,
            ),
            validator=validator,
            disposition=frame.disposition,
            citation_edges=edges,
            content_iri=proposition_content_iri(source_uri, content),
        )
        # Pydantic serializes declared fields only. This diagnostic attribute
        # is visible to the benchmark without changing the shared schema or JSON.
        if frame.pattern_name:
            object.__setattr__(proposition, "pattern_name", frame.pattern_name)
        return proposition
