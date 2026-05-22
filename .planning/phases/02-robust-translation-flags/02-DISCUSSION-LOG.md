# Phase 02: Robust translation flags - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 02-robust-translation-flags
**Areas discussed:** Language-only locales, Flag visual style, Fallback appearance, Label & disambiguation

---

## Language-only locales

| Option | Description | Selected |
|--------|-------------|----------|
| Map to country flag | Explicit language→representative-country map (he→IL, hi→IN, ja→JP, zh→CN, es→ES, fr→FR). Fixes current broken-flag bug. | ✓ |
| Language pill (no flag) | Region-less locales show a text language pill instead of a flag. | |
| Use the fallback pill | Treat region-less locales identically to FLAG-04 unknowns. | |

**User's choice:** Map to country flag
**Notes:** Locales without a region (he, hi, ja, zh, es, fr) are rare (1–2 concepts each) but currently produce invalid codes like "HE"/"ZH"; mapping to a representative country flag keeps the visual consistent and fixes the bug.

---

## Flag visual style

| Option | Description | Selected |
|--------|-------------|----------|
| Rounded rect + hairline border | ~16px, 4:3 rounded rectangle, 1px subtle theme-aware border so white flags (JP, CN) don't vanish on light bg. | ✓ |
| Circle / squircle | Round flag avatars; crops detail, harder to read small. | |
| Plain rectangle, no border | Simplest; white-edged flags blend into light backgrounds. | |

**User's choice:** Rounded rect + hairline border
**Notes:** Border must be theme-aware (CSS var) to work in Dark / Light / Mixed.

---

## Fallback appearance (FLAG-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Country-code pill | Muted rounded chip with 2-letter code, same footprint as a flag; reads as intentional. | ✓ |
| Language-name pill | Show language name; more readable but variable width. | |
| Generic globe icon | Neutral glyph; compact but conveys no specific info. | |

**User's choice:** Country-code pill
**Notes:** Must never read as "broken"; reuse the existing chip aesthetic.

---

## Label & disambiguation (FLAG-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Language (Country) | e.g. "Spanish (Mexico)"; aria-label + title; disambiguates en-gb/us/ca. | ✓ |
| Country name only | e.g. "Mexico"; doesn't name the language. | |
| Locale code only | e.g. "es-mx"; precise but unfriendly. | |

**User's choice:** Language (Country)
**Notes:** Flags alone are ambiguous; "Language (Country)" is most informative for screen readers. `Intl.DisplayNames` can likely generate these natively (noted in CONTEXT for research).

---

## Claude's Discretion

- SVG flag source/library (open-licensed), embedding mechanism in the single-file frontend, exact border/radius pixel values.

## Deferred Ideas

- Consolidated system status chip and other emoji-glyph robustness — Phase 03 / future.
- Restyling/regrouping the layer chips — deferred to REQUIREMENTS.md Future.
