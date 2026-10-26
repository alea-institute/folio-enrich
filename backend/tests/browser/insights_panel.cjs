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
const assert = require('node:assert/strict');

const [playwrightPath, frontendDir, fixturePath] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require(playwrightPath)); } catch (e) { console.error('playwright unavailable:', e.message); process.exit(3); }

const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const job = fixture.job;
const jobId = job.id;
// HTTPS matches deployment and supplies Web Crypto for hand-added IDs.
const ORIGIN = 'https://folio-enrich.test';
const CONTENT_TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.html': 'text/html' };

function session(outcomes = {}, activeJobId = jobId) {
  return {
    session_id: 'sess-1', job_id: activeJobId, annotator: 'tester', baseline: false, blind_pending: 0,
    candidates: job.result.propositions.map(p => ({ proposition: p, outcome: outcomes[p.id] || 'unreviewed', explicit_unresolved: false })),
    hand_added: [],
  };
}

async function openPage(browser, statusBody, { holdStatus = false, postJob = null, tab = 'propositions' } = {}) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const state = { errors: [], patches: [], statusCalls: 0, outcomes: {}, postJob,
    statusResponses: [], postResponses: [], statusByJob: {} };
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
    for (const activeJob of [job, fixture.otherJob]) {
      if (url.pathname === `/enrich/${activeJob.id}/insights-status`) {
        state.statusCalls += 1;
        state.statusByJob[activeJob.id] = (state.statusByJob[activeJob.id] || 0) + 1;
        const response = state.statusResponses.shift() || { body: statusBody };
        if (holdStatus && state.statusCalls === 1) await held;
        if (response.wait) await response.wait;
        return json(response.body, response.status || 200);
      }
      if (url.pathname === `/enrich/${activeJob.id}`) return json(activeJob);
      if (state.postJob && url.pathname === `/enrich/${activeJob.id}/post-job`) {
        const response = state.postResponses.shift() || { body: state.postJob };
        if (response.wait) await response.wait;
        return json(postPayload(activeJob.id, response.body));
      }
      if (state.postJob && ['/review/complete', '/insights-push'].some(suffix => url.pathname === `/enrich/${activeJob.id}${suffix}`) && method === 'POST') {
        state.postJob = { ...fixture.postJob.pushed, push_attempts: state.postJob.push_attempts + 1 };
        return json(postPayload(activeJob.id, state.postJob));
      }
    }
    if (url.pathname === '/gold/access') return json({ authenticated: true, via: 'local' });
    if (url.pathname === '/enrich/push-access') return json({ push_allowed: true, insights_configured: true });
    if (url.pathname === '/gold/sessions' && method === 'GET') return json([session(state.outcomes, url.searchParams.get('job_id') || jobId)]);
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
  await page.goto(`${ORIGIN}/?job=${encodeURIComponent(jobId)}&tab=${tab}`);
  if (tab === 'propositions') {
    await page.waitForSelector('#tab-propositions.active .proposition-card', { timeout: 15000 });
  } else {
    await page.waitForSelector('#propositionCandidates .proposition-card', { state: 'attached', timeout: 15000 });
  }
  if (postJob) await page.waitForFunction(() => document.getElementById('postJobChips').textContent.includes('Insights:'));
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

function postPayload(id, postJob) {
  return { job_id: id, job_status: 'completed', legacy: false, push_in_flight: false,
    insights_configured: true, push_allowed: true, post_job: postJob };
}

function barrier() {
  let release;
  const wait = new Promise(resolve => { release = resolve; });
  return { wait, release };
}

async function waitCorpus(page, count) {
  await page.waitForFunction(n => {
    const button = document.getElementById('refreshCorpusStatusBtn');
    return button && !button.disabled && document.getElementById('propositionCorpusBannerText')?.textContent.includes(`${n} of 3 propositions in corpus`);
  }, count, { timeout: 10000 });
}

async function enableReview(page) {
  await page.click('#propositionModeToggle');
  await page.waitForSelector('.proposition-card select[data-field="disposition"]:not([disabled])');
}

async function revisit(page, id = jobId) {
  await page.evaluate(async id => {
    history.replaceState(null, '', `/?job=${id}&tab=propositions`);
    await tryLoadJob();
  }, id);
}

async function pushRegressions(browser, out) {
  const absent = fixture.absent;
  const present = fixture.scenarios.connected;
  out.pushChecks = [];
  const finish = async (name, page, state) => {
    out.errors.push(...state.errors.map(e => `${name}: ${e}`));
    out.pushChecks.push(name);
    await page.close();
  };

  // Complete review via the real action, retaining a dirty field and its focus.
  {
    const { page, state } = await openPage(browser, absent, { postJob: fixture.postJob.awaiting });
    await waitCorpus(page, 0);
    await enableReview(page);
    const field = '.proposition-card select[data-field="disposition"]';
    await page.selectOption(field, 'rejected');
    await page.evaluate(() => { document.querySelector('.proposition-card').dataset.marker = 'original-node'; });
    const gate = barrier();
    state.statusResponses.push({ body: present, wait: gate.wait });
    await page.click('#propositionCompleteReviewBtn');
    await page.waitForFunction(() => document.getElementById('postJobChips').textContent.includes('Insights: pushed'));
    await page.focus(field);
    gate.release();
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2, 'a completed push refreshes cached absence once');
    assert.equal(await page.inputValue(field), 'rejected');
    assert.equal(await page.getAttribute('.proposition-card', 'data-dirty'), 'true');
    assert.equal(await page.getAttribute('.proposition-card', 'data-marker'), 'original-node');
    assert.equal(await page.$eval(field, el => el === document.activeElement), true);
    assert.match(await page.textContent('.proposition-card .proposition-corpus'), /hypothesis/);
    if (process.env.FOLIO_ENRICH_INSIGHTS_SCREENSHOT) {
      await page.setViewportSize({ width: 1600, height: 1400 });
      await page.click('.proposition-type-keys summary');
      await page.focus(field);
      await page.$eval('#propositionCandidates', el => { el.scrollTop = 0; });
      await page.screenshot({ path: process.env.FOLIO_ENRICH_INSIGHTS_SCREENSHOT, fullPage: true });
      await page.setViewportSize({ width: 1400, height: 950 });
    }
    // Polling, rendering and revisiting the same success reuse the new facts.
    await page.evaluate(async () => { await refreshPostJob(); renderPostJob(); });
    assert.equal(state.statusCalls, 2);
    await revisit(page);
    await page.evaluate(() => refreshPostJob());
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2);
    // A later attempt may be observed without seeing its pending phase.
    state.postJob = { ...state.postJob, push_attempts: 2 };
    state.statusResponses.push({ body: absent });
    await page.evaluate(() => refreshPostJob());
    await waitCorpus(page, 0);
    assert.equal(state.statusCalls, 3);
    assert.match(await page.textContent('.proposition-card .proposition-corpus'), /Not in corpus/);
    await finish('success-dirty-dedupe-later-attempt', page, state);
  }

  // Success during an old status read queues one follow-up, never overlaps it.
  {
    const { page, state, release } = await openPage(browser, absent, { holdStatus: true, postJob: fixture.postJob.awaiting });
    state.statusResponses.push({ body: present });
    await page.click('#propositionCompleteReviewBtn');
    await page.waitForFunction(() => document.getElementById('postJobChips').textContent.includes('Insights: pushed'));
    await page.evaluate(() => refreshPostJob());
    assert.equal(state.statusCalls, 1, 'success cannot start an overlapping status request');
    release();
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2);
    await page.evaluate(() => refreshPostJob());
    assert.equal(state.statusCalls, 2);
    await finish('in-flight-coalescing', page, state);
  }

  // A historical success on a hidden tab needs only its first status read.
  {
    const { page, state } = await openPage(browser, present, { postJob: fixture.postJob.pushed, tab: 'annotated' });
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 1);
    await page.click('.tab[data-tab="propositions"]');
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 1);
    await finish('initial-success-hidden-tab', page, state);
  }

  // Hidden-tab success also invalidates previously cached facts.
  {
    const { page, state } = await openPage(browser, absent, { postJob: fixture.postJob.awaiting });
    await waitCorpus(page, 0);
    await page.click('.tab[data-tab="annotated"]');
    state.statusResponses.push({ body: present });
    await page.click('#postJobCompleteReviewBtn');
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2);
    await page.click('.tab[data-tab="propositions"]');
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2);
    await finish('cached-success-hidden-tab', page, state);
  }

  // Job and sequence guards precede invalidation; late reads cannot repaint a
  // different job, and the pending refresh is retained for a return visit.
  {
    const { page, state, release } = await openPage(browser, absent, { holdStatus: true, postJob: fixture.postJob.awaiting });
    await page.click('#propositionCompleteReviewBtn');
    await page.waitForFunction(() => document.getElementById('postJobChips').textContent.includes('Insights: pushed'));
    state.postJob = fixture.postJob.awaiting;
    await revisit(page, fixture.otherJob.id);
    await waitCorpus(page, 0);
    const oldRead = page.waitForResponse(r => r.url().endsWith(`/enrich/${jobId}/insights-status`));
    release();
    await (await oldRead).finished();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(state.statusByJob[jobId], 1);
    assert.equal(await page.evaluate(() => currentJobId), fixture.otherJob.id);
    assert.match(await bannerText(page), /0 of 3/);
    state.statusResponses.push({ body: present });
    await revisit(page);
    await waitCorpus(page, 2);
    assert.equal(state.statusByJob[jobId], 2);
    const late = barrier();
    state.postResponses.push({ body: { ...fixture.postJob.pushed, push_attempts: 9 }, wait: late.wait });
    const lateRequest = page.waitForRequest(r => r.url().endsWith('/post-job'));
    await page.evaluate(() => { window.latePostJob = refreshPostJob(); });
    await lateRequest;
    await page.evaluate(() => refreshPostJob());
    late.release();
    await page.evaluate(() => window.latePostJob);
    assert.equal(state.statusByJob[jobId], 2, 'an older successful payload must be ignored');
    const otherJobLate = barrier();
    state.postResponses.push({ body: { ...fixture.postJob.pushed, push_attempts: 10 }, wait: otherJobLate.wait });
    const otherJobRequest = page.waitForRequest(r => r.url().endsWith('/post-job'));
    await page.evaluate(() => { window.latePostJob = refreshPostJob(); });
    await otherJobRequest;
    await revisit(page, fixture.otherJob.id);
    await waitCorpus(page, 0);
    otherJobLate.release();
    await page.evaluate(() => window.latePostJob);
    assert.equal(state.statusByJob[fixture.otherJob.id], 1, 'another job cannot be invalidated by a late success');
    await revisit(page);
    await waitCorpus(page, 2);
    assert.equal(state.statusByJob[jobId], 2, 'a rejected job payload cannot invalidate its old cache');
    await finish('navigation-and-stale-payload', page, state);
  }

  // Failed/unconfigured pushes do not refresh. A successful retry does, but a
  // failed status request is terminal until the user chooses manual Refresh.
  {
    const { page, state } = await openPage(browser, absent, { postJob: fixture.postJob.failed });
    await waitCorpus(page, 0);
    await page.evaluate(() => refreshPostJob());
    assert.equal(state.statusCalls, 1);
    state.postJob = { ...fixture.postJob.failed, push_status: 'not_configured' };
    await page.evaluate(() => refreshPostJob());
    assert.equal(state.statusCalls, 1);
    state.postJob = fixture.postJob.failed;
    await page.evaluate(() => refreshPostJob());
    state.statusResponses.push({ body: { detail: 'Unavailable' }, status: 503 });
    await page.click('#postJobRetryBtn');
    await page.waitForFunction(() => document.getElementById('propositionCorpusBannerText').textContent.includes('Corpus status request failed (503).'));
    await page.evaluate(() => refreshPostJob());
    assert.equal(state.statusCalls, 2);
    state.statusResponses.push({ body: absent });
    await page.click('#refreshCorpusStatusBtn');
    await waitCorpus(page, 0);
    assert.equal(state.statusCalls, 3);
    assert.match(await page.textContent('.proposition-card .proposition-corpus'), /Not in corpus/);
    await finish('failed-push-status-error-manual-retry', page, state);
  }

  // Auto-refresh must retain an in-progress hand-added draft and field focus.
  {
    const { page, state } = await openPage(browser, absent, { postJob: fixture.postJob.awaiting });
    await waitCorpus(page, 0);
    await enableReview(page);
    await page.evaluate(async () => {
      const doc = document.getElementById('propositionDocument');
      const range = document.createRange();
      range.selectNodeContents(doc);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      await handlePropositionSelection();
    });
    await page.click('#addPropositionSelectionBtn');
    const draft = '.proposition-card[data-draft="true"]';
    await page.waitForSelector(draft);
    await page.$eval(draft, c => { c.dataset.marker = 'draft-node'; });
    const field = `${draft} select[data-field="disposition"]`;
    await page.selectOption(field, 'accepted');
    const gate = barrier();
    state.statusResponses.push({ body: present, wait: gate.wait });
    await page.click('#postJobCompleteReviewBtn');
    await page.waitForFunction(() => document.getElementById('postJobChips').textContent.includes('Insights: pushed'));
    await page.focus(field);
    gate.release();
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2);
    assert.equal(await page.getAttribute(draft, 'data-marker'), 'draft-node');
    assert.equal(await page.inputValue(field), 'accepted');
    assert.equal(await page.$eval(field, el => el === document.activeElement), true);
    assert.equal(await page.locator(`${draft} .proposition-corpus`).count(), 0);
    await finish('hand-added-draft-focus', page, state);
  }

  {
    const { page, state } = await openPage(browser, absent, { postJob: fixture.postJob.awaiting });
    await page.setViewportSize({ width: 390, height: 844 });
    await waitCorpus(page, 0);
    await enableReview(page);
    await page.selectOption('.proposition-card select[data-field="disposition"]', 'rejected');
    state.statusResponses.push({ body: present });
    await page.click('#propositionCompleteReviewBtn');
    await waitCorpus(page, 2);
    assert.equal(state.statusCalls, 2);
    assert.equal(await page.inputValue('.proposition-card select[data-field="disposition"]'), 'rejected');
    await page.locator('#propositionCorpusBanner').scrollIntoViewIfNeeded();
    if (process.env.FOLIO_ENRICH_INSIGHTS_SCREENSHOT) {
      await page.screenshot({ path: process.env.FOLIO_ENRICH_INSIGHTS_SCREENSHOT.replace(/\.png$/, '-mobile.png'), fullPage: true });
    }
    await finish('mobile-push-preserves-edit', page, state);
  }
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
    await pushRegressions(browser, out);
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(out));
})().catch(e => { console.error('FAILED', e); process.exit(1); });
