import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  hexToRgb,
  relativeLuminance,
  contrastRatio,
  mixColors,
  parseCssVariables,
  resolveVariable,
} from './contrast-audit.mjs';

test('hexToRgb parses #1a1d27 to {r:26, g:29, b:39}', () => {
  const result = hexToRgb('#1a1d27');
  assert.equal(result.r, 26);
  assert.equal(result.g, 29);
  assert.equal(result.b, 39);
});

test('relativeLuminance of white is 1.0', () => {
  const L = relativeLuminance({ r: 255, g: 255, b: 255 });
  assert.ok(Math.abs(L - 1.0) < 0.001, `expected 1.0, got ${L}`);
});

test('relativeLuminance of black is 0.0', () => {
  const L = relativeLuminance({ r: 0, g: 0, b: 0 });
  assert.ok(Math.abs(L - 0.0) < 0.001, `expected 0.0, got ${L}`);
});

test('contrastRatio of white vs black is 21', () => {
  const ratio = contrastRatio('#ffffff', '#000000');
  assert.ok(Math.abs(ratio - 21) < 0.1, `expected 21, got ${ratio}`);
});

test('contrastRatio of #1a1d27 on #ffffff is >= 15', () => {
  const ratio = contrastRatio('#1a1d27', '#ffffff');
  assert.ok(ratio >= 15.0, `expected >=15, got ${ratio}`);
});

test('mixColors blends 12% foreground onto background', () => {
  // 12% of #5ec4d4 (94,196,212) + 88% of #0f1117 (15,17,23)
  // r: 0.12*94 + 0.88*15 = 11.28 + 13.2 = 24.48 → 24
  // g: 0.12*196 + 0.88*17 = 23.52 + 14.96 = 38.48 → 38
  // b: 0.12*212 + 0.88*23 = 25.44 + 20.24 = 45.68 → 46
  const result = mixColors('#5ec4d4', '#0f1117', 0.12);
  const rgb = hexToRgb(result);
  assert.ok(Math.abs(rgb.r - 24) <= 1, `r expected ~24, got ${rgb.r}`);
  assert.ok(Math.abs(rgb.g - 38) <= 1, `g expected ~38, got ${rgb.g}`);
  assert.ok(Math.abs(rgb.b - 46) <= 1, `b expected ~46, got ${rgb.b}`);
});

test('parseCssVariables extracts --name: value pairs from a block', () => {
  const css = `
    --bg: #0f1117;
    --text: #e4e6f0;
    --accent: var(--blue-400);
  `;
  const map = parseCssVariables(css);
  assert.equal(map.get('--bg'), '#0f1117');
  assert.equal(map.get('--text'), '#e4e6f0');
  assert.equal(map.get('--accent'), 'var(--blue-400)');
});

test('resolveVariable follows var(--x) chain through themeMap and paletteMap', () => {
  const palette = new Map([
    ['--gray-200', '#e4e6f0'],
  ]);
  const theme = new Map([
    ['--text', 'var(--gray-200)'],
  ]);
  const resolved = resolveVariable('--text', theme, palette);
  assert.equal(resolved, '#e4e6f0');
});

// ── STATUS-05: status-icon 3:1 graphical-object floor (WCAG 1.4.11) ──────────
// These pin the computed Light-theme ratios (03-RESEARCH.md:294, 03-UI-SPEC.md:72-77)
// so the mandatory --text stroke fallback for status icons cannot regress.
// The --text stroke clears 3:1 (≥13:1); solid green/orange fills FAIL — proving
// the stroke fallback is mandatory, not optional. Exact v1.0 hex literals are
// pinned here: --text #1a1d27, --green #16a34a, --orange #d97706,
// --surface2 #eceef4, --surface3 #e2e5ee.

test('STATUS-05: Light --text #1a1d27 stroke clears 3:1 on --surface2 #eceef4', () => {
  const ratio = contrastRatio('#1a1d27', '#eceef4');
  assert.ok(ratio >= 3.0, `--text stroke must clear 3:1, got ${ratio.toFixed(2)}:1`);
});

test('STATUS-05: Light --text #1a1d27 stroke clears 3:1 on --surface3 #e2e5ee', () => {
  const ratio = contrastRatio('#1a1d27', '#e2e5ee');
  assert.ok(ratio >= 3.0, `--text stroke must clear 3:1, got ${ratio.toFixed(2)}:1`);
});

test('STATUS-05: Light solid --green #16a34a FAILS 3:1 on --surface2 #eceef4 (stroke fallback mandatory)', () => {
  const ratio = contrastRatio('#16a34a', '#eceef4');
  assert.ok(ratio < 3.0, `solid green must fail 3:1 (~2.84:1), got ${ratio.toFixed(2)}:1`);
});

test('STATUS-05: Light solid --orange #d97706 FAILS 3:1 on --surface2 #eceef4 (stroke fallback mandatory)', () => {
  const ratio = contrastRatio('#d97706', '#eceef4');
  assert.ok(ratio < 3.0, `solid orange must fail 3:1 (~2.75:1), got ${ratio.toFixed(2)}:1`);
});
