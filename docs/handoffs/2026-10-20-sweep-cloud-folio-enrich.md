# Sweep handoff: folio-enrich (cloud lane, cycle sweep-2026-10-20)

Date: 2026-10-20. Lane: cloud orchestrator.

## Outcome

| Item | State | Evidence |
|---|---|---|
| `codex/proposition-review-workspace-final` | Already merged before this sweep (ancestor of main, 0 commits ahead) | `git merge-base --is-ancestor` |
| Insights bridge, first unit (shared content IRIs, propositions export/ingest, insights panel) | Already merged as PR #44 (2026-10-09) | `d424876` on main |
| PR #45 backend CI workflow | **Merged** (squash `fe7f462`) after rework | Actions `backend-tests` green; 1226/1226 locally |
| PR #46 Word ingestor `w:sdt` content controls | **Merged** (squash `8ce29a7`) after review fix | Actions green; 1230/1230 locally |

### PR #45 rework
- Withdrew the skip/xfail markers on `test_demos_are_fresh`, `test_regenerate_if_stale`,
  `test_agreement_collision_discovered`. The default `addopts` already deselects them
  (`slow`/`demo_regen`), so they never ran in CI; quarantining them was unnecessary.
- Fixed the real CI failure: `test_expired_jwks_fetch_failure_does_not_use_stale_keys`
  expired the JWKS cache by setting its timestamp to 0, which reads as fresh on any host
  whose monotonic clock sits below the 600 s TTL (fresh CI runners). Test-only change;
  production code unaffected.

### PR #46 review
- Found and fixed a regression: Word stores each text box in `mc:Choice` and again in
  `mc:Fallback`; walking every `w:p` emitted text-box text twice. Now skips `mc:Fallback`.
  Regression test added. Removed lint findings the PR introduced.

## Stale branches (no deletion performed: deletion needs Damien's go-ahead)

Fully merged (ancestor of main), safe to delete with no backup needed:
`build/folio-resolve-0.4.0`, `codex/proposition-review-workspace-final`,
`feat/cf-access-annotation`, `feat/folio-matching-migration`, `feat/gold-human-validation`,
`feat/proposition-cycle-2`, `feat/proposition-system-phase-a`, `feat/u10-synthetic-runner`,
`ci/drain-backend-tests` (merged as #45), `fix/word-ingestor-sdt-v2` (merged as #46).

Content already on main under different SHAs (squash or cherry-pick; `git cherry` shows
every commit as equivalent, or the PR merged by squash):
`feat/drain-insights-bridge` (squashed as #44), `docs/u12-palsgraf-cycle1-reconciliation`,
`fix/u10-deterministic-runner-config`, `fix/word-ingestor-sdt-content-controls`
(superseded by #46).

Pre-history-rewrite lineage (no common ancestor with main; main carries the Canon and
multi-ontology work as PRs #20 through #31): `dev`, `feat/canon-demos`, `feat/demo-slim`,
`feat/folio-ontology-update-modal`, `feat/multi-ontology-enable-canon`,
`feat/multi-ontology-frontend-switcher`, `feat/multi-ontology-security`,
`fix/canon-concept-detail-hierarchy`, `fix/folio-python-search-extra`,
`fix/search-preflabel-matching`, `polish/canon-plan-completion`.

## Open questions for Damien

1. **Palsgraf gold human review (legal judgment; filed, not done).** The 2026-09-30
   reconciliation (`docs/plans/2026-09-30-palsgraf-cycle-1-reconciliation.md`) records
   104 AI-annotated gold propositions and states that no human validation exists; the
   gold README's "human-reviewed" label does not hold for Palsgraf. Damien must review
   the propositions in the annotation workspace (gold validation, PR #42) and record a
   validation receipt.
   Recommendation: do it in one sitting through the Cloudflare Access annotation UI once deployed.
   Setting: browser-with-logins.
2. **Delete stale remote branches?** Recommendation: delete the 14 merged/equivalent
   branches now. For the 11 pre-rewrite branches, keep or tag them first (e.g.
   `archive/<name>`), then delete. Setting: quick-decision.
3. **Demo rebake.** `test_demos_are_fresh` (opt-in `demo_regen`) fails on main: baked
   demos target an older FOLIO OWL. Rebaking may call a paid LLM provider, so it counts as spend.
   Recommendation: run `scripts/generate_demos.py` in an authorized regeneration run.
   Setting: quick-decision.

## Box-only steps
- Deploy main (CF Access annotation, bridge, CI) to the hosting environment; the cloud
  lane holds no deploy credentials.
- Configure the folio-insights endpoint and CF Access settings in the deployed environment.
