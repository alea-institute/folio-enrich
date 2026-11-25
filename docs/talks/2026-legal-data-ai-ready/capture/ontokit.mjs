// Clip "ontokit": browse the public FOLIO project in OntoKit to a concept's detail panel.
// Anonymous, read-only: no sign-in, no credential. Usage: node capture/ontokit.mjs
import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MEDIA = path.resolve(HERE, '..', 'media');
const RAW = path.join(MEDIA, 'raw-ontokit');
const BASE = process.env.ONTOKIT_URL || 'https://ontokit.openlegalstandard.org';
const PATH = ['Area of Law', 'Intellectual Property Law'];
const TARGET = 'Trademark and Trade Dress Law';

async function drive(page, { still } = {}) {
  const marks = {}; const t0 = Date.now();
  const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
  const w = (ms) => page.waitForTimeout(still ? Math.min(ms, 400) : ms);
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.locator('a[href^="/projects/"]', { hasText: 'FOLIO' }).first().waitFor();
  mark('ready');
  await w(1400);
  await page.locator('a[href^="/projects/"]', { hasText: 'FOLIO' }).first().click();
  await page.locator('[role=treeitem]').first().waitFor({ timeout: 60000 });
  await w(1600);
  for (const label of PATH) {
    const item = page.locator('[role=treeitem]', { has: page.getByText(label, { exact: true }) }).first();
    await item.getByText(label, { exact: true }).click(); // select: shows detail
    await w(1200);
    await item.locator('button').first().click(); // expand children
    await page.waitForTimeout(still ? 1500 : 1800);
  }
  const target = page.locator('[role=treeitem]', { has: page.getByText(TARGET, { exact: true }) }).first();
  await target.scrollIntoViewIfNeeded();
  await target.getByText(TARGET, { exact: true }).click();
  await page.getByText('Primary Label').waitFor();
  mark('target');
  await page.waitForTimeout(still ? 2000 : 2600);
  if (!still) {
    // Smooth-scroll the detail panel to show translations and parents.
    await page.mouse.move(1300, 650);
    for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, 40); await page.waitForTimeout(90); }
    await page.waitForTimeout(1800);
    for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, -40); await page.waitForTimeout(60); }
    await page.waitForTimeout(800);
    await page.getByRole('button', { name: 'Sign in to edit' }).hover();
    await page.waitForTimeout(2000);
  }
  mark('end');
  return marks;
}

mkdirSync(RAW, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: RAW, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const tStart = Date.now();
const marks = await drive(page);
await ctx.close();
const vid = readdirSync(RAW).filter((f) => f.endsWith('.webm')).map((f) => path.join(RAW, f)).pop();
renameSync(vid, path.join(MEDIA, 'ontokit-raw.webm'));

const sctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
const sp = await sctx.newPage();
await drive(sp, { still: true });
await sp.screenshot({ path: path.join(MEDIA, 'ontokit-still.jpg'), type: 'jpeg', quality: 85 });
await sctx.close();
await browser.close();
writeFileSync(path.join(MEDIA, 'ontokit-run.json'), JSON.stringify({ url: BASE, path: PATH, target: TARGET,
  videoMarks: marks, recordedAt: new Date(tStart).toISOString() }, null, 2));
console.log(JSON.stringify(marks));
