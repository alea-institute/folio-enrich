# Handoff: Canon law-and-morals overlap — PR #53 open

Written 2026-11-04 by the brainstorm/plan/build session. Receiving session: retire this per the three-condition rule once PR #53 merges and DEV is verified.

## State

- **PR:** https://github.com/alea-institute/folio-enrich/pull/53 from `feat/canon-law-morals-overlap` (one integration commit on main 264fc1c). CI passed; MERGED as 9b77ee9 and deployed to DEV (propositions-dev on hetzner-dev, healthy).
- **Plan:** `docs/plans/2026-11-04-0806-feat-canon-law-morals-overlap-plan.md` — all units built; demos baked with GPT-6.1 Sol via the bake-only Codex CLI provider.
- **Old branch:** `session/1104-0708` holds the original 18-commit history plus two pre-existing commits (an Aug 17 WIP auto-save and an AGENTS.md note) that Damien chose to keep OFF the PR. Leave that branch alone.

## Next steps

1. **Fix live "both" memory before PROD (blocking for live use).** On DEV, a live "both" job pushes propositions-dev (mem_limit 1600m, idles ~470-1000 MB) past its limit; the container is killed and auto-restarts. Measured locally: a both job adds ~900 MB peak, mostly the union EntityRuler duplicating FOLIO's 69,368 patterns. Fix in code: build the union ruler as FOLIO's cached shared ruler plus a Canon-delta ruler (only Canon labels not already identical in FOLIO), merging matches by local identifier; add a peak-RSS regression check. Do NOT raise mem_limit as the fix: the host has ~1.3 GB available.
2. Re-verify on DEV with a live both job inside the container (docker exec python urllib against 127.0.0.1:8000; the public URL is behind Cloudflare Access).
3. Follow-ups: re-bake FOLIO demos against the Oct 30 FOLIO release; three env-version test failures that also fail on pure main.

## Verified on DEV (9b77ee9)

- /ontologies lists the "both" mode; baked overlap and breadth demos serve (e.g. lm_exodus_restitution: 79 tags; canon_diocesan_governance: 161 tags).
- DEV logs show pre-existing missing sentence-transformers/faiss modules (embeddings disabled on DEV); unrelated to this work.
