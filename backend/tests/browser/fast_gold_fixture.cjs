// Synthetic acceptance mode for fast_gold_annotation.cjs; no network or persisted data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const [modulePath, base, frontend, fixturePath, scenario] = process.argv.slice(2);
let chromium;
try { ({ chromium } = require(modulePath)); }
catch (error) { console.error(error.message); process.exit(3); }
const { job } = JSON.parse(fs.readFileSync(fixturePath));
const clone = value => structuredClone(value);
const deferred = () => { let release; const promise = new Promise(resolve => { release = resolve; }); return { promise, release }; };

async function run(browser, width) {
  const context = await browser.newContext({ viewport: { width, height: 950 }, hasTouch: true });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const session = { session_id: 'synthetic-session', job_id: job.id, annotator: 'tester', baseline: false, validation_of: 'synthetic-record',
    blind_pending: 0, hand_added: [], candidates: job.result.propositions.map(proposition => ({
      proposition: clone(proposition), original: clone(proposition), outcome: 'unreviewed', explicit_unresolved: false,
    })) };
  const writes = [];
  let failNext = false, holdNext = null, completenessCalls = 0;
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), method = request.method();
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (url.origin !== base) return route.fulfill({ status: 404, body: '' });
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: fs.readFileSync(path.join(frontend, 'index.html')) });
    if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/favicon')) {
      const file = path.join(frontend, url.pathname.replace(/^\/static\//, '').replace(/^\/favicon\.ico$/, 'favicon.svg'));
      if (file.startsWith(frontend) && fs.existsSync(file)) return route.fulfill({ path: file });
      return route.fulfill({ status: 404, body: '' });
    }
    if (url.pathname === '/gold/access') return json({ authenticated: true, via: 'local' });
    if (url.pathname === `/enrich/${job.id}`) return json(job);
    if (url.pathname.endsWith('/insights-status')) return json({ state: 'not_configured', connected: false, results: {}, propositions: {} });
    if (url.pathname === '/gold/sessions') return json([session]);
    if (url.pathname === '/gold/sessions/synthetic-session') return json(session);
    if (url.pathname.endsWith('/completeness')) { completenessCalls++; return json({ complete: false, reasons: ['candidates remain unreviewed'] }); }
    if (url.pathname.startsWith('/gold/sessions/synthetic-session/') && ['PATCH', 'POST', 'DELETE'].includes(method)) {
      const id = decodeURIComponent(url.pathname.split('/').at(-1));
      const body = request.postDataJSON();
      writes.push({ method, id, body });
      const gate = holdNext; holdNext = null;
      if (gate) await gate.promise;
      if (failNext) { failNext = false; return json({ detail: 'Synthetic failed save' }, 503); }
      if (method === 'PATCH') Object.assign(session.candidates.find(item => item.proposition.id === id), clone(body));
      if (method === 'POST') session.hand_added.push(clone(body));
      if (method === 'DELETE') session.hand_added = session.hand_added.filter(item => item.proposition.id !== id);
      return json(session);
    }
    if (url.pathname === '/settings') return json({ proposition_extraction_enabled: true, proposition_taxonomy: {}, task_llm_overrides: {}, llm_provider: '', llm_model: '' });
    return json({ detail: 'Not stubbed' }, 404);
  });
  const card = page.locator('#propositionCandidates .proposition-card');
  const id = () => card.getAttribute('data-candidate-id');
  const key = async value => { await card.focus(); await page.keyboard.press(value); };
  const saved = () => page.waitForFunction(() => document.getElementById('propositionSaveStatus').textContent === 'All actions saved.');
  const failed = () => page.getByRole('button', { name: 'Not saved — retry', exact: true }).waitFor();
  const stored = candidate => session.candidates.find(item => item.proposition.id === candidate);
  const until = async predicate => { for (let i = 0; i < 200; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 10)); } throw new Error('API condition timed out'); };
  // Dispatch the actual DOM pointer listeners, retaining the original node across
  // asynchronous saves. Synthetic events do not own native pointer capture.
  const pointer = async (type, pointerId, x) => page.evaluate(({ type, pointerId, x }) => {
    const node = window.swipeNode || document.querySelector('#propositionCandidates .proposition-card');
    node.setPointerCapture = () => {};
    node.dispatchEvent(new PointerEvent(type, { pointerType: 'touch', pointerId, clientX: x, clientY: 100, bubbles: true }));
  }, { type, pointerId, x });
  try {
    await page.goto(`${base}/?job=${job.id}&tab=propositions`);
    await card.waitFor();
    await page.waitForFunction(() => document.getElementById('propositionModeToggle').checked);
    await until(() => completenessCalls > 0);
    await saved();
    await page.waitForLoadState('networkidle');
    const first = await id();
    if (scenario === 'queue') {
      holdNext = deferred(); const gate = holdNext;
      for (let i = 0; i < 3; i++) await key('a');
      assert.equal(await id(), 'prop-3');
      assert.equal(writes.length, 1, 'queue sends only one request at a time');
      assert.equal(session.candidates.filter(item => item.outcome !== 'unreviewed').length, 0);
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), true);
      failNext = true; gate.release(); await failed();
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), true);
      await page.getByRole('button', { name: 'View unsaved item:', exact: false }).click();
      assert.match(await card.locator('.proposition-review-save-state').innerText(), /Not saved/);
      await page.getByRole('button', { name: 'Not saved — retry', exact: true }).click();
      await saved();
      assert.deepEqual(writes.map(write => write.id), ['prop-0', 'prop-0', 'prop-1', 'prop-2']);
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), false);
      await page.getByRole('button', { name: 'Next unreviewed', exact: true }).click();
      const discarded = await id(); await key('d'); await saved();
      assert.equal(stored(discarded).outcome, 'deleted');
      await key('z'); await saved();
      assert.equal(stored(discarded).outcome, 'unreviewed');
      assert.equal(await id(), discarded);
    } else if (scenario === 'failed-edit') {
      failNext = true; await key('2'); await failed();
      await page.getByRole('button', { name: 'View unsaved item:', exact: false }).click();
      assert.equal(await card.locator('[data-field="proposition_type"]').inputValue(), 'Factual Statement');
      await key('a'); await saved();
      assert.equal(stored(first).proposition.proposition_type, 'Factual Statement', 'approving a failed edit must persist the displayed edit');
      assert.equal(stored(first).outcome, 'edited');
      assert.equal(writes.at(-1).body.proposition.proposition_type, 'Factual Statement');
      // An outcome-only discard cannot supersede another failed edit.
      const next = await id(); failNext = true; await key('2'); await failed();
      await page.getByRole('button', { name: 'View unsaved item:', exact: false }).click();
      await key('d'); await failed();
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), true);
      assert.equal(stored(next).outcome, 'unreviewed');
      await page.getByRole('button', { name: 'Not saved — retry', exact: true }).click(); await saved();
      assert.equal(stored(next).outcome, 'deleted');
      assert.equal(stored(next).proposition.proposition_type, 'Factual Statement');
      // A full-body undo can replace a failed edit directly.
      failNext = true; await key('2'); await failed();
      const undone = writes.at(-1).id; await key('z'); await saved();
      assert.equal(stored(undone).outcome, 'unreviewed');
      assert.equal(stored(undone).proposition.proposition_type, 'Legal Proposition');
    } else if (scenario === 'held-key') {
      // A repeated keydown arrives on the newly focused card after advancement.
      for (const value of ['2', 'a', 'd', 'z']) {
        const before = writes.length;
        holdNext = deferred(); const gate = holdNext;
        await key(value);
        await card.evaluate((node, key) => {
          for (let i = 0; i < 4; i++) document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key, repeat: true, bubbles: true }));
        }, value);
        gate.release(); await saved();
        assert.equal(writes.length - before, 1, `${value}: held key must save exactly one item`);
      }
    } else if (scenario === 'same-type') {
      await key('1'); await saved();
      assert.equal(writes[0].body.outcome, 'accepted', 'same type is an approval');
      assert.equal('proposition' in writes[0].body, false);
      // A dirty card whose edit was reverted is also a no-op edit.
      await card.locator('[data-field="proposition_type"]').selectOption('Factual Statement');
      await card.locator('[data-field="proposition_type"]').selectOption('Legal Proposition');
      await card.locator('button[onclick*="edited"]').click(); await saved();
      assert.equal(writes[1].body.outcome, 'accepted');
      assert.equal('proposition' in writes[1].body, false);
      // A matching type with another changed field must remain an edit.
      const changed = await id();
      await card.locator('[data-field="disposition"]').selectOption('rejected');
      await key('1'); await saved();
      assert.equal(stored(changed).outcome, 'edited');
      assert.equal(stored(changed).proposition.disposition, 'rejected');
      // Confirming a type while an undo is in flight is still a no-op approval.
      holdNext = deferred(); const gate = holdNext;
      await key('z'); await until(() => writes.length === 4);
      await key('1'); gate.release(); await saved();
      assert.equal(writes[4].body.outcome, 'accepted');
      assert.equal('proposition' in writes[4].body, false);
    } else if (scenario === 'discarded') {
      await key('d'); await saved();
      await key('d'); await saved();
      await key('z'); await saved(); // undo switches to the all filter
      await key('ArrowLeft'); assert.equal(await id(), first);
      for (const value of ['2', '[', ']', '{', '}']) await key(value);
      assert.equal(await card.getAttribute('data-dirty'), 'false', 'discarded cards cannot acquire unsavable shortcut edits');
      await key('ArrowRight'); assert.notEqual(await id(), first);
      assert.equal(writes.length, 3);
    } else if (scenario === 'multitouch') {
      await pointer('pointerdown', 1, 100);
      await pointer('pointerdown', 2, 250);
      await pointer('pointerup', 1, 100);
      await pointer('pointerup', 2, 250);
      assert.equal(await id(), first, 'stationary two-finger touch must not discard');
      assert.equal(writes.length, 0);
      // An unrelated pointerup cannot finish an active gesture.
      await pointer('pointerdown', 3, 100);
      await pointer('pointerup', 4, 250);
      assert.equal(await id(), first);
      await pointer('pointercancel', 3, 100);
    } else if (scenario === 'mid-swipe') {
      holdNext = deferred(); const gate = holdNext;
      await key('a'); await until(() => writes.length === 1);
      const swiped = await id();
      await page.evaluate(() => { window.swipeNode = document.querySelector('#propositionCandidates .proposition-card'); });
      await pointer('pointerdown', 1, 100); await pointer('pointermove', 1, 135);
      const calls = completenessCalls;
      gate.release(); await saved(); await until(() => completenessCalls > calls);
      // Wait until both the PATCH and subsequent completeness fetch have landed.
      await page.waitForLoadState('networkidle');
      assert.equal(await card.evaluate(node => node === window.swipeNode), true, 'save completion must preserve the active swipe node');
      await pointer('pointermove', 1, 210); await pointer('pointerup', 1, 210); await saved();
      assert.equal(stored(swiped).outcome, 'accepted', 'swipe survives a mid-gesture save');
      assert.equal(await card.evaluate(node => node === window.swipeNode), false, 'swipe advances after gesture');
      await page.waitForLoadState('networkidle');
      // Cancellation must also release the busy flag and apply the deferred render.
      holdNext = deferred(); const cancelGate = holdNext;
      const count = writes.length; await key('a'); await until(() => writes.length > count);
      const cancelled = await id();
      await page.evaluate(() => { window.swipeNode = document.querySelector('#propositionCandidates .proposition-card'); });
      await pointer('pointerdown', 2, 100);
      cancelGate.release(); await saved(); await page.waitForLoadState('networkidle');
      assert.equal(await card.evaluate(node => node === window.swipeNode), true);
      await pointer('pointercancel', 2, 100);
      assert.equal(await card.evaluate(node => node === window.swipeNode), false, 'cancel flushes the deferred render');
      assert.equal(stored(cancelled).outcome, 'unreviewed');
    } else if (scenario === 'hand-added') {
      const text = job.result.propositions[0].text;
      await page.evaluate(text => {
        const doc = document.getElementById('propositionDocument');
        const walker = document.createTreeWalker(doc, NodeFilter.SHOW_TEXT);
        let node; while ((node = walker.nextNode())) {
          const start = node.textContent.indexOf(text);
          if (start < 0) continue;
          const range = document.createRange(); range.setStart(node, start); range.setEnd(node, start + text.length);
          const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
          doc.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })); break;
        }
      }, text);
      await page.getByRole('button', { name: 'Add as proposition', exact: true }).click();
      const handId = await id();
      assert.equal(await card.getAttribute('data-draft'), 'true');
      await card.locator('[data-field="disposition"]').selectOption('unresolved');
      await card.locator('[data-field="explicit_unresolved"]').check();
      await card.getByRole('button', { name: 'Save hand-added', exact: true }).click(); await saved();
      assert.equal(session.hand_added[0].proposition.text, text);
      await key('z'); await saved();
      assert.equal(session.hand_added.length, 0);
      assert.equal(writes.at(-1).method, 'DELETE'); assert.equal(writes.at(-1).id, handId);
    } else throw new Error(`Unknown scenario ${scenario}`);
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
}
(async () => {
  let browser;
  try { browser = await chromium.launch(); }
  catch (error) { console.error(error.message); process.exit(3); }
  try { for (const width of [1280, 390]) await run(browser, width); }
  finally { await browser.close(); }
  console.log(JSON.stringify({ scenario, widths: [1280, 390] }));
})().catch(error => { console.error(error); process.exit(1); });
