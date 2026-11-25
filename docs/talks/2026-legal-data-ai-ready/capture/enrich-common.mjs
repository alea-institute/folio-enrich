// Shared setup for the FOLIO Enrich clips (enrich-tag.mjs, enrich-panels.mjs).
// Loads evidence/enrich-result.json into a LOCAL FOLIO Enrich the same way "Try an
// Exemplar" loads a baked demo (?demo=<slug> -> /static/demos/<slug>.json), but the
// demo JSON is served by Playwright request interception, so nothing is copied into
// frontend/demos/ and the repo stays untouched. The per-annotation lineage endpoint is
// answered from the same JSON (the backend only seeds jobs for files in frontend/demos/).
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync, renameSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
export const { chromium } = require('playwright');

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const MEDIA = path.resolve(HERE, '..', 'media');
export const RESULT = path.resolve(HERE, '..', 'evidence', 'enrich-result.json');
export const BASE = process.env.ENRICH_URL || 'http://127.0.0.1:8731';
export const SLUG = 'talk_distribution_breach';
mkdirSync(MEDIA, { recursive: true });

const BODY = readFileSync(RESULT, 'utf8');
const ANNS = new Map(JSON.parse(BODY).cache.job.result.annotations.map((a) => [a.id, a]));

// Visible cursor: Playwright video does not draw the pointer, so draw one.
const CURSOR = `
addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = '__cap_cursor';
  c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;'
    + 'background:rgba(30,64,175,.28);border:2px solid rgba(30,64,175,.85);z-index:2147483647;pointer-events:none;'
    + 'transition:transform .12s ease;display:none';
  document.body.appendChild(c);
  addEventListener('mousemove', (e) => { c.style.display = 'block'; c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => { c.style.transform = 'scale(.7)'; }, true);
  addEventListener('mouseup', () => { c.style.transform = ''; }, true);
});`;

export async function openEnrich({ video, scale = 1, cursor = true } = {}) {
  const browser = await chromium.launch();
  const opts = { viewport: { width: 1920, height: 1080 }, deviceScaleFactor: scale, colorScheme: 'light' };
  let rawDir;
  if (video) {
    rawDir = path.join(MEDIA, 'raw-' + video);
    mkdirSync(rawDir, { recursive: true });
    opts.recordVideo = { dir: rawDir, size: { width: 1920, height: 1080 } };
  }
  const ctx = await browser.newContext(opts);
  if (cursor) await ctx.addInitScript(CURSOR);
  await ctx.route(`**/static/demos/${SLUG}.json`, (r) => r.fulfill({ contentType: 'application/json', body: BODY }));
  await ctx.route('**/enrich/*/annotations/*/lineage', (r) => {
    const id = decodeURIComponent(new URL(r.request().url()).pathname.split('/').slice(-2, -1)[0]);
    const a = ANNS.get(id);
    if (!a) return r.fulfill({ status: 404, body: '{}' });
    return r.fulfill({ contentType: 'application/json', body: JSON.stringify({ annotation_id: id, lineage: a.lineage || [], sentence_text: a.span?.sentence_text ?? null }) });
  });
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(`${BASE}/?demo=${SLUG}`);
  await page.waitForSelector('#annotatedText .annotation-span');
  await page.waitForTimeout(600);
  const ready = (Date.now() - t0) / 1000;
  const finish = async (name) => {
    const v = page.video();
    await ctx.close();
    await browser.close();
    if (v && rawDir) {
      const f = readdirSync(rawDir).find((x) => x.endsWith('.webm'));
      renameSync(path.join(rawDir, f), path.join(MEDIA, `${name}-raw.webm`));
    }
  };
  return { page, ready, finish };
}

// Move the (drawn) pointer smoothly to an element's centre (or offset) and click it.
export async function glideClick(page, locator, { dx, dy, steps = 28, pause = 250 } = {}) {
  await locator.scrollIntoViewIfNeeded();
  const b = await locator.boundingBox();
  const x = b.x + (dx ?? b.width / 2), y = b.y + (dy ?? b.height / 2);
  await page.mouse.move(x, y, { steps });
  await page.waitForTimeout(pause);
  await page.mouse.click(x, y);
  // A click can open the detail panel and reflow the text; keep the pointer on the tag.
  await page.waitForTimeout(350);
  const a = await locator.boundingBox();
  if (a && (Math.abs(a.x - b.x) > 2 || Math.abs(a.y - b.y) > 2)) {
    await page.mouse.move(a.x + Math.min(dx ?? a.width / 2, a.width - 4), a.y + (dy ?? a.height / 2), { steps: 10 });
  }
}

// Smoothly scroll a scroll container by `dy` px over `ms` milliseconds.
export async function smoothScroll(page, selector, dy, ms) {
  await page.evaluate(([sel, dy, ms]) => new Promise((res) => {
    const el = document.querySelector(sel); const y0 = el.scrollTop; const t0 = performance.now();
    const ease = (t) => (t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
    const step = (now) => { const t = Math.min(1, (now - t0) / ms); el.scrollTop = y0 + dy * ease(t); t < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  }), [selector, dy, ms]);
}
