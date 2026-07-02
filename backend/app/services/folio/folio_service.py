from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.services.folio.branch_config import (
    EXCLUDED_BRANCHES,
    get_branch_color,
    get_branch_display_name,
)
from app.services.folio.match_tier import is_higher_priority, lemma_type_for

logger = logging.getLogger(__name__)

# Bump when the lemma rules or denylist change, so the disk cache (keyed by
# owl_hash + this version) is not served stale after a logic change.
LEMMA_VERSION = "1"
_LEMMA_CACHE_DIR = Path.home() / ".folio-enrich" / "cache" / "lemmas"

# Legal pluralia-tantum / terms of art whose singular has a *different* meaning.
# These must never be lemma-merged (e.g. "damages" = monetary remedy != "damage"
# = harm). Checked against both the original label and the computed lemma so
# neither direction creates a spurious match. Conservative by design.
_LEMMA_DENYLIST: frozenset[str] = frozenset({
    "damages", "damage", "costs", "cost", "proceedings", "proceeding",
    "goods", "good", "arms", "arm", "premises", "savings", "saving",
    "findings", "finding", "securities", "minutes", "minute",
    "holdings", "holding", "pleadings", "pleading", "articles", "article",
    "data", "datum", "leaves", "leave", "wills", "will", "means",
})


def _translation_matching_enabled() -> bool:
    """Check if translation matching is enabled in settings (lazy import to avoid circular deps)."""
    from app.config import settings
    return settings.translation_matching_enabled


@dataclass
class FOLIOConcept:
    iri: str
    preferred_label: str
    alternative_labels: list[str]
    definition: str
    branch: str
    parent_iris: list[str]
    folio_pref_label: str = ""
    examples: list[str] | None = None
    notes: list[str] | None = None
    editorial_note: str = ""
    comment: str = ""
    description: str = ""
    source: str = ""
    see_also: list[str] | None = None
    hidden_label: str = ""
    is_defined_by: str = ""
    deprecated: bool = False
    history_note: str = ""
    country: str = ""
    translations: dict[str, str] | None = None


@dataclass
class LabelInfo:
    """A label entry that tracks whether it's a preferred or alternative label."""
    concept: FOLIOConcept
    label_type: str  # "preferred" or "alternative"
    matched_label: str  # The actual label text that matched


@dataclass
class FOLIOProperty:
    iri: str
    label: str  # raw label from ontology (may have prefix)
    clean_label: str  # label with prefix stripped
    preferred_label: str
    alt_labels: list[str]
    clean_alt_labels: list[str]
    definition: str
    examples: list[str] | None = None
    domain_iris: list[str] | None = None
    range_iris: list[str] | None = None
    inverse_of: str | None = None
    sub_property_of: list[str] | None = None


@dataclass
class PropertyLabelInfo:
    """A property label entry tracking whether it's preferred or alternative."""
    prop: FOLIOProperty
    label_type: str  # "preferred" or "alternative"
    matched_label: str


class FolioService:
    """Singleton wrapper around folio-python for ontology access."""

    _instance: FolioService | None = None

    def __init__(self) -> None:
        self._folio = None
        self._labels_cache: dict[str, LabelInfo] | None = None
        self._labels_multi_cache: dict[str, list[LabelInfo]] | None = None
        self._property_labels_cache: dict[str, PropertyLabelInfo] | None = None
        self._branch_map: dict[str, str] | None = None
        self._lemma_map: dict[str, str] | None = None
        # Cross-request cache of multi-strategy search results, keyed by
        # (concept_text.lower(), branch.lower(), top_n). Results depend only on
        # the query and the loaded ontology, so caching is exact (no precision/
        # recall change) — it just avoids re-running the same label/embedding
        # search for the legal terms that recur across documents. Bounded; cleared
        # on ontology reload.
        self._search_cache: dict[tuple[str, str, int], list] = {}

    @classmethod
    def get_instance(cls) -> FolioService:
        if cls._instance is None:
            cls._instance = FolioService()
        return cls._instance

    def _get_folio(self):
        if self._folio is None:
            from folio import FOLIO

            self._folio = FOLIO(github_repo_branch="main")
            self._build_branch_map()
            logger.info("FOLIO ontology loaded with %d concepts", len(self._folio.classes))
        return self._folio

    def _reload(self) -> dict:
        """Reload FOLIO from updated disk cache. Thread-safe via GIL attribute swap."""
        from folio import FOLIO

        old_count = len(self._folio.classes) if self._folio else 0

        new_folio = FOLIO(github_repo_branch="main")

        # Build new caches from the new FOLIO instance
        old_folio = self._folio
        self._folio = new_folio
        self._branch_map = None
        self._build_branch_map()

        # Rebuild label caches (lemma map re-keys to the new owl_hash on demand)
        self._labels_cache = None
        self._labels_multi_cache = None
        self._property_labels_cache = None
        self._lemma_map = None
        self._search_cache = {}  # stale after an ontology swap
        self.get_all_labels()
        self.get_all_labels_multi()
        self.get_all_property_labels()

        new_count = len(new_folio.classes)
        logger.info(
            "FOLIO ontology reloaded: %d → %d concepts", old_count, new_count
        )
        return {"concepts_before": old_count, "concepts_after": new_count}

    def _build_branch_map(self) -> None:
        """Build a map from concept IRI to branch display name."""
        if self._folio is None:
            return
        self._branch_map = {}
        try:
            branches = self._folio.get_folio_branches()
            for branch_type, concepts in branches.items():
                # Use display name from branch_config when possible
                branch_key = branch_type.name if hasattr(branch_type, "name") else str(branch_type)
                branch_name = get_branch_display_name(branch_key)
                for concept in concepts:
                    if hasattr(concept, "iri"):
                        self._branch_map[concept.iri] = branch_name
        except Exception:
            logger.warning("Failed to build branch map", exc_info=True)

    def get_all_branches(self) -> list[dict]:
        """Get all non-excluded branches with concept counts and colors."""
        folio = self._get_folio()
        branches_dict = folio.get_folio_branches(max_depth=16)

        result: list[dict] = []
        for ft_key, classes in branches_dict.items():
            branch_key = ft_key.name if hasattr(ft_key, "name") else str(ft_key).split(".")[-1]
            display_name = get_branch_display_name(branch_key)
            if display_name in EXCLUDED_BRANCHES:
                continue
            color = get_branch_color(display_name)
            result.append({
                "name": display_name,
                "color": color,
                "concept_count": len(classes),
            })
        result.sort(key=lambda b: b["name"])
        return result

    def _get_branch(self, iri: str, parent_iris: list[str]) -> str:
        """Determine the branch for a concept by checking its IRI and ancestors."""
        if self._branch_map is None:
            return ""
        # Direct lookup
        if iri in self._branch_map:
            return self._branch_map[iri]
        # Check parents
        for parent_iri in parent_iris:
            if parent_iri in self._branch_map:
                return self._branch_map[parent_iri]
        # Walk up the hierarchy
        try:
            folio = self._get_folio()
            parents = folio.get_parents(iri)
            for parent in parents:
                if hasattr(parent, "iri") and parent.iri in self._branch_map:
                    # Cache for future lookups
                    self._branch_map[iri] = self._branch_map[parent.iri]
                    return self._branch_map[parent.iri]
        except Exception:
            pass
        return ""

    def search_by_label(self, label: str, top_k: int = 5) -> list[tuple[FOLIOConcept, float]]:
        folio = self._get_folio()
        try:
            results = folio.search_by_label(label, include_alt_labels=True)
        except Exception:
            logger.warning("search_by_label failed for '%s'", label, exc_info=True)
            return []
        output = []
        for concept, score in results[:top_k]:
            output.append((self._to_folio_concept(concept), score))
        return output

    def search_by_prefix(self, prefix: str, top_k: int = 10) -> list[FOLIOConcept]:
        folio = self._get_folio()
        try:
            results = folio.search_by_prefix(prefix)
            return [self._to_folio_concept(c) for c, _ in results[:top_k]]
        except Exception:
            logger.warning("search_by_prefix failed for '%s'", prefix, exc_info=True)
            return []

    def get_concept(self, iri: str) -> FOLIOConcept | None:
        folio = self._get_folio()
        try:
            concept = folio[iri]
            return self._to_folio_concept(concept)
        except (KeyError, Exception):
            return None

    @staticmethod
    def _is_excluded_concept(fc: FOLIOConcept) -> bool:
        """True if a concept should never be indexed as a matchable label.

        Filters excluded branches, deprecated concepts, and editorial dupes/
        placeholders whose marker lives in the label text (mirrors the property
        index filter at get_all_property_labels). The "DUPE of `License`" concept
        (RCiAtR0akBA7apMyfjy515B) is caught here by its preferred label.
        """
        if fc.branch in EXCLUDED_BRANCHES:
            return True
        if fc.deprecated:
            return True
        pl = fc.preferred_label or ""
        up = pl.upper()
        if "DUPE" in up or up.startswith("ZZZ:"):
            return True
        return False

    @staticmethod
    def _primary_and_alt_labels(fc: FOLIOConcept):
        """Yield (raw_label, base_label_type) for the labels eligible for lemma keys."""
        if fc.preferred_label:
            yield fc.preferred_label, "preferred"
        if fc.folio_pref_label:
            yield fc.folio_pref_label, "preferred"
        for alt in fc.alternative_labels:
            if alt:
                yield alt, "alternative"

    def _lemma_cache_path(self) -> Path:
        from app.services.folio.owl_cache import get_owl_content_hash
        h = get_owl_content_hash() or "nohash"
        return _LEMMA_CACHE_DIR / f"labels_{h}_v{LEMMA_VERSION}.pkl"

    def _load_lemma_cache(self) -> dict[str, str] | None:
        try:
            path = self._lemma_cache_path()
            if path.exists():
                import pickle
                with open(path, "rb") as f:
                    data = pickle.load(f)
                if isinstance(data, dict):
                    logger.info("Loaded %d label lemmas from cache", len(data))
                    return data
        except Exception:
            logger.debug("Lemma cache load failed", exc_info=True)
        return None

    def _save_lemma_cache(self, lemma_map: dict[str, str]) -> None:
        try:
            path = self._lemma_cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            import pickle
            with open(path, "wb") as f:
                pickle.dump(lemma_map, f)
        except Exception:
            logger.debug("Lemma cache save failed", exc_info=True)

    def _compute_label_lemmas(self) -> dict[str, str]:
        """Map single-word label (lowercased) -> its lemma, for reachability.

        Computed once per ontology version (disk-cached by owl_hash + LEMMA_VERSION)
        and memoized in-process. Only single-word labels (>3 chars, lemma >2 chars,
        not on the legal terms-of-art denylist) whose lemma differs are included.
        This is what lets the singular surface form "Agreement" reach the
        plural-labelled concept "Agreements".
        """
        if self._lemma_map is not None:
            return self._lemma_map

        cached = self._load_lemma_cache()
        if cached is not None:
            self._lemma_map = cached
            return cached

        folio = self._get_folio()
        candidates: set[str] = set()
        for concept in folio.classes:
            try:
                fc = self._to_folio_concept(concept)
                if self._is_excluded_concept(fc):
                    continue
                for raw, _ in self._primary_and_alt_labels(fc):
                    low = raw.lower()
                    if " " in low or len(low) <= 3 or low in _LEMMA_DENYLIST:
                        continue
                    candidates.add(low)
            except Exception:
                continue

        lemma_map: dict[str, str] = {}
        try:
            from app.services.nlp.spacy_singleton import get_spacy_tokenizer
            nlp = get_spacy_tokenizer()
            # Noun lemmatization (Agreements->agreement) requires the tagger +
            # attribute_ruler; without them the lemmatizer silently lowercases.
            if not {"tagger", "attribute_ruler"} <= set(nlp.pipe_names):
                logger.warning(
                    "spaCy pipeline missing tagger/attribute_ruler (%s); "
                    "skipping lemma normalization", nlp.pipe_names,
                )
                self._lemma_map = {}
                return {}
            for doc in nlp.pipe(sorted(candidates), batch_size=512):
                original = doc.text.lower()
                lemma = (doc[0].lemma_.lower() if len(doc) else original)
                if lemma != original and len(lemma) > 2 and lemma not in _LEMMA_DENYLIST:
                    lemma_map[original] = lemma
        except Exception:
            logger.warning("Lemma normalization failed; proceeding without lemma keys", exc_info=True)
            self._lemma_map = {}
            return {}

        self._lemma_map = lemma_map
        self._save_lemma_cache(lemma_map)
        logger.info("Computed %d label lemmas for reachability", len(lemma_map))
        return lemma_map

    @staticmethod
    def _maybe_set(labels: dict[str, LabelInfo], key: str, fc: FOLIOConcept,
                   label_type: str, matched_label: str) -> None:
        """Set labels[key] only if label_type out-ranks the existing entry.

        Single source of priority truth lives in match_tier; this preserves the
        original "preferred > alternative > hidden > translation" behaviour and
        slots lemma tiers in between (lemma_preferred beats alternative).
        """
        existing = labels.get(key)
        if existing is None or is_higher_priority(label_type, existing.label_type):
            labels[key] = LabelInfo(concept=fc, label_type=label_type, matched_label=matched_label)

    def get_all_labels(self) -> dict[str, LabelInfo]:
        """Return a mapping of all concept labels to LabelInfo with type metadata.

        Priority (highest first): preferred > lemma_preferred > alternative >
        lemma_alternative > hidden > translation. A lemma-of-a-preferred-label
        (e.g. "agreement" from "Agreements") therefore out-ranks an exact
        alternative match (e.g. "Agreement" on "License (Agreement)").
        """
        if self._labels_cache is not None:
            return self._labels_cache

        folio = self._get_folio()
        lemma_map = self._compute_label_lemmas()
        labels: dict[str, LabelInfo] = {}

        for concept in folio.classes:
            try:
                fc = self._to_folio_concept(concept)
                if self._is_excluded_concept(fc):
                    continue

                pref = fc.preferred_label
                if pref:
                    self._maybe_set(labels, pref.lower(), fc, "preferred", pref)
                if fc.folio_pref_label:
                    self._maybe_set(labels, fc.folio_pref_label.lower(), fc, "preferred", fc.folio_pref_label)
                for alt in fc.alternative_labels:
                    if alt:
                        self._maybe_set(labels, alt.lower(), fc, "alternative", alt)
                if fc.hidden_label:
                    self._maybe_set(labels, fc.hidden_label.lower(), fc, "hidden", fc.hidden_label)
                if _translation_matching_enabled() and fc.translations:
                    pref_lower = pref.lower() if pref else ""
                    for _lang, trans_text in fc.translations.items():
                        if trans_text and trans_text.lower() != pref_lower:
                            self._maybe_set(labels, trans_text.lower(), fc, "translation", trans_text)

                # Lemma keys for reachability (singular/plural). lemma_map only
                # holds labels whose lemma is safe to add (denylist-filtered).
                for raw, base_type in self._primary_and_alt_labels(fc):
                    lemma = lemma_map.get(raw.lower())
                    if lemma:
                        self._maybe_set(labels, lemma, fc, lemma_type_for(base_type), raw)
            except Exception:
                continue

        self._labels_cache = labels
        logger.info("Indexed %d FOLIO labels", len(labels))
        return labels

    def get_all_labels_multi(self) -> dict[str, list[LabelInfo]]:
        """Return a mapping of label text to ALL matching concepts.

        Unlike get_all_labels() which keeps only one concept per label,
        this returns every concept that has the label (as preferred, alt, lemma,
        hidden, or translation). Within each list, higher-priority tiers sort
        first; entries are deduplicated by IRI.
        """
        if self._labels_multi_cache is not None:
            return self._labels_multi_cache

        folio = self._get_folio()
        lemma_map = self._compute_label_lemmas()
        labels: dict[str, list[LabelInfo]] = {}

        for concept in folio.classes:
            try:
                fc = self._to_folio_concept(concept)
                if self._is_excluded_concept(fc):
                    continue

                pref = fc.preferred_label
                if pref:
                    labels.setdefault(pref.lower(), []).append(LabelInfo(
                        concept=fc, label_type="preferred", matched_label=pref,
                    ))
                if fc.folio_pref_label:
                    labels.setdefault(fc.folio_pref_label.lower(), []).append(LabelInfo(
                        concept=fc, label_type="preferred", matched_label=fc.folio_pref_label,
                    ))
                for alt in fc.alternative_labels:
                    if alt:
                        labels.setdefault(alt.lower(), []).append(LabelInfo(
                            concept=fc, label_type="alternative", matched_label=alt,
                        ))
                if fc.hidden_label:
                    labels.setdefault(fc.hidden_label.lower(), []).append(LabelInfo(
                        concept=fc, label_type="hidden", matched_label=fc.hidden_label,
                    ))
                if _translation_matching_enabled() and fc.translations:
                    pref_lower = (fc.preferred_label or "").lower()
                    for _lang, trans_text in fc.translations.items():
                        if trans_text and trans_text.lower() != pref_lower:
                            labels.setdefault(trans_text.lower(), []).append(LabelInfo(
                                concept=fc, label_type="translation", matched_label=trans_text,
                            ))

                # Lemma entries for reachability.
                for raw, base_type in self._primary_and_alt_labels(fc):
                    lemma = lemma_map.get(raw.lower())
                    if lemma:
                        labels.setdefault(lemma, []).append(LabelInfo(
                            concept=fc, label_type=lemma_type_for(base_type), matched_label=raw,
                        ))
            except Exception:
                continue

        # Deduplicate by IRI within each label key; higher-priority tiers first.
        from app.services.folio.match_tier import label_type_rank
        for key, entries in labels.items():
            seen_iris: set[str] = set()
            deduped: list[LabelInfo] = []
            entries.sort(key=lambda e: label_type_rank(e.label_type))
            for entry in entries:
                if entry.concept.iri not in seen_iris:
                    seen_iris.add(entry.concept.iri)
                    deduped.append(entry)
            labels[key] = deduped

        self._labels_multi_cache = labels
        total_entries = sum(len(v) for v in labels.values())
        logger.info("Indexed %d FOLIO multi-labels (%d total entries)", len(labels), total_entries)
        return labels

    @staticmethod
    def _strip_prefix(label: str) -> str:
        """Strip namespace prefixes like 'folio:', 'utbms:', 'oasis:' from a label."""
        for prefix in ("folio:", "utbms:", "oasis:"):
            if label.startswith(prefix):
                return label[len(prefix):]
        return label

    def get_all_property_labels(self) -> dict[str, PropertyLabelInfo]:
        """Return a mapping of all property labels to PropertyLabelInfo.

        Preferred labels take priority. Deprecated properties are excluded.
        Labels are lowercased keys with prefixes stripped.
        """
        if self._property_labels_cache is not None:
            return self._property_labels_cache

        folio = self._get_folio()
        labels: dict[str, PropertyLabelInfo] = {}

        for prop in folio.object_properties:
            try:
                fp = self._to_folio_property(prop)

                # Skip deprecated properties
                if "DEPRECATED" in fp.label or fp.label.startswith("ZZZ:"):
                    continue

                # Index clean preferred label
                if fp.clean_label:
                    key = fp.clean_label.lower()
                    labels[key] = PropertyLabelInfo(
                        prop=fp,
                        label_type="preferred",
                        matched_label=fp.clean_label,
                    )

                # Index clean alt labels (only if not already preferred)
                for alt in fp.clean_alt_labels:
                    if alt:
                        akey = alt.lower()
                        if akey not in labels or labels[akey].label_type != "preferred":
                            labels[akey] = PropertyLabelInfo(
                                prop=fp,
                                label_type="alternative",
                                matched_label=alt,
                            )
            except Exception:
                continue

        self._property_labels_cache = labels
        logger.info("Indexed %d FOLIO property labels", len(labels))
        return labels

    def get_concept_count(self) -> int:
        """Return the number of FOLIO concepts (classes)."""
        folio = self._get_folio()
        return len(folio.classes)

    def get_label_count(self) -> int:
        """Return the number of indexed labels."""
        labels = self.get_all_labels()
        return len(labels)

    def get_property_count(self) -> int:
        """Return the number of indexed property labels."""
        props = self.get_all_property_labels()
        return len(props)

    def get_property(self, iri: str) -> FOLIOProperty | None:
        """Look up a property by IRI."""
        folio = self._get_folio()
        for prop in folio.object_properties:
            if getattr(prop, "iri", "") == iri:
                return self._to_folio_property(prop)
        return None

    def _to_folio_property(self, prop) -> FOLIOProperty:
        """Convert an OWLObjectProperty to our FOLIOProperty dataclass."""
        raw_label = getattr(prop, "label", None) or getattr(prop, "preferred_label", "") or ""
        clean_label = self._strip_prefix(raw_label)

        # Convert camelCase to spaces (e.g. "hasFigure" → "has Figure")
        # but only for structural labels — leave verbs like "reversed" as-is
        if clean_label and clean_label[0].islower() and any(c.isupper() for c in clean_label[1:]):
            import re
            clean_label = re.sub(r"([a-z])([A-Z])", r"\1 \2", clean_label).lower()

        raw_alts = getattr(prop, "alternative_labels", []) or []
        clean_alts = [self._strip_prefix(a) for a in raw_alts if a]

        definition = getattr(prop, "definition", "") or ""
        examples = getattr(prop, "examples", []) or []
        domain = getattr(prop, "domain", []) or []
        range_ = getattr(prop, "range", []) or []
        inverse_of = getattr(prop, "inverse_of", None)
        sub_prop = getattr(prop, "sub_property_of", []) or []

        return FOLIOProperty(
            iri=getattr(prop, "iri", "") or "",
            label=raw_label,
            clean_label=clean_label,
            preferred_label=raw_label,
            alt_labels=list(raw_alts),
            clean_alt_labels=clean_alts,
            definition=definition,
            examples=list(examples) if examples else None,
            domain_iris=list(domain) if domain else None,
            range_iris=list(range_) if range_ else None,
            inverse_of=inverse_of,
            sub_property_of=list(sub_prop) if sub_prop else None,
        )

    def _to_folio_concept(self, concept) -> FOLIOConcept:
        # preferred_label may be None; fall back to label
        pref_label = getattr(concept, "label", None) or getattr(concept, "preferred_label", "") or ""
        alt_labels = getattr(concept, "alternative_labels", []) or []
        definition = getattr(concept, "definition", "") or ""
        iri = getattr(concept, "iri", "") or ""
        parent_iris = getattr(concept, "sub_class_of", []) or []

        # OWL/SKOS metadata fields
        examples = getattr(concept, "examples", []) or []
        notes = getattr(concept, "notes", []) or []
        editorial_note = getattr(concept, "editorial_note", "") or ""
        comment = getattr(concept, "comment", "") or ""
        description = getattr(concept, "description", "") or ""
        source = getattr(concept, "source", "") or ""
        see_also = getattr(concept, "see_also", []) or []
        hidden_label = getattr(concept, "hidden_label", "") or ""
        is_defined_by = getattr(concept, "is_defined_by", "") or ""
        deprecated = bool(getattr(concept, "deprecated", False))
        history_note = getattr(concept, "history_note", "") or ""
        country = getattr(concept, "country", "") or ""
        raw_translations = getattr(concept, "translations", {}) or {}
        translations = dict(raw_translations) if raw_translations else None

        branch = self._get_branch(iri, list(parent_iris))

        # FOLIO skos:prefLabel — only store when it exists and differs from rdfs:label
        folio_pref = getattr(concept, "preferred_label", "") or ""
        folio_pref_label = folio_pref if folio_pref and folio_pref.lower() != pref_label.lower() else ""

        return FOLIOConcept(
            iri=iri,
            preferred_label=pref_label,
            alternative_labels=list(alt_labels),
            definition=definition,
            branch=branch,
            parent_iris=list(parent_iris),
            folio_pref_label=folio_pref_label,
            examples=list(examples) if examples else None,
            notes=list(notes) if notes else None,
            editorial_note=editorial_note,
            comment=comment,
            description=description,
            source=source,
            see_also=list(see_also) if see_also else None,
            hidden_label=hidden_label,
            is_defined_by=is_defined_by,
            deprecated=deprecated,
            history_note=history_note,
            country=country,
            translations=translations,
        )
