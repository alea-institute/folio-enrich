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
