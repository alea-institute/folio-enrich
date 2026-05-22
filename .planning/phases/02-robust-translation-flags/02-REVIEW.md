---
phase: 02-robust-translation-flags
reviewed: 2026-05-22T22:19:05Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - scripts/flags.mjs
  - scripts/flags.test.mjs
  - frontend/index.html
  - LICENSES/flag-icons-LICENSE.txt
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-22T22:19:05Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the robust-translation-flags implementation: the new pure module
`scripts/flags.mjs` (FLAG_SVG map + `localeToCountry`/`localeLabel`/`flagMarkup`
helpers), its node:test suite `scripts/flags.test.mjs`, the inlined copy in
`frontend/index.html` (the `makePill` wiring, the `.flag`/`.flag-fallback` CSS,
and the removed `localeToFlag`), and the new `LICENSES/flag-icons-LICENSE.txt`.

The security posture is strong. I independently verified the two FLAG-02 and
byte-identical claims rather than trusting them:

- **FLAG-02 (no external tokens):** Confirmed zero occurrences of `http`,
  `url(`, `src=`, or `<use ` in all 12 SVGs, in **both** the module and the
  inlined HTML block. The marker/`<use>` star fields (US, CN) are fully
  expanded to explicit `<path>`, and the clipPath/`url(#)` wrappers (IL, JP)
  are dropped. The guarantee holds.
- **Byte-identical inlining:** All 12 FLAG_SVG values are byte-for-byte
  identical between `scripts/flags.mjs` and `frontend/index.html`, so the unit
  tests remain authoritative.
- **XSS surface:** `flagMarkup` interpolates only `escapeAttr(label)` (into the
  `aria-label`/`title` attributes) and `escapeHtml(code)` (into the fallback
  pill text). The SVG strings themselves are trusted compile-time constants
  from the allowlisted `FLAG_SVG` map keyed by a validated 2-letter code — no
  user/locale string ever reaches the SVG body. The HTML's pre-existing
  `escapeHtml`/`escapeAttr` are semantically equivalent to the module's. No
  injection path found.
- **`localeToFlag` removal:** No dangling references remain in the HTML.
- **Tests:** All 15 tests pass via `node --test scripts/flags.test.mjs`.

No blockers. Findings below are robustness and accessibility edge cases that
real FOLIO ontology data (well-formed locale keys like `es-mx`, `he`) is
unlikely to trigger, plus minor quality items.

## Warnings

### WR-01: Empty/malformed locale produces an empty `aria-label` on a `role="img"` element

**File:** `scripts/flags.mjs:90-99` (and inlined `frontend/index.html:10346-10355`)
**Issue:** When `locale` is empty/null, `localeLabel('')` returns `''`, so
`flagMarkup('')` emits:
`<span class="flag-fallback" role="img" aria-label="" title="">?</span>`.
An element with `role="img"` and an empty `aria-label` is an accessibility
defect — screen readers either skip it or announce a bare "image" with no
meaning, and the visible `?` glyph has no accessible name. The `if (!s) return ''`
guards in the escape helpers turn the empty label into a literally empty
attribute rather than something descriptive. Translation keys come from FOLIO
ontology data (`dict[str, str]`) so an empty key is unlikely in practice, but
the function is exported and unit-tested as a general-purpose helper and should
never emit an unlabeled `role="img"`.
**Fix:** Fall back to the displayed code (or a generic word) when the label is
empty, so the accessible name is never blank:
```js
export function flagMarkup(locale) {
  const cc = localeToCountry(locale);
  const code = (cc || (locale || '').split('-')[0] || '?').slice(0, 2).toUpperCase();
  const label = localeLabel(locale) || code;   // never empty
  const svg = cc && FLAG_SVG[cc];
  if (svg) {
    return `<span class="flag" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${svg}</span>`;
  }
  return `<span class="flag-fallback" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${escapeHtml(code)}</span>`;
}
```

### WR-02: Leading-hyphen locale resolves to a real flag with a blank language name

**File:** `scripts/flags.mjs:67-86` (and inlined `frontend/index.html:10324-10344`)
**Issue:** `split('-')` does not validate the language segment. For input
`'-us'`, `parts[0]` is `''` and `parts[1]` is `'us'`, so `localeToCountry('-us')`
returns `'us'` and `localeLabel('-us')` returns `" (United States)"` — a US flag
labeled with a leading-space, empty-language string. Similarly `'und'` (the BCP-47
"undetermined" code) yields `localeLabel('und') === 'root'` because
`Intl.DisplayNames` maps `und` to "root", which is meaningless to a user. These
are degenerate but show the resolver trusts the shape of its input. Combined with
WR-01, a malformed locale can render a flag whose only label is whitespace.
**Fix:** Require a non-empty language segment before composing the label, and
treat `und`/`root` as no-language:
```js
export function localeLabel(locale) {
  const parts = (locale || '').toLowerCase().split('-');
  const lang = parts[0] || '';
  let out;
  try { out = (lang && lang !== 'und') ? (_langDN.of(lang) || lang) : ''; }
  catch { out = lang; }
  const cc = (parts[1] || LANG_TO_COUNTRY[lang] || '').toUpperCase();
  if (cc) {
    let country;
    try { country = _regionDN.of(cc); } catch { country = null; }
    if (country && country !== cc) out = out ? `${out} (${country})` : country;
  }
  return out;
}
```

## Info

### IN-01: Dead namespaced ids in the India flag SVG

**File:** `scripts/flags.mjs:33` (and inlined `frontend/index.html`, `in:` entry)
**Issue:** The `in` SVG defines `id="fi-in-d"`, `fi-in-c`, `fi-in-b`, `fi-in-a`
but nothing references them — there is no surviving `url(#fi-in-…)` or `<use>`
(verified). The ids are vendoring leftovers (the comment at lines 11-14 says
internal ids were namespaced specifically so `url(#…)` refs could be updated, but
here the refs were removed entirely). Beyond being dead markup, these are
**global** DOM ids once injected via `innerHTML`; if a Hindi (`hi`/`in`)
translation pill is rendered more than once on a page they become duplicate ids
(invalid HTML, though harmless since unreferenced).
**Fix:** Drop the four unused `id="…"` attributes from the `in` SVG (in both the
module and the byte-identical HTML copy), or keep them only if a future spec
needs the chakra spokes referenced.

### IN-02: `escapeHtml`/`escapeAttr` are defined twice (module + HTML)

**File:** `scripts/flags.mjs:52-59`; `frontend/index.html:10371-10379`
**Issue:** The module ships its own `escapeHtml`/`escapeAttr` "to keep node:test
standalone," and the HTML keeps its pre-existing pair. They are intentionally
semantically equivalent today, but this is a maintenance hazard: a future fix to
one (e.g. also escaping backticks or `/`) silently diverges from the other, and
the unit tests would still pass against the module copy while the shipped HTML
behaves differently. This is an accepted tradeoff of the no-build single-file
architecture, but worth a guard.
**Fix:** Add a comment cross-referencing both definitions (the module already
notes it "mirrors" the HTML; add the reciprocal note in the HTML), or a tiny test
asserting the two escape implementations produce identical output for a shared
fixture string.

### IN-03: No automated guard enforces the byte-identical inlining invariant

**File:** `scripts/flags.mjs:4-6` (the invariant); `scripts/flags.test.mjs` (where a guard belongs)
**Issue:** Correctness of the shipped flags depends entirely on the module and
the HTML staying byte-identical, but nothing enforces it. The test suite imports
only `flags.mjs`; it never reads `frontend/index.html`. A future edit to one
copy (a color tweak, a new flag) would leave the tests green while the actual UI
drifts. I verified them identical today, but the invariant is unprotected going
forward.
**Fix:** Add a test that reads `frontend/index.html`, extracts each `cc: '<svg…>'`
entry, and asserts it equals `FLAG_SVG[cc]` from the module — turning the
"keep byte-identical" comment into an enforced check.

### IN-04: `Intl.DisplayNames` assumed present with no fallback

**File:** `scripts/flags.mjs:62-63` (and inlined `frontend/index.html:10321-10322`)
**Issue:** `_langDN`/`_regionDN` are constructed at module load with no
feature-detection. `Intl.DisplayNames` is widely supported in current browsers
and Node, so this is low risk, but on an unsupported runtime the `new
Intl.DisplayNames(...)` call throws at module/script load time — which, inlined
into `index.html`, would abort the surrounding script block rather than degrade
gracefully. The per-call `try/catch` inside `localeLabel` does not cover the
constructor.
**Fix:** Guard construction and degrade to the raw code, e.g.
`const _langDN = (typeof Intl !== 'undefined' && Intl.DisplayNames) ? new Intl.DisplayNames(['en'], { type: 'language' }) : null;`
and have `localeLabel` fall back to the lowercase segments when `_langDN` is null.

---

_Reviewed: 2026-05-22T22:19:05Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
