import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  FLAG_SVG,
  LANG_TO_COUNTRY,
  localeToCountry,
  localeLabel,
  flagMarkup,
} from './flags.mjs';

// ── localeToCountry: region resolution (FLAG-01) ──────────────────────────
test('localeToCountry resolves region from full locale', () => {
  assert.equal(localeToCountry('es-mx'), 'mx');
  assert.equal(localeToCountry('en-gb'), 'gb');
  assert.equal(localeToCountry('de-de'), 'de');
  assert.equal(localeToCountry('en-us'), 'us');
  assert.equal(localeToCountry('pt-br'), 'br');
});

test('localeToCountry is case-insensitive', () => {
  assert.equal(localeToCountry('ES-MX'), 'mx');
  assert.equal(localeToCountry('En-Gb'), 'gb');
});

// ── D-03: language-only locales map to a representative country ───────────
test('D-03: language-only locales map to representative country', () => {
  assert.equal(localeToCountry('he'), 'il');
  assert.equal(localeToCountry('hi'), 'in');
  assert.equal(localeToCountry('ja'), 'jp');
  assert.equal(localeToCountry('zh'), 'cn');
  assert.equal(localeToCountry('es'), 'es');
  assert.equal(localeToCountry('fr'), 'fr');
});

test('D-03: LANG_TO_COUNTRY map exposes the six representative mappings', () => {
  assert.deepEqual(LANG_TO_COUNTRY, {
    he: 'il', hi: 'in', ja: 'jp', zh: 'cn', es: 'es', fr: 'fr',
  });
});

// ── FLAG-04: unbundled locale resolves to null (fallback path) ────────────
test('FLAG-04: unbundled locale returns null', () => {
  assert.equal(localeToCountry('xx-yy'), null);
  assert.equal(localeToCountry('en-au'), null); // au not in bundle
  assert.equal(localeToCountry(''), null);
  assert.equal(localeToCountry('zz'), null);
});

// ── FLAG_SVG map: 12-key allowlist, all inline SVG, ids stripped ──────────
test('FLAG_SVG has exactly the 12 bundled country keys', () => {
  const expected = ['de', 'ca', 'gb', 'us', 'es', 'mx', 'fr', 'il', 'in', 'jp', 'br', 'cn'];
  assert.deepEqual(Object.keys(FLAG_SVG).sort(), expected.sort());
});

test('FLAG-01: every FLAG_SVG value is an inline <svg> with no flag-icons id', () => {
  for (const [cc, svg] of Object.entries(FLAG_SVG)) {
    assert.ok(svg.startsWith('<svg'), `${cc} should start with <svg`);
    assert.ok(!svg.includes('id="flag-icons'), `${cc} should not keep wrapper id`);
  }
});

// ── FLAG-02: no external-request tokens anywhere in FLAG_SVG ───────────────
test('FLAG-02: FLAG_SVG contains no external-request tokens', () => {
  const tokens = ['http', 'url(', 'src=', '<use '];
  for (const [cc, svg] of Object.entries(FLAG_SVG)) {
    for (const tok of tokens) {
      assert.ok(!svg.includes(tok), `${cc} must not contain "${tok}"`);
    }
  }
});

// ── ES / MX are trimmed stripe-only variants (Pitfall 1) ──────────────────
test('ES and MX are trimmed stripe variants under 1 KB with no emblem', () => {
  assert.ok(FLAG_SVG.es.length < 1024, `es should be < 1 KB, got ${FLAG_SVG.es.length}`);
  assert.ok(FLAG_SVG.mx.length < 1024, `mx should be < 1 KB, got ${FLAG_SVG.mx.length}`);
  // stripe-only: no coat-of-arms <g>/<circle> emblem, no <defs>
  assert.ok(!FLAG_SVG.es.includes('<g'), 'es should be stripe-only (no <g>)');
  assert.ok(!FLAG_SVG.mx.includes('<g'), 'mx should be stripe-only (no <g>)');
  assert.ok(!FLAG_SVG.mx.includes('<circle'), 'mx should be stripe-only (no <circle>)');
  // exact band hex from source
  assert.ok(FLAG_SVG.es.includes('#AA151B'), 'es red band hex');
  assert.ok(FLAG_SVG.es.includes('#F1BF00'), 'es yellow band hex');
  assert.ok(FLAG_SVG.mx.includes('#006847'), 'mx green band hex');
  assert.ok(FLAG_SVG.mx.includes('#ce1126'), 'mx red band hex');
});

// ── FLAG-03: accessible "Language (Country)" labels via Intl.DisplayNames ──
test('FLAG-03: localeLabel composes "Language (Country)"', () => {
  assert.equal(localeLabel('es-mx'), 'Spanish (Mexico)');
  assert.equal(localeLabel('en-gb'), 'English (United Kingdom)');
  assert.equal(localeLabel('en-us'), 'English (United States)');
  assert.equal(localeLabel('de-de'), 'German (Germany)');
});

test('FLAG-03 + D-03: language-only labels resolve country', () => {
  assert.equal(localeLabel('he'), 'Hebrew (Israel)');
  assert.equal(localeLabel('ja'), 'Japanese (Japan)');
  assert.equal(localeLabel('zh'), 'Chinese (China)');
});

// ── flagMarkup: SVG branch (FLAG-01) ──────────────────────────────────────
test('FLAG-01: flagMarkup returns labeled inline-SVG span for bundled locale', () => {
  const out = flagMarkup('es-mx');
  assert.ok(out.includes('class="flag"'), 'has flag class');
  assert.ok(out.includes('role="img"'), 'has role=img');
  assert.ok(out.includes('aria-label="Spanish (Mexico)"'), 'has aria-label');
  assert.ok(out.includes('title="Spanish (Mexico)"'), 'has title');
  assert.ok(out.includes('<svg'), 'has inline svg');
  // no emoji regional-indicator codepoints (U+1F1E6..U+1F1FF)
  for (const ch of out) {
    const cp = ch.codePointAt(0);
    assert.ok(cp < 0x1f1e6 || cp > 0x1f1ff, `must not contain regional-indicator codepoint`);
  }
});

test('FLAG-01: language-only he renders the IL flag svg (no blank)', () => {
  const out = flagMarkup('he');
  assert.ok(out.includes('class="flag"'), 'has flag class');
  assert.ok(out.includes('<svg'), 'has inline svg');
  assert.ok(out.includes('aria-label="Hebrew (Israel)"'), 'labeled IL');
});

// ── flagMarkup: fallback branch (FLAG-04) ─────────────────────────────────
test('FLAG-04: flagMarkup returns styled code pill for unbundled locale', () => {
  const out = flagMarkup('xx-yy');
  assert.ok(out.includes('class="flag-fallback"'), 'has flag-fallback class');
  assert.ok(out.includes('role="img"'), 'has role=img');
  assert.ok(out.includes('aria-label='), 'has an aria-label');
  assert.ok(out.includes('XX'), 'shows uppercased 2-letter code');
  assert.ok(!out.includes('<svg'), 'fallback is never an svg');
});

test('FLAG-04: fallback uses first 2 letters uppercased, never empty', () => {
  // unbundled region -> falls back to the language part (en-au -> EN)
  assert.ok(flagMarkup('en-au').includes('EN'), 'au not bundled -> EN pill');
  assert.ok(flagMarkup('en-au').includes('class="flag-fallback"'));
  // fully-unknown locale -> first 2 letters of the language code
  assert.ok(flagMarkup('qz').includes('QZ'), 'unknown -> QZ pill');
  assert.ok(flagMarkup('qz').includes('class="flag-fallback"'));
});
