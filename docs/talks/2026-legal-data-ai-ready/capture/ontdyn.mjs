// Clip "ontdyn": ontology-dynamic finds a concept FOLIO lacks in the synthetic demo memo.
// Read-only: no review action is submitted. Needs ontdyn-viewer (QA build) serving the scratch
// store from capture/README.md at ONTDYN_URL (default http://127.0.0.1:8811).
// Usage: node capture/ontdyn.mjs
import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MEDIA = path.resolve(HERE, '..', 'media');
const RAW = path.join(MEDIA, 'raw-ontdyn');
const BASE = process.env.ONTDYN_URL || 'http://127.0.0.1:8811';
const CORPUS = process.env.ONTDYN_CORPUS_ID || '1';
const LABEL = 'Wrongful Termination of Commercial Contract';

async function drive(page, { still } = {}) {
  const marks = {}; const t0 = Date.now();
  const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
  const w = (ms) => page.waitForTimeout(still ? Math.min(ms, 300) : ms);
  // 1. The memo, tagged against FOLIO. "wrongful termination" only matches FOLIO's employment concept.
  await page.goto(`${BASE}/qa/${CORPUS}/documents/1`, { waitUntil: 'networkidle' });
  await page.locator('.annotation-span').first().waitFor();
  mark('ready');
  await w(2200);
  if (!still) {
    await page.locator('[aria-label="Review tag: wrongful termination (preliminary)"]').first().click();
    await page.getByText('Wrongful Discharge or Termination').first().waitFor();
    mark('folioMatch');
    await w(4200);
    await page.keyboard.press('Escape');
    // 2. QA review queue, filtered to the new proposals.
    await page.getByRole('link', { name: 'Review queue' }).click().catch(() => page.goto(`${BASE}/qa/${CORPUS}/queue`));
    await page.waitForLoadState('networkidle');
    await w(800);
    await page.locator('select').first().selectOption('proposals');
    await page.getByText(LABEL).first().waitFor();
    mark('proposal');
    await w(4500);
  }
  // 3. The proposal's page: parent link and verbatim evidence in context.
  await page.goto(`${BASE}/queue/${CORPUS}`, { waitUntil: 'networkidle' });
  await w(1500);
  await page.getByRole('link', { name: LABEL }).first().click();
  await page.getByText('Evidence in context').waitFor();
  mark('item');
  await w(1200);
  if (!still) {
    await page.mouse.move(960, 600);
    for (let i = 0; i < 10; i++) { await page.mouse.wheel(0, 30); await page.waitForTimeout(80); }
    await w(4500);
  } else {
    await page.evaluate(() => window.scrollTo(0, 60));
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
renameSync(vid, path.join(MEDIA, 'ontdyn-raw.webm'));

const sctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
const sp = await sctx.newPage();
await drive(sp, { still: true });
await sp.screenshot({ path: path.join(MEDIA, 'ontdyn-still-2x.png') });
await sctx.close();
await browser.close();
writeFileSync(path.join(MEDIA, 'ontdyn-run.json'), JSON.stringify({ url: BASE, label: LABEL,
  videoMarks: marks, recordedAt: new Date(tStart).toISOString() }, null, 2));
console.log(JSON.stringify(marks));
