// Clip "enrich-panels" + still "enrich-panels-still": FOLIO Enrich result tabs (Concepts,
// Individuals, Properties, Triples) for the pre-computed demo-document.md result. No LLM, no key.
// Usage: node capture/enrich-panels.mjs   (from the deck folder; see capture/README.md)
import { writeFileSync } from 'node:fs';
import path from 'node:path';
import { openEnrich, glideClick, smoothScroll, MEDIA } from './enrich-common.mjs';

const tab = (page, t) => page.locator(`.tab[data-tab="${t}"]`);
// Concepts tab with the Objectives branch (49 concepts) expanded.
async function concepts(page, still) {
  if (still) await tab(page, 'concepts').click(); else await glideClick(page, tab(page, 'concepts'));
  await page.waitForTimeout(still ? 300 : 1300);
  const obj = page.locator('#tab-concepts .ancestry-branch-header', { hasText: /Objectives/i }).locator('.ancestry-toggle');
  if (still) await obj.click(); else await glideClick(page, obj);
  await page.waitForTimeout(500);
}

// --- Still (deviceScaleFactor 2) ---
{
  const { page, finish } = await openEnrich({ scale: 2, cursor: false });
  await concepts(page, true);
  await page.screenshot({ path: path.join(MEDIA, 'enrich-panels-still.png') });
  await finish();
}

// --- Video ---
const { page, ready, finish } = await openEnrich({ video: 'enrich-panels' });
const t0 = Date.now() - ready * 1000;
const marks = { ready };
const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
await page.mouse.move(1300, 500);
await page.waitForTimeout(1200);
mark('concepts'); await concepts(page, false);
await page.waitForTimeout(1200);
await smoothScroll(page, '#resultBody', 900, 3000);
await page.waitForTimeout(800);
// Individuals list scrolls; Properties and Triples fit the pane, so just hold on them.
for (const [t, dy] of [['individuals', 450], ['properties', 0], ['triples', 0]]) {
  mark(t);
  await glideClick(page, tab(page, t));
  await page.waitForTimeout(dy ? 1300 : 2600);
  if (dy) { await smoothScroll(page, '#resultBody', dy, 1800); await page.waitForTimeout(500); }
}
mark('end');
writeFileSync(path.join(MEDIA, 'enrich-panels-run.json'), JSON.stringify({ videoMarks: marks }, null, 2));
await finish('enrich-panels');
console.log(JSON.stringify(marks));
