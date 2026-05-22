# Phase 02: Robust translation flags - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the Unicode emoji flags shown next to FOLIO concept translations (in the detail panel) with self-contained inline SVG flags that render identically on every OS/browser (Windows shows boxed "GB"/"ES" letters for emoji flags today) and make zero external requests (immune to content/privacy blockers like Privacy Badger). Covers FLAG-01..FLAG-04.

**In scope:** flag rendering for the translation pills only. **Not in scope:** the consolidated system status chip (Phase 03), the layer chips, or any other emoji usage in the app.
</domain>

<decisions>
## Implementation Decisions

### Flag source & approach (locked by roadmap)
- **D-01:** Flags are self-contained **inline SVG** — no Unicode emoji, no external image/CDN requests. Must render on Windows/macOS/Linux and survive content blockers.
- **D-02:** Bundle covers the **12 countries** FOLIO's locales resolve to: DE, CA, GB, US, ES, MX, FR, IL, IN, JP, BR, CN. (Full FOLIO locale set observed: `de-de, en-ca, en-gb, en-us, es-es, es-mx, fr-fr, he-il, hi-in, ja-jp, pt-br, zh-cn` + rare language-only `es, fr, he, hi, ja, zh`.)

### Language-only locales (he, hi, ja, zh, es, fr — no region)
- **D-03:** Map each language-only locale to a **representative country flag**: `he→IL`, `hi→IN`, `ja→JP`, `zh→CN`, `es→ES`, `fr→FR`. This fixes the current bug where `localeToFlag('he')` produces "HE" (not a country) and renders broken/blank. These locales are rare (1–2 concepts each) but must not break.

### Flag visual style
- **D-04:** **Rounded rectangle, ~16px wide, 4:3 aspect, with a 1px hairline border.** The border keeps white-heavy flags (JP, CN) from disappearing on the light-theme background. Border color must be theme-aware (CSS var) so it works in Dark / Light / Mixed.

### Fallback for unknown/unbundled locales (FLAG-04)
- **D-05:** A **muted, rounded country-code pill** showing the 2-letter code (e.g. "CA"), same footprint as a flag. Must read as intentional — never a broken glyph. Reuse the existing chip/pill aesthetic.

### Accessible label & tooltip (FLAG-03)
- **D-06:** Each flag/pill gets an accessible label and hover tooltip in the form **"Language (Country)"** — e.g. "Spanish (Mexico)", "English (United Kingdom)". Set via both `aria-label` and `title`. This disambiguates same-language regional variants (en-gb vs en-us vs en-ca) and serves screen-reader users.

### Claude's Discretion
- Exact SVG flag source/library (must be open-licensed; see research questions), the precise embedding mechanism in the single-file frontend (JS map of SVG strings vs `<symbol>` sprite), and exact border/radius pixel values within the style intent above.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` § "Phase 02: Robust translation flags" — goal + 4 success criteria.
- `.planning/REQUIREMENTS.md` § "Translation Flags (FLAG)" — FLAG-01..FLAG-04.

No external specs/ADRs — requirements fully captured in decisions above.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/index.html:10286` — `localeToFlag(locale)`: the current emoji generator (`String.fromCodePoint(0x1f1a5 + ...)`). This is the single function to replace with SVG lookup + the language→country map (D-03) + fallback (D-05).
- Browser-native **`Intl.DisplayNames`** can generate the "Language (Country)" labels (D-06) from a locale string with no dependency — strongly preferred over a hand-maintained map. Researcher should confirm coverage/fallbacks.

### Established Patterns
- Single translation render site: `frontend/index.html:8343-8344` —
  `` `<span class="detail-trans-pill"><span class="flag">${flag}</span>${escapeHtml(label)}</span>` ``. (The pills at line 8388 are see-also pills, NOT translations — leave untouched.)
- The "+N more" expand toggle wraps the pill list at ~8348-8350.
- Theme system: all colors are CSS vars (Dark/Light/Mixed). The hairline border (D-04) must use a theme-aware var, consistent with the v1.0 token system.

### Integration Points
- CSS lives at `frontend/index.html:1021-1032`: `.detail-translations`, `.detail-trans-pills`, `.detail-trans-pill`, and `.detail-trans-pill .flag { font-size: 14px }`. The `.flag` rule is emoji-sized today and must change to size/box the inline SVG (width/height/border-radius/border).
- Single-file frontend, no build step, no new runtime dependencies — flag SVGs must be embedded inline.

### Research questions (for phase-researcher)
- Which open-licensed SVG flag set to vendor (e.g., flag-icons (MIT), twemoji country flags (CC-BY 4.0), flagpack) for the 12 countries — license + minimal byte size, since they inline into a ~10k-line single file.
- Confirm `Intl.DisplayNames` produces clean "Language (Country)" output for all 18 locales and define the fallback when a locale is unknown.
</code_context>

<specifics>
## Specific Ideas

- The bug originally surfaced on PROD (`enrich.openlegalstandard.org`) viewed from Windows/Chrome with Privacy Badger — both the OS emoji-flag gap and the blocker concern must be satisfied by the SVG approach.
- Visual reference: the existing translation pills (flag + translated label) in the concept detail panel; keep that layout, just swap the flag rendering.
</specifics>

<deferred>
## Deferred Ideas

- Consolidated system status chip and any other emoji-glyph robustness — Phase 03 / future.
- Restyling/regrouping the layer chips — deferred (see REQUIREMENTS.md Future).

None other — discussion stayed within phase scope.
</deferred>

---

*Phase: 02-robust-translation-flags*
*Context gathered: 2026-05-22*
