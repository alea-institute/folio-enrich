// Browser test for the post-job review/push card (left panel) and its
// Propositions-tab bar. Driven by backend/tests/test_post_job_browser.py.
// Serves the real frontend/index.html through page.route and stubs every API
// call (no backend or port). Prints one JSON line of results.
// Exit 3 = Playwright/Chromium unavailable (the pytest wrapper skips).
//
// argv: <playwright module path> <frontend dir> <fixture json path>
const fs = require('fs');
const path = require('path');

const [playwrightPath, frontendDir, fixturePath] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require(playwrightPath)); } catch (e) { console.error('playwright unavailable:', e.message); process.exit(3); }

const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const ORIGIN = 'http://folio-enrich.test';
const CONTENT_TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.html': 'text/html' };

function payload(jobId, postJob, extra = {}) {
  return { job_id: jobId, job_status: 'completed', legacy: false, push_in_flight: false,
    insights_configured: true, push_allowed: true, post_job: postJob, ...extra };
}

async function openPage(browser, { prefs = {}, pushAllowed = true, query = '' } = {}) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const state = { errors: [], requests: [], postJob: JSON.parse(JSON.stringify(fixture.postJob)) };
  page.on('pageerror', e => state.errors.push(String(e)));
  await page.addInitScript(p => { for (const [k, v] of Object.entries(p)) localStorage.setItem(k, v); }, prefs);
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
    state.requests.push(`${method} ${url.pathname}`);
    if (url.pathname === '/settings') return json({ post_job_review_default: false, post_job_push_default: false, insights_configured: true, proposition_extraction_enabled: true, proposition_taxonomy: {}, task_llm_overrides: {}, llm_provider: '', llm_model: '' });
    if (url.pathname === '/enrich/push-access') return json({ push_allowed: pushAllowed, insights_configured: true });
    for (const [name, job] of Object.entries(fixture.jobs)) {
      if (url.pathname === `/enrich/${job.id}`) return json(job);
      if (url.pathname === `/enrich/${job.id}/post-job`) return json(payload(job.id, state.postJob[name], { push_allowed: pushAllowed }));
      if (url.pathname === `/enrich/${job.id}/insights-push` && method === 'POST') {
        state.postJob[name] = fixture.postJob.pushed;
        return json(payload(job.id, state.postJob[name]));
      }
      if (url.pathname === `/enrich/${job.id}/review/complete` && method === 'POST') {
        state.postJob[name] = { ...state.postJob[name], review_status: 'completed', push_status: 'pending' };
        return json(payload(job.id, state.postJob[name]));
      }
    }
    if (url.pathname === '/enrich' && method === 'POST') {
      state.submitted = JSON.parse(route.request().postData() || '{}');
      return json({ job_id: fixture.runningJobId, status: 'pending', post_job: null }, 202);
    }
    if (url.pathname === `/enrich/${fixture.runningJobId}`) return json({ ...fixture.jobs.pushed, id: fixture.runningJobId, status: 'enriching' });
    return json({ detail: 'Not stubbed' }, 404);
  });
  await page.goto(`${ORIGIN}/${query}`);
  await page.waitForSelector('#postJobPanel');
  return { page, state };
}

const chips = page => page.textContent('#postJobChips');
async function waitChips(page, re) {
  await page.waitForFunction(r => new RegExp(r).test(document.getElementById('postJobChips').textContent), re.source, { timeout: 10000 });
  return chips(page);
}

(async () => {
  let browser;
  try { browser = await chromium.launch(); } catch (e) { console.error('chromium unavailable:', e.message.split('\n')[0]); process.exit(3); }
  const out = { errors: [] };
  try {
    // 1. localStorage defaults prefill the submission toggles.
    {
      const { page, state } = await openPage(browser, { prefs: { postJobReview: 'true', postJobPush: 'true' } });
      await page.waitForFunction(() => document.getElementById('postJobNote').textContent.length > 0);
      out.prefill = { review: await page.isChecked('#postJobReviewToggle'), push: await page.isChecked('#postJobPushToggle'),
        heading: await page.textContent('#postJobHeading') };
      out.errors.push(...state.errors.map(e => `prefill: ${e}`));
      await page.close();
    }
    // 2. Without push access the push toggle is disabled with an explanation.
    {
      const { page, state } = await openPage(browser, { prefs: { postJobPush: 'true' }, pushAllowed: false });
      await page.waitForFunction(() => document.getElementById('postJobPushToggle').disabled);
      out.noAccess = { pushChecked: await page.isChecked('#postJobPushToggle'), note: await page.textContent('#postJobNote') };
      out.errors.push(...state.errors.map(e => `noAccess: ${e}`));
      await page.close();
    }
    // 3. Chips for awaiting / pushed / failed jobs; Retry on failed.
    for (const name of ['awaiting', 'pushed', 'failed']) {
      const { page, state } = await openPage(browser, { query: `?job=${fixture.jobs[name].id}` });
      out[name] = { chips: await waitChips(page, /Insights:/) };
      out[name].completeVisible = await page.isVisible('#postJobCompleteReviewBtn');
      out[name].retryVisible = await page.isVisible('#postJobRetryBtn');
      out[name].heading = await page.textContent('#postJobHeading');
      if (name === 'failed') {
        out.failed.title = await page.getAttribute('#postJobChips .post-job-chip.bad', 'title');
        await page.click('#postJobRetryBtn');
        out.failed.afterRetry = await waitChips(page, /pushed \(/);
        out.failed.retryVisibleAfter = await page.isVisible('#postJobRetryBtn');
      }
      if (name === 'awaiting') {
        await page.click('.tab[data-tab="propositions"]');
        await page.waitForSelector('#propositionPostJobBar:not([style*="display: none"])', { timeout: 10000 });
        out.awaiting.barCompleteVisible = await page.isVisible('#propositionCompleteReviewBtn');
      }
      out.errors.push(...state.errors.map(e => `${name}: ${e}`));
      await page.close();
    }
    // 4. Resubmitting after a completed job shows the running state.
    {
      const { page, state } = await openPage(browser, { query: `?job=${fixture.jobs.pushed.id}`, prefs: { postJobReview: 'false', postJobPush: 'true' } });
      await waitChips(page, /pushed \(/);
      await page.evaluate(() => { document.getElementById('docInput').value = 'We hold that the rule applies.'; });
      await page.evaluate(() => { _llmBannerDismissed = true; });
      await page.click('#enrichBtn');
      await page.waitForFunction(id => currentJobId === id, fixture.runningJobId, { timeout: 10000 });
      await waitChips(page, /after the run/);
      out.resubmit = {
        heading: await page.textContent('#postJobHeading'),
        chips: await chips(page),
        togglesDisabled: await page.isDisabled('#postJobReviewToggle') && await page.isDisabled('#postJobPushToggle'),
        submitted: { review: state.submitted?.review_before_continuing, push: state.submitted?.push_to_insights },
      };
      out.errors.push(...state.errors.map(e => `resubmit: ${e}`));
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(out));
})().catch(e => { console.error('FAILED', e); process.exit(1); });
