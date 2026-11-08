"""Deterministic federal court spellings and court jurisdiction precision checks."""
from __future__ import annotations

import re
from collections.abc import Iterable


def normalize_court_text(text: str) -> str:
    return " ".join(text.casefold().split()).removeprefix("the ")


def is_deictic_court(text: str) -> bool:
    """A court reference whose identity must come from document context."""
    return bool(re.fullmatch(r"(?:this|the|that|said) court", " ".join(text.casefold().split())))


def exact_label(text: str, preferred_labels: Iterable[str], aliases: Iterable[str] = ()) -> bool:
    """Gate exemption: preferred labels or aliases with at least two words."""
    query = normalize_court_text(text)
    return any(query == normalize_court_text(label) for label in preferred_labels if label) or any(
        query == normalize_court_text(label) for label in aliases if label and len(label.split()) >= 2
    )


_ORDINALS = dict(zip(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh".split(),
    "1st 2nd 3rd 4th 5th 6th 7th 8th 9th 10th 11th".split(),
))


# Bluebook spellings, compacted only for parsing dotted/undotted spacing variants.
_BLUEBOOK_STATES = dict(zip(
    "ala alaska ariz ark cal colo conn del fla ga haw idaho ill ind iowa kan ky la me md mass mich minn miss mo mont neb nev nh nj nm ny nc nd ohio okla or pa ri sc sd tenn tex utah vt va wash wva wis wyo dc pr".split(),
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|district of columbia|puerto rico".split("|"),
))


def canonical_court_keys(text: str) -> list[str]:
    original = normalize_court_text(text)
    stripped = re.sub(r"^(?:united states|u\.s\.|us)\s+", "", original)
    keys = [original, stripped]
    match = re.fullmatch(r"(?:court of appeals for the )?(.+?) (?:circuit|cir\.)", stripped)
    if match:
        ordinal = match[1]
        ordinal = next((word for word, number in _ORDINALS.items() if number == ordinal), ordinal)
        if ordinal in _ORDINALS or ordinal in {"d.c.", "federal"}:
            number = _ORDINALS.get(ordinal, ordinal)
            keys += [f"court of appeals for the {ordinal} circuit", f"u.s. ct. app. - {number} circuit"]
    match = re.fullmatch(r"(district|bankruptcy) court for the (?:(northern|southern|eastern|western|central|middle) )?district of (.+)", stripped)
    if match:
        kind, direction, state = match.groups()
        district = f"{direction[0]}.d." if direction else "d."
        keys.append(f"u.s. {kind} court - {district} {state}")
        if kind == "district":
            keys.append(f"district court, {district} {state}")
    bluebook = re.fullmatch(r"(.+?)(?:\s+(bankr\.))?", stripped)
    compact = re.sub(r"[.\s]", "", bluebook[1]) if bluebook else ""
    match = re.fullmatch(r"([nsewcm]?d)(.+)", compact)
    if match and match[2] in _BLUEBOOK_STATES:
        district = ".".join(match[1]) + "."
        state = _BLUEBOOK_STATES[match[2]]
        kind = "bankruptcy" if bluebook[2] else "district"
        keys.append(f"u.s. {kind} court - {district} {state}")
        if kind == "district":
            keys.append(f"district court, {district} {state}")
    keys += [key + "." for key in keys if "court - " in key or "court, " in key]
    return list(dict.fromkeys(keys))


_JURISDICTIONS = """alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|puerto rico|guam|american samoa|northern mariana islands|virgin islands|district of columbia""".split("|")


def _contains(text: str, token: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", text))


def jurisdiction_mismatch(query: str, label: str) -> bool:
    query, label = normalize_court_text(query), normalize_court_text(label)
    if "court" not in label and "circuit" not in label:
        return False
    jurisdictions = [(token,) for token in _JURISDICTIONS if token != "district of columbia"]
    jurisdictions += [("d.c.", "district of columbia"), ("u.s.", "united states"), ("federal",)]
    jurisdictions += [(token,) for token in re.findall(r"\b\w+ county\b", label)]
    return any(
        any(_contains(label, token) for token in aliases)
        and not any(_contains(query, token) for token in aliases)
        for aliases in jurisdictions
    )


def is_case_caption(text: str) -> bool:
    return bool(re.search(r"\b[A-Z][\w'’-]*(?:\s+.*?)?\s+v(?:\.|s\.?)\s+[A-Z]\S*", text))


def concept_labels(concept) -> list[str]:
    return [concept.preferred_label, concept.folio_pref_label, *concept.alternative_labels, concept.hidden_label]
