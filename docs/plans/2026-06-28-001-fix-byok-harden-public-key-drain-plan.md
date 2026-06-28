---
title: Harden BYOK Mode — Stop Public Key Drain (consistency + client-side persistence)
type: fix
status: completed
date: 2026-06-28
branch: claude/prod-api-key-prepopulation-itf21w
pr: 2
---

# 🐛 Harden BYOK Mode — Stop Public Key Drain

## Overview

The public PROD site (`https://enrich.openlegalstandard.org`) was silently using the
operator's server-stored Gemini key as a fallback for **every anonymous enrichment
request**, letting any visitor spend the owner's key. The existing branch
`claude/prod-api-key-prepopulation-itf21w` (PR #2) introduces an opt-in flag
`FOLIO_ENRICH_REQUIRE_USER_API_KEY` ("bring your own key" / BYOK) that, when `true`,
never uses a server-stored key to serve a request. **That fix is correct and is the right
primary approach.** This plan does not replace it — it *folds three hardening changes into
the same PR* to close the gaps found in code review and make BYOK airtight, consistent,
and convenient for the owner.

The animating insight from review: **today the only place an API key is persisted is the
shared server-global settings singleton** — that shared storage *is* the drain bug. The
fix is to move persistence from *server-global* → *per-browser `localStorage`*, so the
owner keeps cross-session convenience on their own machine while the public can never
spend a shared key.

## Problem Statement

### The original bug (fixed by the branch)
- Key resolution in `backend/app/api/routes/settings.py::_get_api_key_for_provider`
  resolved keys as `explicit (request) > settings.<provider>_api_key (server) > None`.
  A request with no `api_key` silently fell back to the server's stored key.
- This single helper feeds every request-serving path: `enrich.py:55`,
  `orchestrator.py:280` (per-task LLMs), `synthetic.py:38`, plus model-listing,
  test-connection, and provider display. One leak, several entry points.

### Gaps remaining after the branch (what this plan fixes)

1. **`PUT /settings` still persists visitor keys into the shared global singleton — even
   in BYOK mode.** BYOK stops the stored key from being *used*, but the frontend still
   `PUT`s the user's key on every enrich (`frontend/index.html:5853-5863`), so a visitor's
   secret still lands in shared server memory. The design intent "the server never holds a
   servable key" is only half-true. (Not directly exfiltrable — only booleans are returned
   — but it is the wrong place to store a per-user secret, and it is the mechanism the
   original bug exploited.)
   - **Sub-finding:** the frontend has **no client-side persistence** for the key
     (`localStorage` is used for theme/layers/debug, never for `apiKeyInput`). So the
     *only* way a key currently survives is the shared server write — which is exactly
     what must stop.

2. **`/synthetic` parity gap.** `SyntheticRequest` has **no `api_key` field**, and the
   route lacks the graceful `REQUIRES_API_KEY and not api_key → return None` guard that
   `enrich.py` and `orchestrator._make_llm` both have. In BYOK mode it passes
   `api_key=None` into `get_provider`, the Google provider sends `x-goog-api-key: ""`, and
   the (un-guarded) `.generate()` call raises → an unhandled **500**, instead of accepting
   a user key or returning a clean 4xx. **Not a leak** (verified: providers never read
   ambient `GOOGLE_API_KEY`/`GEMINI_API_KEY` from the environment), but a broken,
   inconsistent endpoint.

3. **Implicit BYOK UX.** The header chip shows "Not Configured" in BYOK mode, but there is
   no explicit empty-state telling a first-time visitor *what to do*. Users need a clear
   "**Add your API key**" prompt.

## Proposed Solution

Keep the branch's BYOK fix. Add three hardening changes **on the same branch / PR #2**:

| # | Change | Layer |
|---|--------|-------|
| H1 | **Block server-side key storage in BYOK mode** + move owner key persistence to browser `localStorage` (per-request only; server never stores it) | backend + frontend |
| H2 | **Fix `/synthetic` parity** — accept `api_key` on `SyntheticRequest`, add the graceful guard, return a clean 4xx (not 500) when no key in BYOK | backend |
| H3 | **Explicit BYOK UX** — first-run empty-state / banner reading **"Add your API key"** that guides the visitor to paste a key | frontend |
| H4 | **Tests** for the new behavior | backend |

### Verified facts the design relies on (from code review)
- ✅ All request-serving key resolution flows through `_get_api_key_for_provider` (single
  choke point). Confirmed by grep — the only direct `settings.*_api_key` reads left are the
  boolean reporters in `/settings`, which the branch masks with `_key_set`.
- ✅ Providers build clients from the **explicit key only** — e.g.
  `google_provider.py:52` `"x-goog-api-key": self.api_key or ""`. **No ambient env-var
  fallback.** So `api_key=None` cannot quietly pick up a server env key.
- ✅ `enrich` and `orchestrator._make_llm` already degrade gracefully (skip LLM stages) in
  BYOK mode. The frontend already sends `api_key` per-request (`index.html:5874`).

## Technical Approach

### H1 — Block server-side key storage in BYOK; persist client-side instead

**Backend (`backend/app/api/routes/settings.py::update_settings`):**
- When `settings.require_user_api_key` is `True`, **skip** writing any of the
  `*_api_key` fields in the `update_settings` loop (the `for fld in (...)` block).
  Non-key settings (provider, model, task overrides, etc.) still update normally.
- Rationale: defense in depth — the server refuses to *store* a servable key, not just
  refuses to *use* it. Makes "server never holds a servable key" actually true and stops
  trusting the frontend to do the right thing.
- Note: `require_user_api_key` itself is **env-only** (not in the `SettingsUpdate`
  whitelist), so a public user cannot toggle BYOK off at runtime. ✓ (already true — keep it
  that way.)

```python
# settings.py::update_settings — gate the key-write loop
_KEY_FIELDS = (
    "openai_api_key", "anthropic_api_key", "google_api_key", "mistral_api_key",
    "cohere_api_key", "meta_llama_api_key", "groq_api_key", "xai_api_key",
    "github_models_api_key",
)
if not settings.require_user_api_key:      # BYOK: never persist a server-side key
    for fld in _KEY_FIELDS:
        val = getattr(update, fld, None)
        if val is not None:
            setattr(settings, fld, val)
```

**Frontend (`frontend/index.html`):**
- Persist the inline `apiKeyInput` value in **`localStorage`** (key e.g.
  `folio_enrich_api_key_<provider>`), client-side only. Restore it into the field on load
  and on provider change. This replaces the server-side persistence the app relied on.
- In the enrich submit flow (`~index.html:5853-5863`): **stop `PUT`ing the key to
  `/settings`** (either always, or at minimum when `require_user_api_key` is true — the
  `/settings` GET already exposes `require_user_api_key`). Continue sending the key
  **per-request** as `body.api_key` (already done at `index.html:5874`). Non-key settings
  (provider/model) may still be `PUT` as today.
- Net effect for the owner: paste once → key sticks in *your* browser across sessions; the
  server never holds it.

### H2 — `/synthetic` parity

**`backend/app/api/routes/synthetic.py`:**
- Add `api_key: str | None = None` to `SyntheticRequest`.
- Resolve via `_get_api_key_for_provider(provider_type, req.api_key)` (pass the explicit
  key, mirroring `enrich.py:55`).
- Add the graceful guard before constructing the provider:
  ```python
  if REQUIRES_API_KEY.get(provider_type, True) and not api_key:
      raise HTTPException(
          status_code=400,
          detail="An API key is required. Add your API key to generate documents.",
      )
  ```
- Move the `.generate()` call's failure into a clean error path (it currently sits outside
  the construction `try`, so provider/runtime errors 500). Wrap appropriately so an auth
  failure returns a clear 4xx/502, not an unhandled 500.

**Frontend:** include the user's key in the synthetic-generation request body (same
`apiKey` value used for enrich).

### H3 — Explicit "Add your API key" UX

**`frontend/index.html`:**
- When `/settings` reports `require_user_api_key: true` (and no key in `localStorage`),
  show a clear, dismissible empty-state / banner near the enrich action and the LLM chip:
  headline **"Add your API key"** with a short line ("This site uses your own LLM key —
  paste it to enable AI extraction. It stays in your browser.") and focus/scroll to the
  `apiKeyInput`.
- Keep the existing "Not Configured" chip behavior (already wired via `l.status ===
  'no_api_key'` at `index.html:4773`); the banner is the actionable companion to it.
- Apply UX best practices: accessible (labelled input, aria-live on the banner), clear
  feedback, progressive disclosure, no dark patterns. Exact required copy: **"Add your API
  key"** (per owner).

### H4 — Tests (`backend/tests/`)
Extend `test_require_user_api_key.py` (or a sibling):
- `update_settings` is a **no-op for key fields** when BYOK is on (stored key unchanged),
  but still updates provider/model.
- `update_settings` **does** persist keys when BYOK is off (regression guard).
- `/synthetic` returns **400** (not 500) when BYOK is on and no `api_key` is supplied.
- `/synthetic` **honors an explicit `api_key`** when BYOK is on (provider constructed).
- (Already covered by branch: key resolution, health status, `/settings` + `/providers`
  masking.)

## System-Wide Impact

- **Interaction graph:** `enrich`/`synthetic`/`orchestrator` → `_get_api_key_for_provider`
  → `get_provider` → provider client (explicit key only). `update_settings` mutates the
  global `settings` singleton; H1 removes key mutation in BYOK. Frontend `localStorage`
  becomes the persistence layer for the owner's key.
- **Error propagation:** H2 converts an unhandled 500 (provider auth failure on empty key)
  into a deliberate 400 with actionable copy. Confirm the frontend surfaces `detail` (it
  already does for enrich at `index.html:~5882`).
- **State lifecycle:** H1 removes a place where a per-user secret was written to
  process-global memory. No DB/disk involved — keys never persisted server-side in BYOK.
- **API surface parity:** the three serving paths (enrich, synthetic, per-task) now all
  honor an explicit key + degrade/refuse cleanly without a server fallback. `/settings`
  GET masking and `/providers` already reflect BYOK.
- **Integration scenarios:** (1) BYOK on, no key → enrich runs rule-based, synthetic 400s,
  banner shows. (2) BYOK on, user key pasted → full pipeline + synthetic work, key
  persists in browser only, never `PUT` to server. (3) BYOK on, attacker `PUT`s a key →
  ignored server-side. (4) BYOK off (self-host) → unchanged legacy behavior.

## Acceptance Criteria

- [x] **H1a:** With `require_user_api_key=true`, `PUT /settings` with an `*_api_key` field
      does **not** change the stored key; provider/model still update.
- [x] **H1b:** Frontend no longer `PUT`s the API key to `/settings` in BYOK mode; the key
      persists in `localStorage` and is restored on reload. *(verified round-trip in Chrome.)*
- [x] **H1c:** The key is still sent per-request as `body.api_key` and enrichment works
      end-to-end with a user-supplied key in BYOK mode.
- [x] **H2a:** `SyntheticRequest` accepts `api_key`; `/synthetic` succeeds in BYOK mode
      with an explicit key.
- [x] **H2b:** `/synthetic` returns **400** (clear message), not 500, when BYOK is on and
      no key is supplied. *(verified live: curl → 400.)*
- [x] **H3:** In BYOK mode with no key, the UI shows an actionable **"Add your API key"**
      empty-state/banner that focuses the key input; accessible (aria-live, labelled).
      *(verified in Chrome — banner + chip render correctly.)*
- [x] **H4:** New tests pass; full backend suite has no *new* failures (720 passed,
      38 deselected heavy-dep tests).
- [x] **Docs:** Update `docs/HANDOFF-2026-06-28-byok-api-key.md` (and README if needed) to
      note client-side persistence + synthetic behavior + that key storage is blocked
      server-side in BYOK.
- [x] **No new dependencies.**

## Rollout (operator actions — owner decision recorded)

Decision: **enable BYOK on PROD *and* DEV, keep the existing Gemini env key.**
Rationale: the env key is only used for the owner's own server-side Test Connection; BYOK
prevents public spend; client-side `localStorage` gives the owner cross-session
persistence. Removing the env key (Option 2) would yield identical *enrichment* UX once
H1's localStorage persistence lands — it would only cost the owner the server-side
Test-Connection convenience. So: keep it.

1. Merge the hardened PR #2 into `main`.
2. PROD (bare-metal): `git pull`; set `FOLIO_ENRICH_REQUIRE_USER_API_KEY=true`; restart the
   uvicorn service. **Open item: confirm the restart mechanism (systemd unit? supervisor?)
   for bare-metal PROD** — see `reference_prod_server.md`.
3. DEV (Railway): set the same env var (`enrich` auto-deploys from `main`).
4. Keep `FOLIO_ENRICH_GOOGLE_API_KEY` on both (owner Test Connection only).
5. Verify: `scripts/verify-byok.sh https://enrich.openlegalstandard.org` → **PASS**, LLM
   chip "Not Configured", and a fresh visitor sees "Add your API key". Repeat for DEV.

## Sequencing

**Fold all hardening commits onto the existing branch `claude/prod-api-key-prepopulation-itf21w`
/ PR #2** (owner decision). Review once, merge once, single deploy. Suggested atomic
commits: (a) H1 backend gate, (b) H1 frontend localStorage + stop PUT, (c) H2 synthetic,
(d) H3 UX banner, (e) H4 tests + docs.

## Alternatives Considered

- **Per-IP rate-limit the server key** — still spends the owner's money and needs a
  limiter/store; doesn't stop drain. ❌
- **Real auth + per-user quotas** — heavyweight; no auth exists today; out of scope. ❌
- **Just delete the PROD key** — blunt; breaks owner Test Connection; no code path
  hardening. Folded in as the *optional* belt-and-suspenders (not chosen). ❌
- **BYOK + harden + client-side persistence (this plan)** — simplest correct fix for the
  stated threat, made airtight and consistent, with no owner-convenience regression. ✅

## Sources & References

- **Branch / PR:** `claude/prod-api-key-prepopulation-itf21w` → PR #2
  (https://github.com/alea-institute/folio-enrich/pull/2), base `main`.
- **Origin handoff:** `docs/HANDOFF-2026-06-28-byok-api-key.md` (the branch's own handoff —
  carries the bug analysis, choke-point map, and open decisions this plan resolves).
- **Choke point:** `backend/app/api/routes/settings.py::_get_api_key_for_provider`
- **Serving paths:** `backend/app/api/routes/enrich.py:55`,
  `backend/app/pipeline/orchestrator.py:280`, `backend/app/api/routes/synthetic.py:38`,
  `backend/app/api/routes/settings.py:216/240/267`
- **No-ambient-env proof:** `backend/app/services/llm/google_provider.py:52`,
  `openai_compat.py:32`, `cohere_provider.py:30`, `github_models_provider.py:25`
- **Frontend key flow:** `frontend/index.html:5844-5874` (submit), `:4773` (chip),
  `:5853-5863` (the `PUT /settings` to remove in BYOK)
- **Verify script:** `scripts/verify-byok.sh`
- **PROD/DEV deploy:** `reference_prod_server.md`, `reference_railway_dev.md` (memory) —
  `enrich` auto-deploys from `main`.
