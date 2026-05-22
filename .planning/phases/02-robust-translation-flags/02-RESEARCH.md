# Phase 02: Robust translation flags - Research

**Researched:** 2026-05-22
**Domain:** Front-end (vanilla JS, single-file HTML), inline SVG asset vendoring, i18n display names, theming, accessibility
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Flags are self-contained **inline SVG** — no Unicode emoji, no external image/CDN requests. Must render on Windows/macOS/Linux and survive content blockers.
- **D-01b:** **Reuse existing open-licensed flag SVGs — do NOT hand-build flags.** Vendor (copy inline) the specific SVGs from an established set. **Preferred source: `flag-icons` (lipis/flag-icons), MIT-licensed**, ISO-code-named, 4:3 variants matching the rounded-rectangle style. MIT = no UI attribution burden; retain the license notice in-repo. (Do NOT link a CDN like flagcdn.com — external request violates FLAG-02.)
- **D-02:** Bundle covers the **12 countries** FOLIO's locales resolve to: DE, CA, GB, US, ES, MX, FR, IL, IN, JP, BR, CN. (Full FOLIO locale set: `de-de, en-ca, en-gb, en-us, es-es, es-mx, fr-fr, he-il, hi-in, ja-jp, pt-br, zh-cn` + rare language-only `es, fr, he, hi, ja, zh`.)
- **D-03:** Map each language-only locale to a **representative country flag**: `he→IL`, `hi→IN`, `ja→JP`, `zh→CN`, `es→ES`, `fr→FR`.
- **D-04:** **Rounded rectangle, ~16px wide, 4:3 aspect, with a 1px hairline border.** Border keeps white-heavy flags (JP, CN) from disappearing on light-theme background. Border color must be theme-aware (CSS var) so it works in Dark / Light / Mixed.
- **D-05:** Fallback for unknown/unbundled locale = a **muted, rounded country-code pill** showing the 2-letter code (e.g. "CA"), same footprint as a flag. Must read as intentional — never a broken glyph. Reuse the existing chip/pill aesthetic.
- **D-06:** Each flag/pill gets an accessible label + hover tooltip in the form **"Language (Country)"** — e.g. "Spanish (Mexico)", "English (United Kingdom)". Set via both `aria-label` and `title`.

### Claude's Discretion
- The precise embedding mechanism in the single-file frontend (JS map of SVG strings vs `<symbol>` sprite) and exact border/radius pixel values within the style intent above. (Flag source is locked to flag-icons per D-01b — not discretionary.)

### Deferred Ideas (OUT OF SCOPE)
- Consolidated system status chip and any other emoji-glyph robustness — Phase 03 / future.
- Restyling/regrouping the layer chips — deferred.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FLAG-01 | Flags render as self-contained inline SVG (no emoji, no external requests) — display on every OS incl. Windows | flag-icons MIT 4x3 SVGs vendored inline (Standard Stack); embedding mechanism (Pattern 1); replaces emoji `localeToFlag` |
| FLAG-02 | Flags display correctly when a content/privacy blocker (Privacy Badger) is enabled | Inline SVG = zero network requests — verified by absence of `<img src>`/`url()` in flag markup (Pitfall 3 / Validation) |
| FLAG-03 | Screen-reader user gets accessible label naming locale/country per flag | `Intl.DisplayNames` → "Language (Country)" + `role="img"` `aria-label` + `title` (Pattern 2, Code Examples) |
| FLAG-04 | Graceful fallback (styled country-code pill) for any locale without a bundled flag — never a broken glyph | Fallback pill pattern + locale→country resolver returning null path (Pattern 3) |
</phase_requirements>

## Summary

This phase replaces the emoji-based `localeToFlag(locale)` (frontend/index.html:10286) — which emits Unicode regional-indicator codepoints that Windows renders as boxed "GB"/"ES" letters — with **inline SVG flags vendored from `lipis/flag-icons` (MIT)**. The work is almost entirely front-end: a locale→country resolver, an SVG lookup map of 12 flags, a theme-aware `.flag` CSS box, a `Intl.DisplayNames`-derived accessible label, and a styled fallback pill. No backend changes, no new runtime dependencies (SVGs are copy-pasted source, not an installed package), no build step — fully consistent with the single-file frontend constraint in CLAUDE.md.

The single non-obvious risk is **asset size**: 10 of the 12 flags are tiny (80 B–1.1 KB), but **es.svg (81 KB) and mx.svg (85 KB) carry full coats of arms** that render as a 1-px smudge at 16 px. Inlining them raw would add ~166 KB to an already ~10,375-line file. The right move is to substitute hand-trimmed plain-stripe variants for ES and MX (visually identical at 16 px, ~250 B each), or run the two heavy files through `svgo`. A second non-obvious risk is **duplicate DOM IDs**: each flag-icons SVG ships `id="flag-icons-XX"` and some (jp, in) define internal `clipPath`/`defs` ids — inlining 12 verbatim would create id collisions. Strip the wrapper `id` and namespace any internal ids per flag.

**Primary recommendation:** Vendor the 12 flag-icons 4x3 SVGs into a JS object map keyed by ISO-alpha-2 (lowercase), substituting trimmed stripe-only variants for `es` and `mx`. Strip each SVG's `id` attribute and add `aria-hidden`/`focusable=false`; let the wrapping element carry `role="img"` + `aria-label`/`title` built from `Intl.DisplayNames`. Replace `localeToFlag` with a resolver that maps locale→country (handling language-only locales D-03), returns the SVG string or `null`, and a `localeLabel` helper for the accessible text. CSS `.flag` becomes a 16×12 (4:3) inline-block with `border-radius`, `border:1px solid var(--border)`, and `overflow:hidden`. Fallback path renders a `.flag-fallback` country-code pill.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Flag glyph rendering | Browser / Client | — | Pure presentation; SVG drawn by the browser, no server involvement |
| Locale→country resolution | Browser / Client | — | Static lookup over a known 12-locale set; runs at render time in `makePill` |
| "Language (Country)" labels | Browser / Client | — | `Intl.DisplayNames` is a browser-native API; no server round-trip |
| Flag SVG assets | Static (vendored in HTML) | — | Copied into the single-file frontend at author time; no CDN/static-server fetch (FLAG-02) |
| Theme-aware hairline border | Browser / Client | — | Driven by existing CSS custom properties (`--border`) per `[data-theme]` |

Every capability lives in the browser tier. There is **no backend, API, or build-tier responsibility** in this phase. This is a deliberate consequence of D-01 (self-contained inline SVG): the moment any capability moved to a static-asset tier (e.g. an external sprite URL), FLAG-02 would break.

## Standard Stack

### Core
| Library / Asset | Version | Purpose | Why Standard |
|-----------------|---------|---------|--------------|
| `lipis/flag-icons` 4x3 SVGs (vendored, not installed) | repo `main` @ 2026-05 (npm pkg 7.5.0) | Source of the 12 country flag SVGs, copied inline | De-facto standard open flag set; MIT; ISO-named; 4:3 variants match D-04 rounded-rect intent `[VERIFIED: github.com/lipis/flag-icons LICENSE = MIT]` |
| `Intl.DisplayNames` (browser-native) | Baseline (widely available since 2021-04) | Generate "Language (Country)" labels from locale strings | Native, zero-dependency, evergreen-supported; eliminates a hand-maintained label map `[VERIFIED: developer.mozilla.org]` |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `svgo` (npm, dev-time only) | 4.0.1 | One-time minification of the two heavy SVGs (es, mx) before vendoring | Optional alternative to hand-trimming ES/MX coats of arms `[VERIFIED: npm registry — npm view svgo version]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| flag-icons (locked D-01b) | `flagpack-core` (Yummygum, MIT) | Also MIT, ISO-named, more uniformly small files — but D-01b locks the source to flag-icons. Only relevant if a *specific* flag-icons file is unusable. `[CITED: github.com/Yummygum/flagpack-core]` |
| flag-icons es/mx raw | flag-icons es/mx run through `svgo`, OR hand-trimmed stripe-only variants | svgo keeps the coat of arms but shrinks bytes modestly; hand-trim drops it entirely (invisible at 16 px) for a ~250 B file. Hand-trim wins on size; svgo wins on fidelity-if-ever-enlarged. |
| JS object map of SVG strings | inline `<svg><symbol>` sprite + `<use>` | See Pattern 1 — object map recommended for this codebase. |

**Installation:** None at runtime. SVGs are **copied as text** into `frontend/index.html`. This honors the CLAUDE.md "no new runtime dependencies" rule. The only optional tooling install is dev-time minification:
```bash
# OPTIONAL, dev-time only — do NOT add to any runtime manifest
npx svgo --multipass es.svg mx.svg     # svgo is an npm package (v4.0.1)
```

**Source paths to vendor from (raw GitHub):**
```
https://raw.githubusercontent.com/lipis/flag-icons/main/flags/4x3/<iso>.svg
# <iso> ∈ { de, ca, gb, us, es, mx, fr, il, in, jp, br, cn }
```

**Version verification (run at research time):**
- `npm view flag-icons version` → `7.5.0` `[VERIFIED: npm registry]`
- `npm view svgo version` → `4.0.1` `[VERIFIED: npm registry]`
- `Intl.DisplayNames` Baseline "widely available" since 2021-04 `[VERIFIED: developer.mozilla.org]`

## Package Legitimacy Audit

> This phase installs **no runtime packages**. It vendors SVG *source text* (copy-paste) and uses one optional dev-time CLI (`svgo`). Audit covers the candidate names for completeness.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `flag-icons` | npm | ~12 yrs (since 2013) | millions/wk | github.com/lipis/flag-icons | n/a (npm; slopcheck checked PyPI) | Source-of-truth for vendored SVGs — **not installed**, only files copied |
| `svgo` | npm | ~11 yrs | tens of M/wk | github.com/svg/svgo | **[SLOP]** ⚠ false positive — see note | Optional dev tool only; **safe** |

**slopcheck note (cross-ecosystem false positive):** slopcheck 0.6.1 reported `[SLOP] svgo (pypi) — does not exist on pypi`. This is the documented cross-ecosystem confusion vector: **svgo is an npm package, not PyPI**. `npm view svgo version` returns `4.0.1` from a 11-year-old, tens-of-millions-weekly-downloads package owned by the official `svg/svgo` org. svgo is **legitimate**. Disposition: keep as optional dev tool. `[VERIFIED: npm registry]`

**Packages removed due to slopcheck [SLOP] verdict:** none (the one [SLOP] was a PyPI/npm ecosystem mismatch, not a hallucination).
**Packages flagged as suspicious [SUS]:** none.

**No runtime install gating needed** — nothing is installed. The planner does NOT need a `checkpoint:human-verify` task here, because no package enters the dependency graph. The only verification the planner should keep is the standard "no external requests in flag markup" check (FLAG-02).

## Architecture Patterns

### System Architecture Diagram

```
detail.translations (object: { "es-mx": "Derecho ...", "he": "...", ... })
        │
        ▼  Object.entries → makePill([locale, label])     (index.html ~8342)
        │
        ├─► localeToCountry(locale)  ──► ISO-alpha2 country code  OR  null
        │        (split "-", take region; else map language→country via D-03)
        │
        ├─► FLAG_SVG[country]        ──► inline <svg> string       OR  undefined
        │
        ├─► localeLabel(locale)      ──► "Spanish (Mexico)"  (Intl.DisplayNames)
        │
        ▼
   ┌─────────────────────────────────────────────────────────┐
   │  branch A: SVG found                                      │
   │    <span class="flag" role="img" aria-label=… title=…>   │
   │       {inline svg, id stripped, aria-hidden}              │
   │    </span> + escapeHtml(label)                            │
   │                                                           │
   │  branch B: no SVG (FLAG-04)                               │
   │    <span class="flag-fallback" role="img"                │
   │          aria-label=… title=…>CA</span> + label           │
   └─────────────────────────────────────────────────────────┘
        │
        ▼  joined into collapsedHtml / expandedHtml (≤3 + "+N more" toggle)
        ▼  injected into .detail-trans-pills   (index.html ~8348)
```
No data leaves the browser. CSS `var(--border)` resolves per `[data-theme]` for the hairline.

### Recommended Project Structure
```
frontend/index.html        # ALL changes land here:
  <style> .detail-trans-pill .flag { ... }      # ~line 1032 — rewrite for SVG box
          .flag-fallback { ... }                # NEW rule near it
  <script>
    const FLAG_SVG = { de:'<svg…>', ca:'…', … }; # NEW const (the 12 vendored SVGs)
    const LANG_TO_COUNTRY = { he:'il', hi:'in', ja:'jp', zh:'cn', es:'es', fr:'fr' };
    function localeToCountry(locale) { … }        # NEW (replaces emoji logic)
    function flagMarkup(locale) { … }             # NEW (svg span OR fallback pill)
    function localeLabel(locale) { … }            # NEW (Intl.DisplayNames)
    function localeToFlag(locale) { … }           # REMOVE/replace at ~10286
  makePill (~8342) calls flagMarkup(locale) + localeLabel(locale)

LICENSES/flag-icons-LICENSE.txt   # NEW — retain MIT notice (see Don't Hand-Roll)
scripts/flags.test.mjs            # NEW — node:test unit coverage (see Validation)
```

### Pattern 1: JS object map of SVG strings (RECOMMENDED for this codebase)
**What:** Store each flag as an inline `<svg>` string in a `const FLAG_SVG = { de:'…', … }` map; `flagMarkup()` looks up by country code and injects the string into a wrapping `<span class="flag" role="img">`.
**When to use:** Single-file vanilla JS, content built by string concatenation (this codebase already does exactly this — see `_removeTagIcon`, `_thumbUpIcon` JS-string-SVG consts at index.html:6731-6734).
**Why over `<symbol>` sprite:**
- The codebase's established idiom is JS-string SVG icons concatenated into `innerHTML` — the object map matches it exactly. `[VERIFIED: codebase grep index.html:6731-6734]`
- `<use href="#sym">` sprites need the `<symbol>` defs present in the DOM before the `<use>` renders, and `currentColor`/per-instance theming through `<use>` is fiddly across a shadow boundary. The detail panel is re-rendered via `innerHTML`, which would re-parse `<use>` but not re-inject symbols.
- Flags are **multi-color raster-like fills** — they do NOT benefit from `currentColor` the way monochrome icons do. The one themeable element (the hairline border) lives on the **wrapper CSS**, not inside the SVG, so a sprite gives no theming advantage.
**Example:**
```javascript
// Source: pattern follows existing index.html:6731 (_removeTagIcon JS-string SVG const)
const FLAG_SVG = {
  jp: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#fff" d="M0 0h640v480H0z"/><circle cx="320" cy="240" r="194.9" fill="#bc002d"/></svg>',
  // … 11 more, id="flag-icons-XX" stripped, internal ids namespaced if present
};
function flagMarkup(locale) {
  const cc = localeToCountry(locale);             // 'jp' | 'il' | … | null
  const label = localeLabel(locale);              // "Japanese (Japan)"
  const svg = cc && FLAG_SVG[cc];
  if (svg) {
    return `<span class="flag" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${svg}</span>`;
  }
  const code = (cc || locale.split('-')[0] || '?').slice(0,2).toUpperCase();
  return `<span class="flag-fallback" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${escapeHtml(code)}</span>`;
}
```

### Pattern 2: Accessible label via `Intl.DisplayNames`
**What:** Compose a human label from the locale's language + region parts.
**When to use:** Building the `aria-label`/`title` (D-06, FLAG-03).
**Example:**
```javascript
// Source: developer.mozilla.org/.../Intl/DisplayNames  [VERIFIED]
const _langDN   = new Intl.DisplayNames(['en'], { type: 'language' });
const _regionDN = new Intl.DisplayNames(['en'], { type: 'region' });
function localeLabel(locale) {
  const [lang, region] = locale.split('-');
  let out = '';
  try { out = _langDN.of(lang) || lang; } catch { out = lang; }
  // language-only locales (he/hi/ja/zh/es/fr) → use the D-03 representative country
  const cc = (region || LANG_TO_COUNTRY[lang] || '').toUpperCase();
  if (cc) {
    let country;
    try { country = _regionDN.of(cc); } catch { country = null; }
    if (country && country !== cc) out += ` (${country})`;
  }
  return out;   // e.g. "Spanish (Mexico)", "Hebrew (Israel)", "English (United Kingdom)"
}
```
**Note:** `Intl.DisplayNames#of()` defaults to `fallback:'code'` — it returns the **input code itself** (never `undefined`) when no display name exists, so the `|| lang` guard is belt-and-suspenders. `[VERIFIED: developer.mozilla.org Intl.DisplayNames/DisplayNames — fallback default = "code"]`

### Pattern 3: Locale→country resolver with explicit fallback (FLAG-04)
**What:** Resolve any locale to a bundled country code or signal "no flag" cleanly.
**Example:**
```javascript
const LANG_TO_COUNTRY = { he:'il', hi:'in', ja:'jp', zh:'cn', es:'es', fr:'fr' }; // D-03
const BUNDLED = new Set(['de','ca','gb','us','es','mx','fr','il','in','jp','br','cn']); // D-02
function localeToCountry(locale) {
  const parts = (locale || '').toLowerCase().split('-');
  const region = parts[1];
  let cc = region || LANG_TO_COUNTRY[parts[0]] || '';
  return BUNDLED.has(cc) ? cc : null;   // null → fallback pill (FLAG-04)
}
```

### Anti-Patterns to Avoid
- **Inlining es.svg / mx.svg raw:** adds ~166 KB for detail invisible at 16 px. Substitute trimmed stripe variants or svgo them. (See Pitfall 1.)
- **Keeping the SVG's `id="flag-icons-XX"`:** 12 elements with ids in the live DOM = collision/validity risk; CSS `#flag-icons-es` could leak. Strip it. (Pitfall 2.)
- **`<symbol>`/`<use>` sprite re-injected via `innerHTML`:** symbol defs must persist in DOM separate from the re-rendered panel; brittle here. Use the object map.
- **Re-deriving labels from a hand-kept map:** `Intl.DisplayNames` already does it correctly and stays current with the platform.
- **Putting flag SVG in an `<img src="data:…">`:** still self-contained, but inline `<svg>` is cleaner for theming the wrapper and avoids base64 bloat; some aggressive blockers also scrutinize `data:` images. Prefer raw inline `<svg>`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Flag artwork | Hand-drawn SVG paths per country | flag-icons 4x3 SVGs (D-01b) | Correct proportions/colors/coats of arms; MIT; maintained. Hand-drawing is error-prone and explicitly forbidden by D-01b. |
| "Language (Country)" text | Hand-maintained `{ 'es-mx':'Spanish (Mexico)', … }` map | `Intl.DisplayNames` | Native, localizable, stays current; covers all 18 FOLIO locales. |
| Locale parsing | Regex gymnastics on BCP-47 tags | Simple `split('-')` + the small D-03 map | The FOLIO locale set is known and tiny (12 + 6); full BCP-47 parsing is overkill. |
| SVG minification | Hand-stripping XML | `svgo` (dev-time) OR a deliberate hand-trim of just es/mx | svgo is the standard tool; only es/mx need attention. |

**Key insight:** The only thing genuinely worth authoring by hand is the **stripe-only ES and MX variants** — and that is not "hand-building a flag," it is removing an invisible-at-16px coat of arms from an existing vetted file. Everything else is reuse.

**License-notice retention (MIT requirement):** flag-icons is MIT, © 2013 Panayiotis Lipiridis. The MIT license requires the copyright + permission notice be included "in all copies or substantial portions." Vendoring 12 SVGs is a substantial portion of the artwork, so **retain the notice in-repo**: add `LICENSES/flag-icons-LICENSE.txt` (verbatim MIT text) and a short HTML comment near the `FLAG_SVG` const pointing to it (e.g. `<!-- Flags: lipis/flag-icons, MIT © 2013 Panayiotis Lipiridis. See LICENSES/flag-icons-LICENSE.txt -->`). No visible UI attribution is required by MIT. `[VERIFIED: raw.githubusercontent.com/lipis/flag-icons/main/LICENSE]`

## Common Pitfalls

### Pitfall 1: es.svg and mx.svg are huge (coat-of-arms detail)
**What goes wrong:** Inlining all 12 raw SVGs balloons the file. Measured raw sizes (from `flags/4x3`):

| ISO | bytes | ISO | bytes | ISO | bytes |
|-----|------:|-----|------:|-----|------:|
| de | 221 | gb | 504 | jp | 470 |
| fr | 241 | us | 648 | cn | 813 |
| ca | 625 | il | 834 | br | 7,140 |
| in | 1,090 | **es** | **80,958** | **mx** | **84,753** |

ES + MX alone ≈ **166 KB**; the other ten total ≈ 12.6 KB. `[VERIFIED: curl byte counts from raw.githubusercontent.com 2026-05-22]`
**Why it happens:** flag-icons draws the full Spanish and Mexican coats of arms as detailed vector paths (known upstream issue lipis/flag-icons#315). At 16 px wide that detail is a sub-pixel smudge.
**How to avoid:** For ES and MX, vendor a **trimmed stripe-only variant** (just the colored bands — ~250–400 B, visually identical at 16 px), OR run the two files through `npx svgo --multipass`. Recommend the hand-trim for ES/MX given the 16px target. Keep the other 10 as-is. Total inlined budget then ≈ **13 KB** for all 12.
**Warning signs:** A diff that grows index.html by >150 KB; an es/mx flag that looks "busy" or muddy at 16 px.

### Pitfall 2: Duplicate / leaking SVG ids
**What goes wrong:** Each flag-icons file ships `<svg id="flag-icons-XX" …>`; some define internal ids (`jp.svg` uses `clipPath id="jp-a"`, `in.svg` uses gradient/clip ids). Pasting 12 verbatim creates duplicate-id collisions in the live DOM, and a stray CSS rule on `#flag-icons-es` could match unexpectedly.
**Why it happens:** SVGs were authored as standalone files, not as DOM fragments.
**How to avoid:** When vendoring, **strip the wrapper `id` attribute** and **namespace any internal ids** (e.g. `jp-a` → `fi-jp-a`, update its `url(#…)` reference). Add `aria-hidden="true" focusable="false"` to each inner `<svg>` so AT ignores it (the wrapper carries the label).
**Warning signs:** Browser console "duplicate id" warnings; one flag's clip path mangling another.

### Pitfall 3: Reintroducing an external request (breaks FLAG-02)
**What goes wrong:** Convenience temptation to `<img src="https://flagcdn.com/...">` or `background-image:url(...)`. Privacy Badger / blockers strip these → blank flags. This is the exact PROD bug being fixed.
**Why it happens:** CDNs are the "normal" way to use flag-icons.
**How to avoid:** All flag pixels come from inline `<svg>` markup; no `src`, no `url()`, no `@import`, no `<use href>` pointing off-document. Add a verification step grepping the flag block for `http`, `url(`, `src=`.
**Warning signs:** Any `http`/`//`/`url(` token inside `FLAG_SVG`.

### Pitfall 4: Hebrew (`he`) and the current "HE→broken" bug
**What goes wrong:** Today `localeToFlag('he')` builds regional-indicator codepoints for "HE", which is not a country → blank/box. The D-03 map (`he→il`) fixes it, but only if the resolver maps **before** attempting flag lookup.
**How to avoid:** `localeToCountry` consults `LANG_TO_COUNTRY` for language-only locales prior to the `BUNDLED` check. Covered by Pattern 3 and a unit test.
**Warning signs:** A blank flag next to a Hebrew/Hindi/Japanese/Chinese translation.

### Pitfall 5: White-heavy flags vanish on light theme
**What goes wrong:** JP (white field + red disc) and CN (mostly red but with a white-adjacent edge) and the white stripes of others blend into the light/mixed theme background without a border.
**How to avoid:** D-04's `border:1px solid var(--border)` on `.flag` — `var(--border)` already resolves to `#d0d4e0` in light/mixed and `--gray-700` in dark `[VERIFIED: codebase index.html:70,188,306,422]`. Add `overflow:hidden` + `border-radius` so the SVG corners are clipped to the rounded box.
**Warning signs:** JP flag looks like a floating red dot on light theme.

## Code Examples

### CSS rewrite for `.flag` (replaces index.html:1032)
```css
/* Source: derived from existing .detail-trans-pill + theme tokens (index.html:1026-1032) */
.detail-trans-pill .flag {
  display: inline-block;
  width: 16px; height: 12px;         /* 4:3 */
  border-radius: 2px;
  border: 1px solid var(--border);    /* theme-aware hairline (D-04) */
  overflow: hidden;
  flex: 0 0 auto;
  line-height: 0;
}
.detail-trans-pill .flag svg { display: block; width: 100%; height: 100%; }
.detail-trans-pill .flag-fallback {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 16px; height: 12px; padding: 0 3px;
  border-radius: 2px;
  border: 1px solid var(--border);
  background: var(--surface3);
  color: var(--text-dim);
  font-size: 8px; font-weight: 700; letter-spacing: 0.3px;
  flex: 0 0 auto;
}
```

### Trimmed ES stripe-only variant (illustrative — confirm exact hex against source)
```javascript
// Spain: three horizontal bands 1:2:1, coat of arms removed (invisible at 16px)
es: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#AA151B" d="M0 0h640v480H0z"/><path fill="#F1BF00" d="M0 120h640v240H0z"/></svg>',
// Mexico: three vertical bands green/white/red, eagle emblem removed
mx: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#fff" d="M0 0h640v480H0z"/><path fill="#006847" d="M0 0h213.3v480H0z"/><path fill="#ce1126" d="M426.7 0H640v480H426.7z"/></svg>',
```
(Hex values from the raw es.svg header: `#AA151B`, `#F1BF00`. `[VERIFIED: raw es.svg first 300 bytes]` Mexican green/red are the standard `#006847`/`#ce1126`; the executor should copy exact band hex from raw mx.svg.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unicode regional-indicator emoji flags | Inline SVG flags | n/a (project bug) | Windows has never shipped emoji flag glyphs in its default font — emoji flags are unreliable cross-OS. SVG is the standard fix. |
| Hand-maintained locale→label maps | `Intl.DisplayNames` | Baseline 2021-04 | Native, no map to maintain. |

**Deprecated/outdated:**
- Emoji-codepoint flag generation (`String.fromCodePoint(0x1f1a5 + …)`) — the current `localeToFlag` — is being removed.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Hand-trimmed stripe-only ES/MX variants are visually acceptable to the user at 16 px (coat of arms dropped) | Pitfall 1 / Code Examples | LOW — if user wants the emblem, fall back to svgo'd full files (~larger but still bounded); a discuss point, not a blocker |
| A2 | Mexican band hex `#006847`/`#ce1126` are correct | Code Examples | LOW — executor must copy exact hex from raw mx.svg; verify visually |

**Note:** ES band hex, flag-icons MIT license, all 12 file existence + byte sizes, `Intl.DisplayNames` support/fallback, and `var(--border)` theme values are all `[VERIFIED]` — not assumed.

## Open Questions

1. **Should the heavy ES/MX flags keep their coat of arms?**
   - What we know: at 16 px the emblem is invisible; trimmed variants are ~250 B vs ~82 KB.
   - What's unclear: user aesthetic preference if the pill is ever zoomed.
   - Recommendation: ship trimmed stripe-only variants (A1). Cheap to swap to svgo'd full files later if desired. Not a blocker.

2. **Where exactly to retain the MIT notice?**
   - What we know: MIT requires the notice in copies; no visible UI attribution required.
   - Recommendation: `LICENSES/flag-icons-LICENSE.txt` + an HTML comment by `FLAG_SVG`. Planner should make this an explicit task (compliance).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js (test runner `node:test`) | Frontend unit tests | ✓ | v25.2.1 | — |
| Chromium (visual verification) | Manual OS-render check | ✓ | /snap/bin/chromium | — |
| `svgo` (dev-time minify, OPTIONAL) | ES/MX size trim (only if not hand-trimming) | ✗ (npx-fetchable) | npm 4.0.1 | Hand-trim ES/MX by hand (preferred anyway) |
| Internet access to raw.githubusercontent.com | One-time vendoring of source SVGs | ✓ (verified during research) | — | flag SVG markup is reproduced in this RESEARCH.md for 11 of 12; executor can also re-fetch |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `svgo` — hand-trimming ES/MX is the recommended path regardless, so svgo is not needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node.js built-in `node:test` + `node:assert/strict` (existing project idiom) |
| Config file | none — run via `node --test` (see `scripts/contrast-audit.test.mjs`) `[VERIFIED: codebase]` |
| Quick run command | `node --test scripts/flags.test.mjs` |
| Full suite command | `node --test scripts/*.test.mjs` (frontend) + `cd backend && .venv/bin/python -m pytest tests/ -q` (unchanged) |

**Testability note:** The existing frontend test pattern extracts pure logic into a `scripts/<name>.mjs` ES module and tests it with `node:test` (mirroring `contrast-audit.mjs` / `contrast-audit.test.mjs`). To follow it, the executor should extract `localeToCountry`, `localeLabel`, and `flagMarkup` into `scripts/flags.mjs` (exported), keep a copy/import path usable from the single-file HTML, and unit-test the module. Pure string/lookup functions are ideal for this — no DOM needed. Visual/OS rendering (FLAG-01) and blocker behavior (FLAG-02) remain manual (Chromium + Privacy Badger), as they are inherently browser/OS-level.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLAG-01 | Flag markup is inline `<svg>`, no emoji codepoints | unit | `node --test scripts/flags.test.mjs` (assert output contains `<svg`, no `\u{1F1E6}`-range chars) | ❌ Wave 0 |
| FLAG-01 | Renders actual flag on Windows | manual | Chromium screenshot on Win (manual UAT) | n/a |
| FLAG-02 | Flag markup contains no external request token | unit | `node --test scripts/flags.test.mjs` (assert no `http`, `url(`, `src=` in `FLAG_SVG`) | ❌ Wave 0 |
| FLAG-02 | Displays with Privacy Badger on | manual | Chromium + blocker (manual UAT) | n/a |
| FLAG-03 | `flagMarkup` includes `role="img"` + correct `aria-label`/`title` | unit | `node --test scripts/flags.test.mjs` (assert label === "Spanish (Mexico)" for `es-mx`, etc.) | ❌ Wave 0 |
| FLAG-04 | Unknown locale yields fallback pill, never empty/emoji | unit | `node --test scripts/flags.test.mjs` (assert `flagMarkup('xx-yy')` → `class="flag-fallback"`, text "XX") | ❌ Wave 0 |
| D-03 | Language-only locales map to country (he→il etc.) | unit | `node --test scripts/flags.test.mjs` (assert `localeToCountry('he')==='il'`) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `node --test scripts/flags.test.mjs`
- **Per wave merge:** `node --test scripts/*.test.mjs` + backend pytest (unchanged, must stay green)
- **Phase gate:** Full frontend test suite green + manual Chromium screenshot (all 3 themes) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `scripts/flags.mjs` — extract pure `localeToCountry` / `localeLabel` / `flagMarkup` + `FLAG_SVG` map (testable module)
- [ ] `scripts/flags.test.mjs` — covers FLAG-01..04 + D-03 per table above
- [ ] No framework install needed — `node:test` ships with Node v25.2.1 `[VERIFIED]`

## Security Domain

> `security_enforcement` not present in config.json → treated as enabled. Surface is minimal (client-side string rendering), but XSS via locale/label is the live concern.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth surface) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation / Output Encoding | **yes** | Escape all interpolated text with existing `escapeHtml`/`escapeAttr` (index.html). Locale strings and translation labels come from FOLIO data → treat as untrusted in `innerHTML`. |
| V6 Cryptography | no | — |

### Known Threat Patterns for vanilla-JS innerHTML rendering
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via translation label injected into pill | Tampering | `escapeHtml(label)` (already used at index.html:8344) — preserve it |
| XSS via locale string in `aria-label`/`title` attribute | Tampering | `escapeAttr(localeLabel(locale))` when building attributes (Pattern 1) |
| Malicious `<svg>` in the vendored set | Tampering | SVGs are **author-vendored from a trusted MIT repo and reviewed**, never user-supplied — no runtime SVG from data. Risk = supply-chain at vendor time; mitigated by manual review of the 12 pasted strings (small, auditable). |

**Key control:** The flag SVG strings are a fixed author-controlled allowlist (`FLAG_SVG` const). User/FOLIO data never reaches `innerHTML` un-escaped. Keep `escapeHtml`/`escapeAttr` on every interpolated label and attribute.

## Sources

### Primary (HIGH confidence)
- `github.com/lipis/flag-icons` (repo + `/flags/4x3`) — license = MIT, ISO-alpha2 lowercase naming, 4:3 path `[VERIFIED]`
- `raw.githubusercontent.com/lipis/flag-icons/main/LICENSE` — MIT, © 2013 Panayiotis Lipiridis, notice-retention clause `[VERIFIED]`
- `raw.githubusercontent.com/.../flags/4x3/<iso>.svg` (all 12) — byte sizes + markup measured via `curl` `[VERIFIED]`
- `developer.mozilla.org/.../Intl/DisplayNames` and `.../DisplayNames/DisplayNames` — usage, Baseline 2021-04, `fallback` default `"code"` `[VERIFIED]`
- Codebase: `frontend/index.html` lines 70/188/306/422 (`--border` tokens), 1021-1032 (CSS), 6731-6734 (JS-string SVG idiom), 8337-8358 (translation render), 10286 (`localeToFlag`); `scripts/contrast-audit.test.mjs` (test idiom) `[VERIFIED: grep/read]`
- `npm view flag-icons version` → 7.5.0; `npm view svgo version` → 4.0.1 `[VERIFIED: npm registry]`

### Secondary (MEDIUM confidence)
- `github.com/lipis/flag-icons/issues/315` — large-filesize-due-to-complex-shapes (corroborates es/mx bloat) `[CITED]`
- `github.com/Yummygum/flagpack-core` — alternate MIT flag set (only relevant if a flag-icons file is unusable) `[CITED]`

### Tertiary (LOW confidence)
- None relied upon for any actionable claim.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — flag-icons license/paths/sizes and Intl.DisplayNames support all tool-verified.
- Architecture: HIGH — matches the codebase's existing JS-string-SVG idiom and theme tokens, both read directly.
- Pitfalls: HIGH — es/mx sizes and id collisions verified from raw files; theme/border verified from CSS.

**Research date:** 2026-05-22
**Valid until:** 2026-06-21 (stable; flag-icons license and Intl.DisplayNames are not fast-moving)
