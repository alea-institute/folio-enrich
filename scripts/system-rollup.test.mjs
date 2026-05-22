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
