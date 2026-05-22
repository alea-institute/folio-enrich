import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  TIER_RANK,
  normalizeSubsystems,
  computeRollup,
  chipLabel,
} from './system-rollup.mjs';

// ── computeRollup: worst-of-four + quiet green (STATUS-02/03) ──────────────
test('STATUS-02: all-green subsystems roll up to green "System"', () => {
  const r = computeRollup([
    { name: 'Backend', tier: 'green' },
    { name: 'FOLIO', tier: 'green' },
    { name: 'Embedding', tier: 'green' },
    { name: 'spaCy', tier: 'green' },
  ]);
  assert.equal(r.tier, 'green');
  assert.equal(r.worstName, null);
  assert.equal(r.overflow, 0);
  assert.equal(chipLabel(r), 'System');
});

test('STATUS-03: single error names the failing subsystem', () => {
  const r = computeRollup([
    { name: 'Backend', tier: 'green' },
    { name: 'FOLIO', tier: 'green' },
    { name: 'Embedding', tier: 'green' },
    { name: 'spaCy', tier: 'red' },
  ]);
  assert.equal(r.tier, 'red');
  assert.equal(r.worstName, 'spaCy');
  assert.equal(r.overflow, 0);
  assert.equal(chipLabel(r), 'System: spaCy');
});

test('STATUS-03: worst-of-four picks red over green', () => {
  // A single red among greens is the worst (red > orange > green via TIER_RANK).
  const r = computeRollup([
    { name: 'Backend', tier: 'green' },
    { name: 'FOLIO', tier: 'red' },
    { name: 'Embedding', tier: 'green' },
    { name: 'spaCy', tier: 'green' },
  ]);
  assert.equal(r.tier, 'red');
  assert.equal(r.worstName, 'FOLIO');
});

test('STATUS-03: red outranks orange as the worst tier', () => {
  const r = computeRollup([
    { name: 'Backend', tier: 'orange' },
    { name: 'FOLIO', tier: 'red' },
  ]);
  assert.equal(r.tier, 'red');
  assert.equal(r.worstName, 'FOLIO');
});

test('STATUS-03: multiple failures show worst + "+1" overflow', () => {
  // Two reds → worst named + one OTHER non-green beyond the worst.
  const r = computeRollup([
    { name: 'Backend', tier: 'red' },
    { name: 'FOLIO', tier: 'green' },
    { name: 'Embedding', tier: 'green' },
    { name: 'spaCy', tier: 'red' },
  ]);
  assert.equal(r.tier, 'red');
  assert.equal(r.overflow, 1);
  assert.equal(chipLabel(r), `System: ${r.worstName} +1`);
});

test('STATUS-03: overflow counts only OTHER non-green beyond the worst (3 reds → +2)', () => {
  const r = computeRollup([
    { name: 'Backend', tier: 'red' },
    { name: 'FOLIO', tier: 'red' },
    { name: 'Embedding', tier: 'green' },
    { name: 'spaCy', tier: 'red' },
  ]);
  assert.equal(r.tier, 'red');
  assert.equal(r.overflow, 2);
  assert.equal(chipLabel(r), `System: ${r.worstName} +2`);
});

test('STATUS-03: a lone orange rolls up to orange with no overflow', () => {
  const r = computeRollup([
    { name: 'Backend', tier: 'green' },
    { name: 'FOLIO', tier: 'orange' },
    { name: 'Embedding', tier: 'green' },
    { name: 'spaCy', tier: 'green' },
  ]);
  assert.equal(r.tier, 'orange');
  assert.equal(r.worstName, 'FOLIO');
  assert.equal(r.overflow, 0);
  assert.equal(chipLabel(r), 'System: FOLIO');
});

// ── TIER_RANK contract (D-07: red > orange > green) ────────────────────────
test('D-07: TIER_RANK maps red>orange>green', () => {
  assert.equal(TIER_RANK.green, 0);
  assert.equal(TIER_RANK.orange, 1);
  assert.equal(TIER_RANK.red, 2);
});

// ── normalizeSubsystems: shape, order, LLM exclusion (STATUS-02/03/06) ──────
const rowByKey = (rows, key) => rows.find((s) => s.key === key);

test('normalizeSubsystems returns exactly 4 rows in fixed order, no llm', () => {
  const rows = normalizeSubsystems(
    {
      folio_ontology: { status: 'ready', concepts: 10, labels_indexed: 20 },
      embedding: { status: 'ready', provider: 'Local', index_size: 5 },
      spacy: { status: 'ready', version: '3.7.0' },
      llm: { status: 'configured', provider: 'google', model: 'gemini' },
    },
    true,
  );
  assert.equal(rows.length, 4);
  assert.deepEqual(rows.map((s) => s.key), ['backend', 'folio', 'embedding', 'spacy']);
  assert.deepEqual(rows.map((s) => s.name), ['Backend', 'FOLIO', 'Embedding', 'spaCy']);
  assert.equal(rows.some((s) => s.key === 'llm'), false);
});

// ── D-05: Standby (not_loaded) normalizes to GREEN with Standby annotation ──
test('D-05: FOLIO not_loaded normalizes to green (Standby annotation)', () => {
  const rows = normalizeSubsystems({ folio_ontology: { status: 'not_loaded' } }, true);
  const folio = rowByKey(rows, 'folio');
  assert.equal(folio.tier, 'green');
  assert.match(folio.annotation, /Standby/);
});

test('D-05: Embedding not_loaded normalizes to green (Standby annotation)', () => {
  const rows = normalizeSubsystems({ embedding: { status: 'not_loaded' } }, true);
  const emb = rowByKey(rows, 'embedding');
  assert.equal(emb.tier, 'green');
  assert.match(emb.annotation, /Standby/);
});

// ── D-06: Update flags stay GREEN (informational, never a warning) ──────────
test('D-06: FOLIO update_available stays green (Update annotation)', () => {
  const rows = normalizeSubsystems(
    { folio_ontology: { status: 'ready', concepts: 5, labels_indexed: 9, update_status: { update_available: true } } },
    true,
  );
  const folio = rowByKey(rows, 'folio');
  assert.equal(folio.tier, 'green');
  assert.match(folio.annotation, /Update/);
});

test('D-06: FOLIO update_in_progress stays green (Updating annotation)', () => {
  const rows = normalizeSubsystems(
    { folio_ontology: { status: 'ready', concepts: 5, labels_indexed: 9, update_status: { update_in_progress: true } } },
    true,
  );
  const folio = rowByKey(rows, 'folio');
  assert.equal(folio.tier, 'green');
  assert.match(folio.annotation, /Updating/);
});

// ── Error mapping → red ─────────────────────────────────────────────────────
test('spacy error maps to red tier', () => {
  const rows = normalizeSubsystems({ spacy: { status: 'error', message: 'no model' } }, true);
  assert.equal(rowByKey(rows, 'spacy').tier, 'red');
});

test('FOLIO error maps to red and surfaces the backend message', () => {
  const rows = normalizeSubsystems({ folio_ontology: { status: 'error', message: 'load failed' } }, true);
  const folio = rowByKey(rows, 'folio');
  assert.equal(folio.tier, 'red');
  assert.match(folio.metric + ' ' + (folio.annotation || ''), /load failed/);
});

// ── Backend-down: all rows offline/red, Backend row reads offline ───────────
test('backendUp=false maps all rows to red and Backend reads offline', () => {
  const rows = normalizeSubsystems({}, false);
  assert.equal(rows.length, 4);
  for (const r of rows) assert.equal(r.tier, 'red');
  assert.match(rowByKey(rows, 'backend').metric, /Offline/i);
});

// ── Metric preservation (STATUS-04) ─────────────────────────────────────────
test('STATUS-04: FOLIO ready metric preserves concepts and "labels indexed"', () => {
  const rows = normalizeSubsystems(
    { folio_ontology: { status: 'ready', concepts: 1234, labels_indexed: 5678 } },
    true,
  );
  const folio = rowByKey(rows, 'folio');
  assert.equal(folio.tier, 'green');
  assert.match(folio.metric, /concepts/);
  assert.match(folio.metric, /labels indexed/);
});

test('STATUS-04: Embedding ready metric preserves provider and "vectors indexed"', () => {
  const rows = normalizeSubsystems(
    { embedding: { status: 'ready', provider: 'OpenAI', index_size: 42 } },
    true,
  );
  const emb = rowByKey(rows, 'embedding');
  assert.equal(emb.tier, 'green');
  assert.match(emb.metric, /OpenAI/);
  assert.match(emb.metric, /vectors indexed/);
});

test('STATUS-04: spaCy ready metric preserves version and "EntityRuler ready"', () => {
  const rows = normalizeSubsystems({ spacy: { status: 'ready', version: '3.7.2' } }, true);
  const sp = rowByKey(rows, 'spacy');
  assert.equal(sp.tier, 'green');
  assert.match(sp.metric, /3\.7\.2/);
  assert.match(sp.metric, /EntityRuler ready/);
});

// ── D-08: FOLIO row carries the Manage action; no other row does ────────────
test('D-08: only the FOLIO row carries a manage action', () => {
  const rows = normalizeSubsystems({ folio_ontology: { status: 'ready', concepts: 1, labels_indexed: 1 } }, true);
  assert.ok(rowByKey(rows, 'folio').action);
  assert.equal(rowByKey(rows, 'backend').action, undefined);
  assert.equal(rowByKey(rows, 'embedding').action, undefined);
  assert.equal(rowByKey(rows, 'spacy').action, undefined);
});

// ── STATUS-06: the module never reads the LLM subsystem ─────────────────────
test('STATUS-06: llm field is ignored even when present and erroring', () => {
  const rows = normalizeSubsystems(
    {
      folio_ontology: { status: 'ready', concepts: 1, labels_indexed: 1 },
      embedding: { status: 'ready', provider: 'Local', index_size: 1 },
      spacy: { status: 'ready', version: '3.0.0' },
      llm: { status: 'error', message: 'should be ignored' },
    },
    true,
  );
  // An LLM error must NOT pollute the rollup.
  assert.equal(computeRollup(rows).tier, 'green');
  assert.equal(rows.some((s) => s.key === 'llm'), false);
});
