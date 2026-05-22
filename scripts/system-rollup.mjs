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

// Placeholder so the test module's named import resolves; the real
// implementation (D-05/D-06 mapping) is driven by Task 3's TDD cycle.
export function normalizeSubsystems(_detail, _backendUp) {
  throw new Error('normalizeSubsystems not yet implemented');
}
