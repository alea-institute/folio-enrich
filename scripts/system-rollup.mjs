// Pure subsystem-health rollup logic for the consolidated "System" status chip.
//
// Pure, testable module mirroring the style of scripts/flags.mjs.
// normalizeSubsystems()/computeRollup()/chipLabel() are inlined into
// frontend/index.html (single-file frontend, no build step) — keep the two
// byte-identical so these unit tests stay authoritative. The inline copy in
// index.html drops the `export` keyword; everything else must match.
//
// Decisions encoded here:
//   D-05 — FOLIO/Embedding `not_loaded` (Standby) normalizes to GREEN tier.
//   D-06 — FOLIO update_available / update_in_progress normalizes to GREEN tier.
//   D-07 — tier ranking red > orange > green (TIER_RANK / computeRollup).
//   D-10 — healthy chip label is exactly "System".
//   D-11 — degraded chip label is "System: {Subsystem}" + optional " +{N}".
// STATUS-06 — the LLM subsystem is EXCLUDED from the rollup; this module never
//             reads the LLM field.

// D-07: tier mapping red > orange > green.
export const TIER_RANK = { green: 0, orange: 1, red: 2 };

// computeRollup: worst-of-four, red > orange > green; "+N" = other non-green
// subsystems beyond the worst. The D-05/D-06 Standby/Update→green mapping is
// applied upstream in normalizeSubsystems (one place), NOT here.
export function computeRollup(subsystems) {
  let worst = { name: null, tier: 'green' };
  let failCount = 0;
  for (const s of subsystems) {
    if (TIER_RANK[s.tier] > TIER_RANK['green']) failCount++;
    if (TIER_RANK[s.tier] > TIER_RANK[worst.tier]) worst = s;
  }
  const overflow = Math.max(0, failCount - 1);
  return { tier: worst.tier, worstName: worst.name, overflow };
}

export function chipLabel(rollup) {
  if (rollup.tier === 'green') return 'System';                // D-10
  let label = `System: ${rollup.worstName}`;                   // D-11
  if (rollup.overflow > 0) label += ` +${rollup.overflow}`;    // D-11
  return label;
}

// Inline number formatter so node:test stays standalone (no DOM, no imports
// beyond node: built-ins). Mirrors the `.toLocaleString()` calls in the
// current index.html setChip() tooltips.
function fmt(n) {
  return Number(n || 0).toLocaleString();
}

// normalizeSubsystems: map raw /health/detail JSON + backend reachability to a
// fixed-order array of 4 presentation rows for the consolidated System chip.
// LLM is EXCLUDED (STATUS-06) — this function never reads the LLM subsystem.
//
// Row shape: { key, name, tier, statusWord, metric, annotation, action? }
//   key        — stable id: 'backend' | 'folio' | 'embedding' | 'spacy'
//   name       — display name: 'Backend' | 'FOLIO' | 'Embedding' | 'spaCy'
//   tier       — 'green' | 'red' (D-05/D-06 keep Standby/Update green)
//   statusWord — terse status-bar word (STATUS-05: text, not color alone)
//   metric     — preserved metric string (STATUS-04), verbatim from the
//                Metric Preservation Map (03-RESEARCH.md:352-368)
//   annotation — informational sub-line (Standby/Update), never a warning (D-06)
//   action     — 'manage-folio' on the FOLIO row ONLY (D-08); absent elsewhere
//
// backendUp=false (the /health probe failed): every row is red and the
// dependents read "Backend offline", mirroring index.html:4044-4050.
export function normalizeSubsystems(detail, backendUp) {
  const d = detail || {};

  if (backendUp === false) {
    return [
      { key: 'backend', name: 'Backend', tier: 'red', statusWord: 'Offline', metric: 'Offline — cannot reach backend' },
      { key: 'folio', name: 'FOLIO', tier: 'red', statusWord: 'Offline', metric: 'Backend offline', action: 'manage-folio' },
      { key: 'embedding', name: 'Embedding', tier: 'red', statusWord: 'Offline', metric: 'Backend offline' },
      { key: 'spacy', name: 'spaCy', tier: 'red', statusWord: 'Offline', metric: 'Backend offline' },
    ];
  }

  // Backend — reachable here (backendUp truthy).
  const backend = { key: 'backend', name: 'Backend', tier: 'green', statusWord: 'Running', metric: 'Running' };

  // FOLIO ontology.
  const f = d.folio_ontology || {};
  const folio = { key: 'folio', name: 'FOLIO', tier: 'green', statusWord: '', metric: '', action: 'manage-folio' };
  if (f.status === 'ready') {
    folio.tier = 'green';
    folio.statusWord = 'Ready';
    folio.metric = `${fmt(f.concepts)} concepts, ${fmt(f.labels_indexed)} labels indexed`;
    const us = f.update_status || {};
    if (us.update_in_progress) {
      folio.annotation = 'Updating…';                       // D-06 (green)
    } else if (us.update_available) {
      folio.annotation = 'Update available';                // D-06 (green)
    }
  } else if (f.status === 'not_loaded') {
    folio.tier = 'green';                                   // D-05 (green)
    folio.statusWord = 'Standby';
    folio.metric = 'Standby — loads on first use';
    folio.annotation = 'Standby — loads on first use';
  } else {
    folio.tier = 'red';
    folio.statusWord = 'Error';
    folio.metric = f.message ? `FOLIO error — ${f.message}` : 'FOLIO error';
  }

  // Embedding.
  const e = d.embedding || {};
  const embedding = { key: 'embedding', name: 'Embedding', tier: 'green', statusWord: '', metric: '' };
  if (e.status === 'ready') {
    embedding.tier = 'green';
    embedding.statusWord = 'Ready';
    embedding.metric = `${e.provider || 'Local'}, ${fmt(e.index_size)} vectors indexed`;
  } else if (e.status === 'not_loaded') {
    embedding.tier = 'green';                               // D-05 (green)
    embedding.statusWord = 'Standby';
    embedding.metric = 'Standby — loads on first use';
    embedding.annotation = 'Standby — loads on first use';
  } else {
    embedding.tier = 'red';
    embedding.statusWord = 'Error';
    embedding.metric = e.message ? `Embedding error — ${e.message}` : 'Embedding error';
  }

  // spaCy.
  const s = d.spacy || {};
  const spacy = { key: 'spacy', name: 'spaCy', tier: 'green', statusWord: '', metric: '' };
  if (s.status === 'ready') {
    spacy.tier = 'green';
    spacy.statusWord = 'Ready';
    spacy.metric = `spaCy ${s.version} — EntityRuler ready`;
  } else {
    spacy.tier = 'red';
    spacy.statusWord = 'Error';
    spacy.metric = s.message ? `spaCy error — ${s.message}` : 'spaCy error';
  }

  // Fixed order: Backend, FOLIO, Embedding, spaCy. LLM excluded (STATUS-06).
  return [backend, folio, embedding, spacy];
}
