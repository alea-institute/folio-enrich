// Clip "mapper": FOLIO Mapper mapping a SYNTHETIC firm taxonomy (no LLM, no key).
// Usage: node capture/mapper.mjs   (from the deck folder; see capture/README.md)
import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MEDIA = path.resolve(HERE, '..', 'media');
const RAW = path.join(MEDIA, 'raw-mapper');
const URL = 'https://mapper.openlegalstandard.org';

// Invented practice-area labels. No real firm data.
const TAXONOMY = [
  'Cross-border Arbitration', 'Employment Claims', 'Product Liability',
  'Disputes > Distribution', 'Trademark Enforcement', 'Customs & Trade', 'Data Protection',
  'M&A', 'Real Estate Leasing', 'Banking & Finance', 'Tax Controversy',
  'Regulatory Investigations', 'Insolvency', 'Antitrust', 'Wine & Spirits Regulatory',
  'Franchise Disputes',
];
const ITEMS_TO_ACCEPT = 3;

async function bestCandidate(page) {
  // Highest-scoring candidate badge in the visible tree; returns its row.
  const rows = page.locator('div.cursor-pointer:has(> input[type=checkbox]):has(span.tabular-nums.rounded-full)');
  const n = await rows.count();
  let best = null, bestScore = -1, bestLabel = '';
  for (let i = 0; i < n; i++) {
    const r = rows.nth(i);
    const s = parseInt(await r.locator('span.tabular-nums.rounded-full').first().innerText(), 10);
    if (s > bestScore) { bestScore = s; best = r; bestLabel = (await r.locator('span.truncate').first().innerText()).trim(); }
  }
  return { row: best, score: bestScore, label: bestLabel };
}

async function drive(page, { still } = {}) {
  const marks = {};
  const t0 = Date.now();
  const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.getByText('Enter text directly').waitFor();
  mark('ready');
  await page.getByRole('button', { name: 'No LLM' }).click().catch(() => {});
  await page.waitForTimeout(still ? 0 : 900);
  const ta = page.locator('textarea');
  if (still) await ta.fill(TAXONOMY.join('\n'));
  else { await ta.click(); await page.keyboard.type(TAXONOMY.join('\n'), { delay: 11 }); }
  await page.waitForTimeout(still ? 0 : 700);
  await page.getByRole('button', { name: 'Parse Text' }).click();
  await page.getByText(`${TAXONOMY.length} items detected`).waitFor();
  await page.waitForTimeout(still ? 0 : 1600);
  await page.getByRole('button', { name: 'Continue →' }).click();
  await page.getByRole('button', { name: 'Continue Anyway' }).click();
  await page.locator('span.tabular-nums.rounded-full').first().waitFor({ timeout: 60000 });
  mark('mapped');
  const accepted = [];
  for (let i = 0; i < ITEMS_TO_ACCEPT; i++) {
    await page.waitForTimeout(still ? 500 : 1500);
    const { row, score, label } = await bestCandidate(page);
    await row.locator('span.truncate').first().click(); // open candidate details
    await page.waitForTimeout(still ? 300 : 1000);
    await row.locator('input[type=checkbox]').first().check();
    accepted.push({ input: TAXONOMY[i], folio: label, score });
    if (still && i === ITEMS_TO_ACCEPT - 1) break;
    await page.waitForTimeout(still ? 300 : 1500);
    if (i < ITEMS_TO_ACCEPT - 1) await page.getByRole('button', { name: 'Next →' }).click();
  }
  mark('end');
  return { marks, accepted };
}

mkdirSync(RAW, { recursive: true });
const browser = await chromium.launch();

// 1) Video pass
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: RAW, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const tStart = Date.now();
const run = await drive(page);
await page.waitForTimeout(1500);
await ctx.close();
const vid = readdirSync(RAW).filter((f) => f.endsWith('.webm')).map((f) => path.join(RAW, f)).pop();
renameSync(vid, path.join(MEDIA, 'mapper-raw.webm'));

// 2) Still pass (deviceScaleFactor 2) at the key moment: third item accepted, details open
const sctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
const sp = await sctx.newPage();
const srun = await drive(sp, { still: true });
await sp.getByText("Loading details").waitFor({ state: "detached", timeout: 15000 }).catch(() => {});
await sp.waitForTimeout(1500);
await sp.screenshot({ path: path.join(MEDIA, 'mapper-still.jpg'), type: 'jpeg', quality: 85 });
await sctx.close();
await browser.close();

writeFileSync(path.join(MEDIA, 'mapper-run.json'), JSON.stringify({ url: URL, taxonomy: TAXONOMY,
  videoMarks: run.marks, accepted: run.accepted, stillAccepted: srun.accepted, recordedAt: new Date(tStart).toISOString() }, null, 2));
console.log(JSON.stringify(run, null, 2));
