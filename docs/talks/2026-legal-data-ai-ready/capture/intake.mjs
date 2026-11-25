// Screen capture of ALEA Intake (showcase page) tagging a plain-language story.
// Usage: INTAKE_URL=http://127.0.0.1:8984-ish OUT_DIR=<raw dir> node capture/intake.mjs
// The local run routes the OpenAI-compatible client to Ollama, so the "key" is a
// placeholder that only satisfies the page's format check; no paid key is used.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE = process.env.INTAKE_URL || 'http://127.0.0.1:8985/';
const OUT = process.env.OUT_DIR || path.resolve('media/raw');
const KEY = process.env.PLACEHOLDER_KEY || 'sk-local-ollama-demo';
const STORY =
  'I run a small wine import business in São Paulo. Our Chilean supplier sent wine that failed Brazilian customs testing, so the government made us recall it and fined us. Then the supplier ended our exclusive contract without warning and started selling through a competitor in Rio, still using the brand we were promoting. What can I do?';

fs.mkdirSync(OUT, { recursive: true });
const t0 = Date.now();
const marks = {};
const mark = (name) => { marks[name] = (Date.now() - t0) / 1000; console.log(`[mark] ${name} ${marks[name].toFixed(2)}s`); };

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  deviceScaleFactor: 2,
  recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } },
});
const page = await context.newPage();
mark('context');
// REPLAY_TOKEN_FILE: re-show a finished local run (intake 1) in the real UI.
// The live run's analysis converged, but its memo step outlasted the budget, so
// this pass serves that run's stored results from the real backend and stubs only
// the session setup and the memo call. Results and visualization pass through.
const replayTokenFile = process.env.REPLAY_TOKEN_FILE;
if (replayTokenFile) {
  const token = fs.readFileSync(replayTokenFile, 'utf8').trim();
  const ok = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route('**/api/v1/auth/guest', (r) => ok(r, { access_token: token, token_type: 'bearer' }));
  await page.route('**/api/v1/consent/grant', (r) => ok(r, { ok: true }));
  await page.route(/\/api\/v1\/intake\/$/, (r) => ok(r, { id: 1, session_id: 1, party_id: 1 }));
  await page.route('**/api/v1/analysis/1/analyze', async (r) => {
    await new Promise((res) => setTimeout(res, 3500));
    const real = await r.fetch({ method: 'GET', url: r.request().url().replace('/analyze', '/status'), headers: { Authorization: `Bearer ${token}` } });
    return ok(r, { ...(await real.json()), is_reference_model: true });
  });
  await page.route('**/api/v1/output/generate', (r) => ok(r, { documents: [] }));
}
await page.goto(BASE, { waitUntil: 'networkidle' });
await page.getByRole('heading', { name: /See your story/ }).waitFor();
// Off-camera setup (trimmed): placeholder key, consent.
await page.locator('#visitor-key').fill(KEY);
await page.locator('label.consent input[type=checkbox]').check();
if (replayTokenFile) await page.evaluate((story) => {
  let hash = 0xcbf29ce484222325n;
  for (const byte of new TextEncoder().encode(story)) hash = BigInt.asUintN(64, (hash ^ BigInt(byte)) * 0x100000001b3n);
  sessionStorage.setItem(`showcase-story:1:${hash.toString(16).padStart(16, '0')}`, JSON.stringify({ clientId: 'replay', delivered: true }));
}, STORY);
const story = page.locator('textarea');
await story.scrollIntoViewIfNeeded();
await page.evaluate(() => window.scrollTo({ top: document.querySelector('textarea').getBoundingClientRect().top + window.scrollY - 140 }));
await page.waitForTimeout(800);
mark('typing_start');
await story.click();
await story.pressSequentially(STORY, { delay: 12 });
mark('typing_end');
await page.waitForTimeout(800);
await page.getByRole('button', { name: /Analyze my story/ }).click();
mark('analyze_click');
await page.waitForTimeout(3000);
mark('progress_shown');
await page.getByRole('heading', { name: 'Issues and FOLIO concepts' }).waitFor({ timeout: 40 * 60 * 1000 });
mark('results_ready');
await page.waitForTimeout(500);
await page.getByRole('heading', { name: 'Issues and FOLIO concepts' }).evaluate((el) =>
  window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 24, behavior: 'smooth' }));
await page.waitForTimeout(2500);
mark('issues_in_view');
await page.screenshot({ path: path.join(OUT, 'still.png') });
await page.waitForTimeout(4000);
await page.mouse.wheel(0, 380);
await page.waitForTimeout(4000);
mark('end');

const issues = await page.locator('.showcase-issues article').evaluateAll((els) =>
  els.map((a) => ({ claim: a.querySelector('h3')?.textContent, folio_iri: a.querySelector('a.concept-chip')?.getAttribute('href') || null })));
const api = await page.evaluate(async () => {
  const token = sessionStorage.getItem('showcase-token');
  const s = JSON.parse(sessionStorage.getItem('showcase-intake') || 'null');
  const get = async (p) => (await fetch(p, { headers: { Authorization: `Bearer ${token}` } })).json();
  return { results: await get(`/api/v1/analysis/${s.id}/results`), visualization: await get(`/api/v1/analysis/${s.id}/visualization`) };
});
const video = await page.video().path();
await context.close();
await browser.close();
fs.writeFileSync(path.join(OUT, 'run.json'), JSON.stringify({ marks, issues, api, video, story: STORY }, null, 2));
console.log(JSON.stringify({ marks, issues, video }, null, 2));
