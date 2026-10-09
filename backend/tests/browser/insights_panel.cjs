// Browser test for the folio-insights corpus panel in the Propositions tab.
//
// Driven by backend/tests/test_insights_browser.py. Serves the real
// frontend/index.html (and /static/*) through page.route and stubs every API
// call, so no backend or port is needed. Prints one JSON line of results.
// Exit 3 = Playwright/Chromium unavailable (the pytest wrapper skips).
//
// argv: <playwright module path> <frontend dir> <fixture json path>
const fs = require('fs');
const path = require('path');

const [playwrightPath, frontendDir, fixturePath] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require(playwrightPath)); } catch (e) { console.error('playwright unavailable:', e.message); process.exit(3); }

const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const job = fixture.job;
const jobId = job.id;
const ORIGIN = 'http://folio-enrich.test';
const CONTENT_TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.html': 'text/html' };

function session(outcomes = {}) {
  return {
    session_id: 'sess-1', job_id: jobId, annotator: 'tester', baseline: false, blind_pending: 0,
    candidates: job.result.propositions.map(p => ({ proposition: p, outcome: outcomes[p.id] || 'unreviewed', explicit_unresolved: false })),
    hand_added: [],
  };
}

async function openPage(browser, statusBody, { holdStatus = false } = {}) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const state = { errors: [], patches: [], statusCalls: 0, outcomes: {} };
  page.on('pageerror', e => state.errors.push(String(e)));
  let release;
  const held = new Promise(resolve => { release = resolve; });
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (url.origin !== ORIGIN) return route.fulfill({ status: 404, body: '' });
    if (url.pathname === '/') return route.fulfill({ status: 200, contentType: 'text/html', body: fs.readFileSync(path.join(frontendDir, 'index.html')) });
    if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/favicon')) {
      const file = path.join(frontendDir, url.pathname.replace(/^\/static\//, '').replace(/^\/favicon\.ico$/, 'favicon.svg'));
      if (file.startsWith(frontendDir) && fs.existsSync(file)) return route.fulfill({ status: 200, contentType: CONTENT_TYPES[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file) });
      return route.fulfill({ status: 404, body: '' });
    }
    if (url.pathname === `/enrich/${jobId}/insights-status`) {
      state.statusCalls += 1;
      if (holdStatus && state.statusCalls === 1) await held;
      return json(statusBody);
    }
    if (url.pathname === `/enrich/${jobId}`) return json(job);
    if (url.pathname === '/gold/sessions' && method === 'GET') return json([session(state.outcomes)]);
    if (url.pathname === '/gold/sessions/sess-1/completeness') return json({ complete: false, reasons: ['candidates remain unreviewed'] });
    if (url.pathname.startsWith('/gold/sessions/sess-1/candidates/') && method === 'PATCH') {
      const id = decodeURIComponent(url.pathname.split('/').pop());
      const body = JSON.parse(route.request().postData() || '{}');
      state.patches.push({ id, outcome: body.outcome });
      state.outcomes[id] = body.outcome;
      return json(session(state.outcomes));
    }
    if (url.pathname === '/settings') return json({ proposition_extraction_enabled: true, proposition_taxonomy: {}, task_llm_overrides: {}, llm_provider: '', llm_model: '' });
    return json({ detail: 'Not stubbed' }, 404);
  });
  await page.goto(`${ORIGIN}/?job=${encodeURIComponent(jobId)}&tab=propositions`);
  await page.waitForSelector('#tab-propositions.active .proposition-card', { timeout: 15000 });
  return { page, state, release };
}

async function bannerText(page) {
  await page.waitForFunction(() => {
    const b = document.getElementById('refreshCorpusStatusBtn');
    const t = document.getElementById('propositionCorpusBannerText');
    return b && !b.disabled && t && t.textContent && !t.textContent.startsWith('Checking');
  }, null, { timeout: 10000 });
  return page.textContent('#propositionCorpusBannerText');
}

(async () => {
  let browser;
  try { browser = await chromium.launch(); } catch (e) { console.error('chromium unavailable:', e.message.split('\n')[0]); process.exit(3); }
  const out = { banners: {}, errors: [] };
  try {
    for (const [name, body] of Object.entries(fixture.scenarios)) {
      const { page, state } = await openPage(browser, body);
      out.banners[name] = await bannerText(page);
      if (name === 'connected') {
        out.connectedCorpusRows = await page.$$eval('.proposition-corpus', n => n.length);
        out.connectedBadges = await page.$$eval('.proposition-corpus .corpus-badge', n => n.map(x => x.textContent));
      }
      if (name === 'not_configured') {
        out.notConfiguredCorpusRows = await page.$$eval('.proposition-corpus', n => n.length);
        // The review workflow is unaffected: enable annotation mode and approve.
        await page.click('#propositionModeToggle');
        await page.waitForSelector('.proposition-card button[onclick*="accepted"]:not([disabled])', { timeout: 10000 });
        const firstId = await page.getAttribute('.proposition-card', 'data-candidate-id');
        await page.click('.proposition-card button[onclick*="accepted"]');
        await page.waitForFunction(id => document.querySelector('.proposition-card')?.dataset.candidateId !== id, firstId, { timeout: 10000 });
        out.notConfiguredPatches = state.patches;
        out.notConfiguredAfterSaveBanner = await page.textContent('#propositionCorpusBannerText');
      }
      out.errors.push(...state.errors.map(e => `${name}: ${e}`));
      await page.close();
    }

    // Regression: a status response landing while the active card is dirty
    // must not re-render the tab (which would discard the unsaved edit).
    {
      const { page, state, release } = await openPage(browser, fixture.scenarios.connected, { holdStatus: true });
      await page.click('#propositionModeToggle');
      await page.waitForSelector('.proposition-card select[data-field="disposition"]:not([disabled])', { timeout: 10000 });
      await page.selectOption('.proposition-card select[data-field="disposition"]', 'rejected');
      out.dirtyBefore = await page.getAttribute('.proposition-card', 'data-dirty');
      await page.evaluate(() => { document.querySelector('.proposition-card').dataset.marker = 'original-node'; });
      release();
      await page.waitForSelector('.proposition-card .proposition-corpus', { timeout: 10000 });
      out.dirtyAfter = await page.getAttribute('.proposition-card', 'data-dirty');
      out.dirtyDisposition = await page.$eval('.proposition-card select[data-field="disposition"]', s => s.value);
      out.dirtySameNode = await page.$eval('.proposition-card', c => c.dataset.marker === 'original-node');
      out.dirtyBanner = await page.textContent('#propositionCorpusBannerText');
      out.dirtyCopyEnabled = await page.$eval('.proposition-card .corpus-copy', b => !b.disabled);
      // Refresh while dirty must not re-render either.
      await page.click('#refreshCorpusStatusBtn');
      await bannerText(page);
      out.dirtyAfterRefresh = await page.getAttribute('.proposition-card', 'data-dirty');
      out.dirtySameNodeAfterRefresh = await page.$eval('.proposition-card', c => c.dataset.marker === 'original-node');
      out.dirtyStatusCalls = state.statusCalls;
      out.errors.push(...state.errors.map(e => `dirty: ${e}`));
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(out));
})().catch(e => { console.error('FAILED', e); process.exit(1); });
