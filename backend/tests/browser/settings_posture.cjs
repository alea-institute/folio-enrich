// Browser test for the settings modal's public vs local posture. Driven by
// backend/tests/test_settings_posture_browser.py. Serves the real
// frontend/index.html through page.route and stubs every API call (no backend
// or port). Prints one JSON line of results.
// Exit 3 = Playwright/Chromium unavailable (the pytest wrapper skips).
//
// argv: <playwright module path> <frontend dir>
const fs = require('fs');
const path = require('path');

const [playwrightPath, frontendDir] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require(playwrightPath)); } catch (e) { console.error('playwright unavailable:', e.message); process.exit(3); }

const ORIGIN = 'http://folio-enrich.test';
const JOB_ID = '00000000-0000-4000-8000-000000000001';
const PROVIDERS = {
  google: { display_name: 'Google', requires_api_key: true, default_model: 'gemini-a', api_key_set: false },
  openai: { display_name: 'OpenAI', requires_api_key: true, default_model: 'gpt-a', api_key_set: false },
};
const MODELS = {
  google: [{ id: 'gemini-a', name: 'gemini-a' }],
  openai: [{ id: 'gpt-a', name: 'gpt-a' }, { id: 'gpt-b', name: 'gpt-b' }],
};

async function openPage(context, { isPublic, putStatus = 200 }) {
  const page = await context.newPage();
  const state = { errors: [], requests: [] };
  page.on('pageerror', e => state.errors.push(String(e)));
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (url.origin !== ORIGIN) return route.fulfill({ status: 404, body: '' });
    if (url.pathname === '/') return route.fulfill({ status: 200, contentType: 'text/html', body: fs.readFileSync(path.join(frontendDir, 'index.html')) });
    if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/favicon')) return route.fulfill({ status: 404, body: '' });
    state.requests.push(`${method} ${url.pathname}`);
    if (url.pathname === '/settings' && method === 'PUT') {
      state.putBody = JSON.parse(route.request().postData() || '{}');
      return putStatus === 200 ? json({ status: 'ok' }) : json({ detail: 'Valid X-Admin-Token required' }, putStatus);
    }
    if (url.pathname === '/settings') return json({
      require_user_api_key: isPublic, llm_provider: 'google', llm_model: 'gemini-a',
      translation_matching_enabled: false, task_llm_overrides: {}, proposition_taxonomy: {},
      post_job_review_default: false, post_job_push_default: false, insights_configured: false,
    });
    if (url.pathname === '/settings/providers') return json({ providers: PROVIDERS, current: { provider: 'google', model: 'gemini-a' } });
    if (url.pathname === '/settings/known-models') return json({ models: MODELS });
    if (url.pathname === '/enrich' && method === 'POST') {
      state.submitted = JSON.parse(route.request().postData() || '{}');
      return json({ job_id: JOB_ID, status: 'pending', post_job: null }, 202);
    }
    return json({ detail: 'Not stubbed' }, 404);
  });
  await page.goto(`${ORIGIN}/`);
  await page.waitForFunction(p => _requireUserKey === p && document.getElementById('providerSelect').options.length > 0, isPublic);
  return { page, state };
}

// Open the modal, pick OpenAI gpt-b with a key, Save.
async function saveOpenAI(page) {
  await page.evaluate(() => openSettings());
  await page.waitForSelector('#settingsKey_openai');
  await page.check('input[name="settingsActiveProvider"][value="openai"]');
  await page.selectOption('#settingsModel_openai', 'gpt-b');
  await page.fill('#settingsKey_openai', 'sk-user-key');
  const translationDisabled = await page.isDisabled('#translationMatchingEnabled');
  await page.evaluate(() => saveSettings());
  return translationDisabled;
}

const puts = state => state.requests.filter(r => r === 'PUT /settings').length;
const toast = page => page.evaluate(() => document.getElementById('infoToast')?.textContent || '');

(async () => {
  let browser;
  try { browser = await chromium.launch(); } catch (e) { console.error('chromium unavailable:', e.message.split('\n')[0]); process.exit(3); }
  const out = { errors: [] };
  try {
    // 1. Public posture: choices stay in this browser; no server PUT.
    {
      const context = await browser.newContext();
      const { page, state } = await openPage(context, { isPublic: true });
      out.public = { translationDisabled: await saveOpenAI(page) };
      out.public.putsAfterSave = puts(state);
      out.public.localChoice = await page.evaluate(() => localStorage.getItem('folio_enrich_llm_choice'));
      out.public.toast = await toast(page);
      await page.close();
      // Reload: the browser's own choice beats the server default.
      const again = await openPage(context, { isPublic: true });
      out.public.afterReload = await again.page.evaluate(() => ({
        provider: document.getElementById('providerSelect').value,
        model: document.getElementById('modelSelect').value,
        key: document.getElementById('apiKeyInput').value,
      }));
      await again.page.evaluate(() => { document.getElementById('docInput').value = 'The court held the contract void.'; _llmBannerDismissed = true; });
      await again.page.click('#enrichBtn');
      await again.page.waitForFunction(() => currentJobId !== null, null, { timeout: 10000 });
      out.public.putsAfterSubmit = puts(again.state);
      const s = again.state.submitted || {};
      out.public.submitted = { provider: s.llm_provider, model: s.llm_model, key: s.api_key };
      out.errors.push(...state.errors.map(e => `public: ${e}`), ...again.state.errors.map(e => `public-reload: ${e}`));
      await context.close();
    }
    // 2. Local posture, server refuses (admin token configured): clear message.
    {
      const context = await browser.newContext();
      const { page, state } = await openPage(context, { isPublic: false, putStatus: 403 });
      out.local403 = { translationDisabled: await saveOpenAI(page) };
      await page.waitForSelector('#infoToast');
      out.local403.puts = puts(state);
      out.local403.toast = await toast(page);
      out.errors.push(...state.errors.map(e => `local403: ${e}`));
      await context.close();
    }
    // 3. Local posture, open server: saves server defaults as before.
    {
      const context = await browser.newContext();
      const { page, state } = await openPage(context, { isPublic: false });
      await saveOpenAI(page);
      out.local = { puts: puts(state), body: state.putBody, toast: await toast(page) };
      out.errors.push(...state.errors.map(e => `local: ${e}`));
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(out));
})().catch(e => { console.error('FAILED', e); process.exit(1); });
