// Clip "enrich-tag" + stills "enrich-tag-still" and "demo-doc-still": FOLIO Enrich showing
// the pre-computed result for demo-document.md (evidence/enrich-result.json). No LLM, no key.
// Needs a local FOLIO Enrich backend on ENRICH_URL (default http://127.0.0.1:8731).
// Usage: node capture/enrich-tag.mjs   (from the deck folder; see capture/README.md)
import { writeFileSync } from 'node:fs';
import path from 'node:path';
import { openEnrich, glideClick, smoothScroll, MEDIA } from './enrich-common.mjs';

const SPAN = '#annotatedText .annotation-span';

// --- Stills (deviceScaleFactor 2, no drawn cursor) ---
{
  const { page, finish } = await openEnrich({ scale: 2, cursor: false });
  // demo-doc: top of the annotated document, results pane only.
  const pane = await page.locator('#resultBody').boundingBox();
  await page.screenshot({ path: path.join(MEDIA, 'demo-doc-still.png'),
    clip: { x: pane.x, y: 48, width: 1920 - pane.x, height: 1080 - 48 } });
  // enrich-tag: full app, document scrolled so the dense Analysis section is in view.
  await page.evaluate(() => { const e = document.getElementById('resultBody'); e.scrollTop = e.scrollHeight; });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(MEDIA, 'enrich-tag-still.png') });
  await finish();
}

// --- Video ---
const { page, ready, finish } = await openEnrich({ video: 'enrich-tag' });
const t0 = Date.now() - ready * 1000;
const marks = { ready };
const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
await page.mouse.move(1500, 700);
await page.waitForTimeout(1800);
mark('scroll1');
await smoothScroll(page, '#resultBody', 400, 2200);
await page.waitForTimeout(400);
await smoothScroll(page, '#resultBody', -400, 1400);
// 1) "ICC" in "ICC arbitration" -> individual: International Chamber of Commerce (Legal Entity)
const icc = page.locator('#annotatedText .individual-span', { hasText: /^ICC$/ }).first();
await glideClick(page, icc);
mark('icc');
await page.waitForTimeout(2600);
await page.keyboard.press('Escape');
// 2) "breach of contract" -> detail panel: Objectives > ... > Breach of Contract + IRI
await glideClick(page, page.locator(`${SPAN}[data-label="Breach of Contract"]`).first(), { dx: 12 });
mark('breach');
await page.waitForTimeout(3200);
await page.keyboard.press('Escape');
// 3) scroll the (now narrower) document, then "trademark infringement" in the Analysis
await smoothScroll(page, '#resultBody', 640, 3600);
const ti = page.locator(`${SPAN}[data-label="Trademark Infringement"]`).last();
await glideClick(page, ti, { dx: 14 });
mark('trademark');
await page.waitForTimeout(3400);
mark('end');
writeFileSync(path.join(MEDIA, 'enrich-tag-run.json'), JSON.stringify({ videoMarks: marks }, null, 2));
await finish('enrich-tag');
console.log(JSON.stringify(marks));
