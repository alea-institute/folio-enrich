// Clip "insights": FOLIO Insights review viewer over propositions extracted from the synthetic
// demo memo. Read-only: selects concepts and units, never approves, rejects or edits.
// Needs `folio-insights serve` on INSIGHTS_URL (default http://127.0.0.1:8812); see capture/README.md.
// Usage: node capture/insights.mjs
import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MEDIA = path.resolve(HERE, '..', 'media');
const RAW = path.join(MEDIA, 'raw-insights');
const BASE = process.env.INSIGHTS_URL || 'http://127.0.0.1:8812';

async function drive(page, { still } = {}) {
  const marks = {}; const t0 = Date.now();
  const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
  const w = (ms) => page.waitForTimeout(still ? Math.min(ms, 300) : ms);
  const node = (label) => page.locator('[role=treeitem]', { has: page.locator('.node-label', { hasText: new RegExp(`^${label}$`) }) }).first();
  const unit = (text) => page.locator('.unit-card', { hasText: text }).first();
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.locator('.unit-card').first().waitFor();
  mark('ready');
  await w(2600);
  if (!still) {
    // Scroll the unit list to show the range of extracted propositions.
    await page.mouse.move(1100, 400);
    for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, 45); await page.waitForTimeout(90); }
    await w(1200);
    for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, -45); await page.waitForTimeout(60); }
    await w(600);
  }
  // FOLIO branch -> concept -> the propositions tagged with it.
  await node('Objectives').click();
  await w(1500);
  await node('Wrongful termination').click();
  await unit('Wrongful termination claim requires').waitFor();
  mark('wrongfulTermination');
  await w(1800);
  await unit('Wrongful termination claim requires').locator('.unit-text').click();
  mark('sourceContext');
  await w(3200);
  if (!still) {
    await node('Limitation of Liability').click();
    await unit('Limitation of liability clauses').waitFor();
    await w(1200);
    await unit('Limitation of liability clauses').locator('.unit-text').click();
    mark('limitation');
    await w(3000);
    await node('Unfair Competition').click();
    await unit('Arbitral tribunal can grant').waitFor();
    await w(1000);
    await unit('Arbitral tribunal can grant').locator('.unit-text').click();
    mark('unfairCompetition');
    await w(3000);
  }
  mark('end');
  return marks;
}

mkdirSync(RAW, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, colorScheme: 'dark',
  recordVideo: { dir: RAW, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const tStart = Date.now();
const marks = await drive(page);
await ctx.close();
const vid = readdirSync(RAW).filter((f) => f.endsWith('.webm')).map((f) => path.join(RAW, f)).pop();
renameSync(vid, path.join(MEDIA, 'insights-raw.webm'));

const sctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2, colorScheme: 'dark' });
const sp = await sctx.newPage();
await drive(sp, { still: true });
await sp.screenshot({ path: path.join(MEDIA, 'insights-still-2x.png') });
await sctx.close();
await browser.close();
writeFileSync(path.join(MEDIA, 'insights-run.json'), JSON.stringify({ url: BASE,
  videoMarks: marks, recordedAt: new Date(tStart).toISOString() }, null, 2));
console.log(JSON.stringify(marks));
