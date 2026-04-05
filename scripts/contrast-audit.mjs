#!/usr/bin/env node
// WCAG AA Contrast Audit for frontend/index.html
// Zero-dependency Node.js script — parses CSS custom properties and
// computes contrast ratios per theme.

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// ── WCAG Math ──────────────────────────────────────────────────────────

export function hexToRgb(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3
    ? h.split('').map(c => c + c).join('')
    : h.padEnd(6, '0').slice(0, 6);
  return {
    r: parseInt(full.slice(0, 2), 16),
    g: parseInt(full.slice(2, 4), 16),
    b: parseInt(full.slice(4, 6), 16),
  };
}

function rgbToHex({ r, g, b }) {
  const c = (n) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, '0');
  return '#' + c(r) + c(g) + c(b);
}

function gammaCorrect(c) {
  // sRGB channel (0-1) to linear (WCAG formula)
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

export function relativeLuminance({ r, g, b }) {
  // WCAG 2.1 relative luminance
  const R = gammaCorrect(r / 255);
  const G = gammaCorrect(g / 255);
  const B = gammaCorrect(b / 255);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

export function contrastRatio(fgHex, bgHex) {
  const L1 = relativeLuminance(hexToRgb(fgHex));
  const L2 = relativeLuminance(hexToRgb(bgHex));
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

export function mixColors(fgHex, bgHex, fgFraction) {
  // Alpha-composite fg onto bg: result = fg*alpha + bg*(1-alpha)
  const fg = hexToRgb(fgHex);
  const bg = hexToRgb(bgHex);
  const bgFraction = 1 - fgFraction;
  return rgbToHex({
    r: fg.r * fgFraction + bg.r * bgFraction,
    g: fg.g * fgFraction + bg.g * bgFraction,
    b: fg.b * fgFraction + bg.b * bgFraction,
  });
}

// ── CSS Parsing ────────────────────────────────────────────────────────

export function parseCssVariables(cssBlock) {
  const map = new Map();
  const lines = cssBlock.split('\n');
  for (const line of lines) {
    // Match: --name: value;  (strip leading whitespace, inline comments)
    const m = line.match(/^\s*(--[a-z0-9-]+)\s*:\s*([^;]+?)\s*(?:;|$)/i);
    if (m) {
      const name = m[1];
      const value = m[2].trim().replace(/\/\*.*?\*\/\s*$/, '').trim();
      map.set(name, value);
    }
  }
  return map;
}

export function resolveVariable(name, themeMap, paletteMap, depth = 0) {
  if (depth > 8) return null; // safety
  const value = themeMap.get(name) ?? paletteMap.get(name);
  if (!value) return null;
  // Skip rgba and color-mix values (not hex)
  if (value.startsWith('rgba(') || value.startsWith('color-mix(')) return null;
  // Resolve var(--x) references
  const varMatch = value.match(/^var\((--[a-z0-9-]+)\)$/i);
  if (varMatch) {
    return resolveVariable(varMatch[1], themeMap, paletteMap, depth + 1);
  }
  // Must be hex
  if (value.startsWith('#')) return value;
  return null;
}

// ── Audit ──────────────────────────────────────────────────────────────

const TEXT_TOKENS = ['--text', '--text-dim', '--accent', '--accent-dim'];
const BG_TOKENS = ['--bg', '--surface', '--surface2', '--surface3'];
const BRANCH_NAMES = [
  'actor-player', 'area-of-law', 'asset-type', 'communication-modality',
  'currency', 'data-format', 'document-artifact', 'document-metadata',
  'engagement-terms', 'event', 'financial-concepts', 'folio-type',
  'forums-venues', 'governmental-body', 'industry', 'language',
  'legal-authorities', 'legal-entity', 'legal-use-cases', 'location',
  'matter-narrative', 'matter-narrative-format', 'objectives', 'service',
  'standards-compatibility', 'status', 'system-identifiers', 'default',
];

function classify(ratio) {
  if (ratio >= 4.5) return 'PASS';
  if (ratio >= 3.0) return 'LARGE-ONLY';
  return 'FAIL';
}

function extractBlock(html, regex) {
  const m = html.match(regex);
  return m ? m[1] : '';
}

function buildReport(results, branchResults, failing, recommendations) {
  const now = new Date().toISOString();
  let md = `# Phase 03 WCAG Contrast Audit Report\n\n`;
  md += `**Generated:** ${now}\n`;
  md += `**Script:** scripts/contrast-audit.mjs\n`;
  md += `**Thresholds:** Body text 4.5:1 (AA), Large text 3:1 (AA), Target margin 5.5:1 per D-04\n\n`;

  // Summary
  md += `## Summary\n\n`;
  md += `| Theme | Total Pairs | Pass | Large-Only | Fail |\n`;
  md += `|-------|-------------|------|------------|------|\n`;
  const summary = {};
  for (const r of results) {
    if (!summary[r.theme]) summary[r.theme] = { total: 0, pass: 0, large: 0, fail: 0 };
    summary[r.theme].total++;
    if (r.status === 'PASS') summary[r.theme].pass++;
    else if (r.status === 'LARGE-ONLY') summary[r.theme].large++;
    else summary[r.theme].fail++;
  }
  for (const theme of Object.keys(summary)) {
    const s = summary[theme];
    md += `| ${theme} | ${s.total} | ${s.pass} | ${s.large} | ${s.fail} |\n`;
  }
  md += `\n`;

  // Text-on-Background Results
  md += `## Text-on-Background Results\n\n`;
  const themes = [...new Set(results.map(r => r.theme))];
  for (const theme of themes) {
    md += `### ${theme}\n\n`;
    md += `| Foreground | Background | FG Hex | BG Hex | Ratio | Status |\n`;
    md += `|-----------|-----------|--------|--------|-------|--------|\n`;
    for (const r of results.filter(x => x.theme === theme)) {
      md += `| ${r.fg} | ${r.bg} | ${r.fgHex} | ${r.bgHex} | ${r.ratio.toFixed(2)}:1 | ${r.status} |\n`;
    }
    md += `\n`;
  }

  // Branch Tint Results
  md += `## Branch Tint Results\n\n`;
  const branchThemes = [...new Set(branchResults.map(r => r.theme))];
  for (const theme of branchThemes) {
    md += `### ${theme}\n\n`;
    md += `| Branch | Base BG | Effective BG | Ratio vs --text | Status |\n`;
    md += `|--------|---------|--------------|-----------------|--------|\n`;
    for (const r of branchResults.filter(x => x.theme === theme)) {
      md += `| ${r.branch} | ${r.baseBg} | ${r.effectiveBg} | ${r.ratio.toFixed(2)}:1 | ${r.status} |\n`;
    }
    md += `\n`;
  }

  // Failing Pairs
  md += `## Failing Pairs\n\n`;
  if (failing.length === 0) {
    md += `None — all pairs meet WCAG AA (4.5:1).\n\n`;
  } else {
    for (const f of failing) {
      md += `- [${f.theme}] ${f.fg} on ${f.bg}: ${f.ratio.toFixed(2)}:1 (need: 4.5:1)\n`;
    }
    md += `\n`;
  }

  // Recommended Fixes
  md += `## Recommended Fixes\n\n`;
  if (recommendations.length === 0) {
    md += `None needed.\n`;
  } else {
    for (const rec of recommendations) {
      md += `- ${rec}\n`;
    }
  }

  return md;
}

export async function runAudit() {
  const projectRoot = path.resolve(fileURLToPath(import.meta.url), '..', '..');
  const htmlPath = path.join(projectRoot, 'frontend/index.html');
  const reportPath = path.join(projectRoot, '.planning/phases/03-accessibility-component-polish/03-AUDIT-REPORT.md');

  const html = readFileSync(htmlPath, 'utf8');

  // Extract :root palette
  const rootBlock = extractBlock(html, /:root\s*\{([^}]+)\}/);
  const paletteMap = parseCssVariables(rootBlock);

  // Extract theme blocks
  const themes = ['dark', 'light', 'mixed'];
  const themeMaps = {};
  for (const theme of themes) {
    const block = extractBlock(html, new RegExp(`\\[data-theme="${theme}"\\]\\s*\\{([^}]+)\\}`));
    themeMaps[theme] = parseCssVariables(block);
  }

  // Extract mixed light overrides block
  const mixedLightBlock = extractBlock(
    html,
    /\[data-theme="mixed"\]\s*\.panel-right[^{]*\{([^}]+)\}/
  );
  themeMaps['mixed-light'] = parseCssVariables(mixedLightBlock);
  // Mixed-light inherits from mixed for missing tokens
  for (const [k, v] of themeMaps['mixed']) {
    if (!themeMaps['mixed-light'].has(k)) {
      themeMaps['mixed-light'].set(k, v);
    }
  }

  const results = [];
  const branchResults = [];
  const failing = [];

  // Text-on-background audit
  for (const theme of ['dark', 'light', 'mixed', 'mixed-light']) {
    const tmap = themeMaps[theme];
    for (const bg of BG_TOKENS) {
      const bgHex = resolveVariable(bg, tmap, paletteMap);
      if (!bgHex) continue;
      for (const fg of TEXT_TOKENS) {
        const fgHex = resolveVariable(fg, tmap, paletteMap);
        if (!fgHex) continue;
        const ratio = contrastRatio(fgHex, bgHex);
        const status = classify(ratio);
        results.push({ theme, fg, bg, fgHex, bgHex, ratio, status });
        if (status === 'FAIL') {
          failing.push({ theme, fg, bg, fgHex, bgHex, ratio });
        }
      }
    }
  }

  // Branch tint audit
  for (const theme of ['dark', 'light', 'mixed', 'mixed-light']) {
    const tmap = themeMaps[theme];
    const textHex = resolveVariable('--text', tmap, paletteMap);
    if (!textHex) continue;
    for (const branch of BRANCH_NAMES) {
      const branchHex = resolveVariable('--branch-' + branch, tmap, paletteMap);
      if (!branchHex) continue;
      for (const bg of ['--bg', '--surface']) {
        const bgHex = resolveVariable(bg, tmap, paletteMap);
        if (!bgHex) continue;
        const effectiveBg = mixColors(branchHex, bgHex, 0.12);
        const ratio = contrastRatio(textHex, effectiveBg);
        const status = classify(ratio);
        branchResults.push({ theme, branch, baseBg: bg, effectiveBg, ratio, status });
        if (status === 'FAIL') {
          failing.push({
            theme, fg: '--text', bg: `${bg}+branch-${branch}@12%`,
            fgHex: textHex, bgHex: effectiveBg, ratio
          });
        }
      }
    }
  }

  // Generate recommendations
  const recommendations = [];
  const dimFails = failing.filter(f => f.fg === '--text-dim').length;
  const accentFails = failing.filter(f => f.fg === '--accent').length;
  const branchFails = failing.filter(f => f.bg.includes('+branch-')).length;
  if (dimFails > 0) recommendations.push(`Adjust --text-dim: ${dimFails} failing pair(s)`);
  if (accentFails > 0) recommendations.push(`Adjust --accent: ${accentFails} failing pair(s)`);
  if (branchFails > 0) recommendations.push(`Add per-branch text overrides: ${branchFails} branch tint(s) fail`);
  const other = failing.length - dimFails - accentFails - branchFails;
  if (other > 0) recommendations.push(`Other fixes needed: ${other}`);

  const md = buildReport(results, branchResults, failing, recommendations);
  writeFileSync(reportPath, md, 'utf8');
  console.log(`Audit complete: ${results.length + branchResults.length} pairs checked, ${failing.length} failures.`);
  console.log(`Report written: ${reportPath}`);
  return { results, branchResults, failing, recommendations };
}

// Run if invoked directly (not imported)
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  await runAudit();
}
