// Real baked opinion demo and real frontend, served without a backend or port.
// argv: Playwright module, frontend directory. Exit 3 means browser unavailable.
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const [modulePath, frontend] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require(modulePath)); } catch (e) { console.error(e.message); process.exit(3); }
(async () => {
  let browser;
  try { browser = await chromium.launch(); } catch (e) { console.error(e.message); process.exit(3); }
  const results = {}, errors = [];
  const demo = JSON.parse(fs.readFileSync(path.join(frontend, 'demos/opinion.json')));
  const expectedCount = new Set(demo.cache.job.result.annotations.filter(a => a.state !== 'rejected' && a.concepts?.[0]?.folio_iri).map(a => a.concepts[0].folio_iri)).size;
  try {
    for (const scenario of ['uncertain', 'confidence', 'counts', 'escape', 'close', 'remove', 'bulk', 'detail']) {
      const context = await browser.newContext();
      const page = await context.newPage();
      const dismissals = [];
      page.on('pageerror', e => errors.push(String(e)));
      await page.route('**/*', async route => {
        const u = new URL(route.request().url());
        const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
        if (u.origin !== 'http://folio-enrich.test') return route.fulfill({ status: 404, body: '' });
        if (u.pathname === '/') return route.fulfill({ contentType: 'text/html', body: fs.readFileSync(path.join(frontend, 'index.html')) });
        if (u.pathname === '/static/demos/opinion.json') {
          const fixture = JSON.parse(fs.readFileSync(path.join(frontend, 'demos/opinion.json')));
          const annotations = fixture.cache.job.result.annotations;
          const source = annotations.find(a => a.state === 'confirmed' && a.concepts?.[0] && /^\S+$/.test(a.span.text));
          assert.ok(source, 'demo must provide a confirmed single-word annotation');
          const rejected = structuredClone(source);
          rejected.id = `${source.id}-ui-rejected`;
          rejected.state = rejected.concepts[0].state = 'rejected';
          annotations.push(rejected);
          // Equal-confidence duplicates keep the first entry when rendered.
          annotations.sort((a, b) => Number(b === rejected) - Number(a === rejected));
          if (!annotations.some(a => a.concepts?.[0]?.confidence < 0.5)) {
            const lowConfidence = structuredClone(source);
            lowConfidence.id = `${source.id}-ui-low-confidence`;
            lowConfidence.state = lowConfidence.concepts[0].state = 'confirmed';
            lowConfidence.concepts[0].confidence = 0.3;
            annotations.push(lowConfidence);
          }
          return json(fixture);
        }
        if (u.pathname === '/settings') return json({ llm_provider: 'google', llm_model: 'test', task_llm_overrides: {}, proposition_taxonomy: {} });
        if (u.pathname === '/settings/providers') return json({ providers: {}, current: {} });
        if (u.pathname === '/settings/known-models') return json({ models: {} });
        if (/\/(reject|bulk-reject)$/.test(u.pathname)) { dismissals.push(u.pathname); return json({ same_concept_count: 0 }); }
        if (u.pathname === '/concepts/batch') return json({});
        return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
      });
      try {
        await page.goto('http://folio-enrich.test/?demo=opinion');
        await page.waitForSelector('.annotation-span');
        const singleTags = page.locator('.annotation-span[data-multi-count="1"]:not([data-state="rejected"])').filter({ hasNot: page.locator('.individual-span, .property-span') });
        const tag = singleTags.first();
        const id = await tag.getAttribute('data-ann-id');
        const intact = async () => {
          assert.equal(dismissals.length, 0, 'close/cancel must not send a dismiss request');
          assert.ok(await page.locator(`.annotation-span[data-ann-id="${id}"]:not([data-state="rejected"])`).count(), 'annotation must remain');
        };
        if (scenario === 'uncertain' || scenario === 'confidence') {
          assert.ok(await page.locator('.annotation-span[data-state="rejected"]').count(), 'ON must include rejected tags');
          await page.locator('label.toggle:has(#hideUncertainToggle) .toggle-track').click();
          assert.equal(await page.locator('#hideUncertainToggle').isChecked(), false);
          if (scenario === 'uncertain') assert.equal(await page.locator('.annotation-span[data-state="rejected"]').count(), 0, 'OFF must omit rejected tags');
          assert.equal(await page.locator('.annotation-span').evaluateAll(els => els.filter(el => { const c = Number(el.dataset.confidence); return (c > 1 ? c / 100 : c) < .5; }).length), 0, 'OFF must omit low confidence');
          assert.equal(await page.getAttribute('#hideUncertainToggle', 'aria-checked'), 'false');
        } else if (scenario === 'counts') {
          await page.click('[data-tab="metadata"]');
          const key = page.locator('.meta-key').filter({ hasText: /^Unique Concepts$/ });
          assert.equal(await key.count(), 1, 'Metadata needs Unique Concepts row');
          const n = Number(await key.evaluate(el => el.nextElementSibling.textContent));
          assert.equal(n, expectedCount, 'count must exclude rejected concepts');
          await page.click('[data-tab="concepts"]');
          await page.waitForSelector('.ct-summary-line');
          assert.equal(Number(await page.locator('.ct-summary-line strong').first().textContent()), n, 'tab counts must agree');
        } else {
          if (scenario === 'bulk') {
            const repeated = await singleTags.evaluateAll(els => els.find(el => els.filter(other => other.dataset.iri === el.dataset.iri).length > 1)?.dataset.annId);
            assert.ok(repeated, 'demo must provide a repeated concept');
            await page.locator(`.annotation-span[data-ann-id="${repeated}"]`).first().click();
          } else if (scenario === 'escape') {
            await tag.focus();
            await page.keyboard.press('Enter');
          } else await tag.click();
          await page.waitForSelector('#tooltip.visible');
          if (scenario === 'escape') {
            await page.keyboard.press('Escape');
            assert.equal(await page.locator('#tooltip.visible').count(), 0, 'Escape must close popover');
            await intact();
            assert.equal(await page.evaluate(() => document.activeElement?.dataset.annId), id, 'Escape returns focus to tag');
          } else if (scenario === 'close') {
            await page.locator('#tooltip .tooltip-dismiss-icon').click();
            assert.equal(await page.locator('#tooltip.visible').count(), 0);
            await intact();
            assert.equal(await page.locator('#tooltip .tooltip-dismiss-icon').getAttribute('aria-label'), 'Close');
          } else if (scenario === 'bulk' || scenario === 'detail') {
            const control = scenario === 'bulk'
              ? page.locator('#tooltip').getByRole('button', { name: /^Remove all/ })
              : page.locator('#detailDismissBtn');
            await control.click();
            const row = page.locator('.tag-remove-confirm');
            await row.getByRole('button', { name: 'Cancel', exact: true }).click();
            assert.equal(dismissals.length, 0);
            await control.click();
            await row.getByRole('button', { name: 'Remove', exact: true }).click();
            await page.waitForTimeout(50);
            assert.equal(dismissals.length, 1);
          } else {
            const remove = () => page.locator('#tooltip').getByRole('button', { name: 'Remove tag', exact: true });
            assert.equal(await remove().count(), 1, 'explicit Remove tag footer required');
            await remove().click();
            await page.locator('#tooltip').getByText('Remove this tag?', { exact: true }).waitFor();
            await intact();
            await page.locator('#tooltip').getByRole('button', { name: 'Cancel', exact: true }).click();
            await intact();
            await remove().click();
            await page.locator('#tooltip').getByRole('button', { name: 'Remove', exact: true }).click();
            await page.waitForFunction(() => !document.querySelector('#tooltip.visible'));
            assert.equal(dismissals.length, 1, 'confirmed removal must send exactly one request');
            assert.ok(dismissals[0].includes(`/annotations/${id}/reject`));
          }
        }
        results[scenario] = null;
      } catch (e) { results[scenario] = e.stack; }
      await context.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify({ results, errors }));
})().catch(e => { console.error(e); process.exit(1); });
