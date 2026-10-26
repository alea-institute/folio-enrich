/* Manual: node tests/browser/fast_gold_annotation.cjs /path/to/playwright http://127.0.0.1:<port>
 * Requires an isolated local backend; creates local Palsgraf sessions only.
 * CI: append <frontend dir> <fixture json> <scenario> to run the synthetic API.
 */
if (process.argv[4]) {
  require('./fast_gold_fixture.cjs');
} else {
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium, request } = require(process.argv[2]);
const base = process.argv[3] || process.env.FAST_ANNOTATION_BASE_URL;
assert.ok(base, 'Pass the isolated local server base URL');
const screenshotRoot = process.env.FAST_ANNOTATION_SCREENSHOTS || require('node:os').homedir();
(async () => {
  const browser = await chromium.launch({ headless: true });
  const api = await request.newContext({ baseURL: base });
  const results = [];
  const sessions = [];
  try {
    for (const width of [1280, 390]) {
      const response = await api.post('/gold/validation-sessions', { data: { slug: 'palsgraf-248-ny-339' } });
      assert.equal(response.status(), 201);
      let session = await response.json();
      // The validation API resumes its existing local session. Reset only this
      // isolated server's test outcomes, each via an explicit inverse PATCH.
      for (const item of session.candidates.filter(item => item.outcome !== 'unreviewed')) {
        const reset = await api.patch(`/gold/sessions/${session.session_id}/candidates/${encodeURIComponent(item.proposition.id)}`, {
          data: { outcome: 'unreviewed', proposition: item.original, explicit_unresolved: item.explicit_unresolved },
        });
        assert.equal(reset.status(), 200);
      }
      for (const item of session.hand_added) {
        assert.equal((await api.delete(`/gold/sessions/${session.session_id}/annotations/${encodeURIComponent(item.proposition.id)}`)).status(), 200);
      }
      session = await (await api.get(`/gold/sessions/${session.session_id}`)).json();
      sessions.push({ width, session_id: session.session_id, job_id: session.job_id });
      assert.equal(session.candidates.length, 104);
      const job = await (await api.get(`/enrich/${session.job_id}`)).json();
      const fullText = job.result.canonical_text.full_text;
      const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      // The entire run is loopback-only, including incidental third-party assets.
      await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
      const card = page.locator('#propositionCandidates .proposition-card');
      const id = () => card.getAttribute('data-candidate-id');
      const focusCard = () => card.focus();
      const saved = () => page.waitForFunction(() => document.getElementById('propositionSaveStatus').textContent === 'All actions saved.');
      const stored = async () => (await api.get(`/gold/sessions/${session.session_id}`)).json();
      await page.goto(`${base}/?job=${session.job_id}&tab=propositions`);
      await card.waitFor();
      await page.waitForFunction(() => document.getElementById('propositionModeToggle').checked);
      const ordered = [...session.candidates].sort((a, b) => a.proposition.start_char - b.proposition.start_char || a.proposition.end_char - b.proposition.end_char);
      assert.equal(await id(), ordered[0].proposition.id, 'direct link resumes first unreviewed');

      let release;
      const gate = new Promise(resolve => { release = resolve; });
      let requests = 0;
      const writes = [];
      const pattern = '**/gold/sessions/*/candidates/*';
      const slowFail = async route => {
        if (route.request().method() !== 'PATCH') return route.continue();
        requests++;
        writes.push({ id: decodeURIComponent(route.request().url().split('/').at(-1)), body: route.request().postDataJSON() });
        if (requests === 1) await gate;
        if (requests === 2) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Simulated local failure' }) });
        const result = await route.fetch();
        await route.fulfill({ response: result });
      };
      await page.route(pattern, slowFail);
      await focusCard();
      const shown = [await id()];
      for (let i = 0; i < 5; i++) {
        await page.keyboard.press('a');
        shown.push(await id());
      }
      assert.equal(new Set(shown).size, 6, 'AE1: five immediate advances');
      assert.equal(requests, 1, 'AE1: ordered queue with first save still unresolved');
      assert.equal((await stored()).candidates.filter(c => c.outcome !== 'unreviewed').length, 0);
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), true);
      release();
      await page.getByRole('button', { name: 'Not saved — retry', exact: true }).waitFor();
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), true);
      await page.screenshot({ path: path.join(screenshotRoot, `fast-annotation-${width}-unsaved.png`), fullPage: true });
      await page.getByRole('button', { name: 'View unsaved item:', exact: false }).click();
      assert.equal(await id(), writes[1].id);
      assert.match(await card.locator('.proposition-review-save-state').innerText(), /Not saved/);
      await page.getByRole('button', { name: 'Not saved — retry', exact: true }).click();
      await saved();
      assert.equal((await stored()).candidates.filter(c => c.outcome === 'accepted').length, 5);
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), false);
      await page.unroute(pattern, slowFail);
      results.push(`${width}: AE1 instant queue, failure visibility, export block, retry PASS`);

      await page.getByRole('button', { name: 'Next unreviewed', exact: true }).click();
      await focusCard();
      const discarded = await id();
      await page.keyboard.press('d');
      assert.notEqual(await id(), discarded);
      await saved();
      assert.equal((await stored()).candidates.find(c => c.proposition.id === discarded).outcome, 'deleted');
      await focusCard();
      await page.keyboard.press('z');
      assert.equal(await id(), discarded);
      await saved();
      assert.equal((await stored()).candidates.find(c => c.proposition.id === discarded).outcome, 'unreviewed');
      results.push(`${width}: AE2 completed discard undo persists unreviewed PASS`);
      let releaseUndo;
      const undoGate = new Promise(resolve => { releaseUndo = resolve; });
      let pendingRequest = false;
      const pendingSave = async route => {
        if (route.request().method() !== 'PATCH') return route.continue();
        if (!pendingRequest) { pendingRequest = true; await undoGate; }
        const result = await route.fetch(); await route.fulfill({ response: result });
      };
      await page.route(pattern, pendingSave);
      await focusCard(); await page.keyboard.press('d');
      await focusCard(); await page.keyboard.press('z');
      assert.equal(await id(), discarded, 'undo is instant before original PATCH resolves');
      await card.locator('[data-field="proposition_type"]').focus();
      await card.evaluate(node => { node.dataset.editorMarker = 'preserve-focused-editor'; });
      releaseUndo(); await saved();
      assert.equal(await card.getAttribute('data-editor-marker'), 'preserve-focused-editor');
      assert.equal(await card.locator('[data-field="proposition_type"]').evaluate(node => node === document.activeElement), true);
      assert.doesNotMatch(await card.locator('.proposition-review-save-state').innerText(), /Saving/);
      await page.unroute(pattern, pendingSave);
      assert.equal((await stored()).candidates.find(c => c.proposition.id === discarded).outcome, 'unreviewed');
      results.push(`${width}: undo during in-flight save reconciles inverse PASS`);

      const prior = (await stored()).candidates.find(c => c.proposition.id === discarded).proposition;
      await focusCard();
      await page.keyboard.press('2');
      assert.notEqual(await id(), discarded);
      await saved();
      let changed = (await stored()).candidates.find(c => c.proposition.id === discarded);
      assert.equal(changed.outcome, 'edited');
      assert.equal(changed.proposition.proposition_type, 'Factual Statement');
      await focusCard();
      await page.keyboard.press('z');
      await saved();
      assert.deepEqual((await stored()).candidates.find(c => c.proposition.id === discarded).proposition, prior);
      const oldStart = Number(await card.locator('[data-field="start_char"]').inputValue());
      await focusCard(); await page.keyboard.press('[');
      const earlierStart = Number(await card.locator('[data-field="start_char"]').inputValue());
      const priorWordStart = [...fullText.matchAll(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu)].map(word => word.index).filter(index => index < oldStart).at(-1);
      assert.equal(earlierStart, priorWordStart);
      await page.keyboard.press(']');
      assert.equal(Number(await card.locator('[data-field="start_char"]').inputValue()), oldStart);
      const oldEnd = Number(await card.locator('[data-field="end_char"]').inputValue());
      await focusCard();
      await page.keyboard.press('}');
      const newEnd = Number(await card.locator('[data-field="end_char"]').inputValue());
      const nextWord = fullText.slice(oldEnd).match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/u);
      assert.equal(newEnd, oldEnd + nextWord.index + nextWord[0].length);
      await page.keyboard.press('{');
      assert.equal(Number(await card.locator('[data-field="end_char"]').inputValue()), oldEnd);
      await page.keyboard.press('}');
      const start = Number(await card.locator('[data-field="start_char"]').inputValue());
      assert.equal(await card.locator('.proposition-quote').innerText(), `“${fullText.slice(start, newEnd)}”`);
      await card.locator('[data-field="proposition_type"]').focus();
      await page.keyboard.press('a');
      assert.equal(await id(), discarded, 'input keys cannot approve');
      await focusCard();
      await page.keyboard.press('a');
      await saved();
      await focusCard();
      await page.keyboard.press('z');
      await saved();
      assert.deepEqual((await stored()).candidates.find(c => c.proposition.id === discarded).proposition, prior);
      results.push(`${width}: numbered type, edited inverse, one-word span preview, input exclusion PASS`);

      const selectionText = 'the risk reasonably to be perceived defines the duty to be obeyed';
      assert.ok(fullText.toLowerCase().includes(selectionText));
      const actual = fullText.slice(fullText.toLowerCase().indexOf(selectionText), fullText.toLowerCase().indexOf(selectionText) + selectionText.length);
      await page.evaluate(text => {
        const doc = document.getElementById('propositionDocument');
        const offset = doc.textContent.indexOf(text);
        if (offset < 0) throw new Error('selection phrase missing');
        const walker = document.createTreeWalker(doc, NodeFilter.SHOW_TEXT);
        let node, seen = 0, first, last;
        while ((node = walker.nextNode())) {
          const end = seen + node.textContent.length;
          if (!first && offset >= seen && offset < end) first = [node, offset - seen];
          if (offset + text.length > seen && offset + text.length <= end) { last = [node, offset + text.length - seen]; break; }
          seen = end;
        }
        const range = document.createRange();
        range.setStart(...first); range.setEnd(...last);
        const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        doc.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
      }, actual);
      await page.getByRole('button', { name: 'Add as proposition', exact: true }).click();
      assert.equal(await card.locator('.proposition-quote').innerText(), `“${actual}”`);
      assert.equal(await card.locator('[data-field="proposition_type"]').evaluate(node => document.activeElement === node), true);
      await card.locator('[data-field="explicit_unresolved"]').check();
      const handId = await id();
      const addPattern = '**/gold/sessions/*/annotations';
      const lostAddResponse = async route => {
        if (route.request().method() !== 'POST') return route.continue();
        await route.fetch();
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Simulated lost POST response after persistence' }) });
      };
      await page.route(addPattern, lostAddResponse);
      await card.getByRole('button', { name: 'Save hand-added', exact: true }).click();
      await page.getByRole('button', { name: 'Not saved — retry', exact: true }).waitFor();
      assert.equal(await page.locator('#exportGoldBtn').isDisabled(), true);
      await page.unroute(addPattern, lostAddResponse);
      await page.getByRole('button', { name: 'Not saved — retry', exact: true }).click();
      await saved();
      assert.equal((await stored()).hand_added.filter(item => item.proposition.id === handId).length, 1);
      assert.equal((await stored()).hand_added.find(item => item.proposition.id === handId).proposition.text, actual);
      await focusCard();
      await page.keyboard.press('z');
      await saved();
      assert.ok(!(await stored()).hand_added.some(item => item.proposition.id === handId));
      results.push(`${width}: AE3 exact selected quote saved; hand-added undo deletes on server PASS`);

      await page.getByRole('button', { name: 'Next unreviewed', exact: true }).click();
      await focusCard();
      await page.keyboard.press('?');
      assert.equal(await page.locator('#propositionHelp').evaluate(node => node.open), true);
      await page.keyboard.press('Escape');
      for (let i = 0; i < 5; i++) { await focusCard(); await page.keyboard.press('a'); }
      await saved();
      assert.equal((await stored()).candidates.filter(c => c.outcome !== 'unreviewed').length, 10);
      const expectedNext = await id();
      await page.reload();
      await card.waitFor();
      assert.equal(await id(), expectedNext, 'server outcomes determine resume');
      assert.match(await page.locator('#propositionReviewSummary').innerText(), /10 of 104 reviewed/i);
      results.push(`${width}: ten reviewed, server-backed reload resume, help PASS`);

      // Browser pointer events exercise touch gesture recognizer, including cancellation.
      async function swipe(dx, dy, cancel = false) {
        await card.locator('.proposition-quote').scrollIntoViewIfNeeded();
        await card.evaluate((node, { dx, dy, cancel }) => {
          const rect = node.getBoundingClientRect();
          const x = rect.left + 100, y = rect.top + 30;
          const fire = (type, clientX, clientY) => node.dispatchEvent(new PointerEvent(type, { pointerId: 19, pointerType: 'touch', clientX, clientY, bubbles: true }));
          // Synthetic events have no browser-owned pointer capture.
          const capture = node.setPointerCapture;
          node.setPointerCapture = () => {};
          fire('pointerdown', x, y);
          node.setPointerCapture = capture;
          fire('pointermove', x + dx, y + dy);
          fire(cancel ? 'pointercancel' : 'pointerup', x + dx, y + dy);
        }, { dx, dy, cancel });
      }
      const beforeSwipe = await id();
      await swipe(35, 2); assert.equal(await id(), beforeSwipe);
      await swipe(110, 180); assert.equal(await id(), beforeSwipe);
      await swipe(110, 2, true); assert.equal(await id(), beforeSwipe);
      await swipe(110, 2); assert.notEqual(await id(), beforeSwipe);
      await saved();
      assert.equal((await stored()).candidates.find(c => c.proposition.id === beforeSwipe).outcome, 'accepted');
      const leftId = await id();
      await swipe(-110, 2); assert.notEqual(await id(), leftId);
      await saved();
      assert.equal((await stored()).candidates.find(c => c.proposition.id === leftId).outcome, 'deleted');
      if (width === 390) {
        const cdp = await context.newCDPSession(page);
        async function nativeSwipe(dx, dy) {
          await card.locator('.proposition-quote').scrollIntoViewIfNeeded();
          const box = await card.locator('.proposition-quote').boundingBox();
          const x = box.x + 45, y = Math.max(140, box.y + 15);
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
          for (let step = 1; step <= 8; step++) {
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + dx * step / 8, y: y + dy * step / 8 }] });
            await new Promise(resolve => setTimeout(resolve, 16));
          }
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        }
        const nativeId = await id();
        await nativeSwipe(20, 2); assert.equal(await id(), nativeId);
        await nativeSwipe(20, 120); assert.equal(await id(), nativeId);
        await nativeSwipe(120, 2);
        assert.notEqual(await id(), nativeId, 'native Chromium touch swipe approves');
        await saved();
        assert.equal((await stored()).candidates.find(c => c.proposition.id === nativeId).outcome, 'accepted');
        const nativeLeftId = await id();
        await nativeSwipe(-100, 2); assert.notEqual(await id(), nativeLeftId, 'native touch swipe discards');
        await saved();
        assert.equal((await stored()).candidates.find(c => c.proposition.id === nativeLeftId).outcome, 'deleted');
        await cdp.detach();
        results.push(`${width}: native Chromium touch right/left commit, short/vertical cancel PASS`);
        const bar = page.locator('#propositionPhoneBar');
        assert.equal(await bar.isVisible(), true);
        const rect = await bar.boundingBox();
        assert.ok(rect.y + rect.height <= 901 && rect.y >= 0);
        for (const button of await bar.locator('button').all()) {
          const r = await button.boundingBox();
          assert.ok(r.height >= 44 && r.width >= 44);
          await button.focus();
          assert.equal(await button.evaluate(node => node === document.activeElement), true);
        }
        await card.evaluate(node => { node.parentElement.scrollTop += 500; });
        const after = await bar.boundingBox();
        assert.equal(after.y, rect.y);
        await page.screenshot({ path: path.join(screenshotRoot, `fast-annotation-${width}-scrolled.png`), fullPage: true });
        await card.locator('.proposition-quote').scrollIntoViewIfNeeded();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
      await page.screenshot({ path: path.join(screenshotRoot, `fast-annotation-${width}-review.png`), fullPage: true });
      const accessPattern = '**/gold/access';
      const deniedAccess = route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false, via: null, email: null }) });
      await page.route(accessPattern, deniedAccess);
      await page.reload();
      await page.waitForFunction(() => document.getElementById('propositionAnnotationTokenHint').getAttribute('role') === 'alert');
      assert.equal(await page.locator('#propositionModeToggle').isChecked(), false);
      assert.equal(await card.locator('[data-field="proposition_type"]').isDisabled(), true);
      await page.unroute(accessPattern, deniedAccess);
      results.push(`${width}: unauthorized direct link stays read-only PASS`);
      assert.deepEqual(errors, []);
      results.push(`${width}: AE4 right/left swipe, short/vertical/cancel safety${width === 390 ? ', fixed phone bar and 44px targets' : ''} PASS`);
      await context.close();
    }
    console.log(JSON.stringify({ results, sessions }, null, 2));
  } finally { await api.dispose(); await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });

}
