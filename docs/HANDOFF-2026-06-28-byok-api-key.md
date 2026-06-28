# CE Handoff — Bring-Your-Own-Key / Public Key Drain Fix (2026-06-28)

Session handoff for the next session (incl. Claude running on the Linux box). Everything
below is **committed and pushed to a branch + PR, but NOT yet deployed to PROD** — the
final step (an env var + restart on PROD) is intentionally left for the operator.

## TL;DR
The public PROD site (`https://enrich.openlegalstandard.org`) was using the operator's
**server-stored Gemini API key as a silent fallback for every enrichment request**, so any
anonymous visitor could spend the owner's key. The key string was never *exposed* (endpoints
only return an `api_key_set` boolean), but it was *spendable* by anyone.

Fix: a new opt-in flag **`FOLIO_ENRICH_REQUIRE_USER_API_KEY`** (default `false`). When `true`,
the server key is never used to serve a request — every user must supply their own key
("bring your own key" / BYOK). Default-off preserves the shared-key convenience for
self-hosted/trusted instances; turn it on for the public PROD instance.

- **Branch:** `claude/prod-api-key-prepopulation-itf21w`
- **PR:** #2 → https://github.com/alea-institute/folio-enrich/pull/2 (base `main`)
- **Commits:** `5bb2598` (the fix), `b5114f1` (verify script + docker-compose), plus this handoff.
- **Live:** PROD `https://enrich.openlegalstandard.org` (bare-metal) · DEV `https://folio-enrich-production.up.railway.app` (Railway)

## The bug, precisely
- Request path: `backend/app/api/routes/enrich.py` → `_get_llm_for_request()` →
  `_get_api_key_for_provider()` (in `backend/app/api/routes/settings.py`).
- `_get_api_key_for_provider(provider, explicit_key)` resolved keys as
  **`explicit (request) > settings.<provider>_api_key (server) > None`**. So a request with no
  `api_key` silently fell back to the server's stored key.
- Same helper is also used by per-task LLMs (`backend/app/pipeline/orchestrator.py:280`),
  dynamic model listing, and provider display — so the leak had several entry points, all
  through this one function.
- Validated live (2026-06-28): `/settings` → `"google_api_key_set": true`; `/health/detail`
  → `llm.status: "configured"`, provider `google`, model `gemini-3-flash-preview`. The key
  string is NOT returned anywhere — only the boolean.

## What changed
| File | Change |
|------|--------|
| `backend/app/config.py` | New setting `require_user_api_key: bool = False` |
| `backend/app/api/routes/settings.py` | `_get_api_key_for_provider` returns `None` (no server fallback) when flag on and no explicit key; `/settings` now returns `require_user_api_key` and reports `*_api_key_set` as `false` in BYOK mode |
| `backend/app/api/routes/health.py` | `_check_llm` reports `no_api_key` in BYOK mode so the UI chip shows "Not Configured" |
| `backend/tests/test_require_user_api_key.py` | 7 tests: key resolution, health status, `/settings` + `/settings/providers` endpoints |
| `backend/.env.example`, `backend/docker-compose.yml`, `README.md` | Document the flag |
| `scripts/verify-byok.sh` | One-command check that a deployment isn't serving requests with a server key |

Single-helper gating means `test-connection` and model-listing still work (they pass an
explicit key); only the silent fallback is disabled.

## Testing (run on the Linux box)
Full backend suite was run this session: **744 passed**. The only red (5 failed + 5 errored)
is **pre-existing on `main`** and environmental — `test_embedding_index` / `test_semantic_ruler`
/ one `test_disambiguation_eval` need the optional `sentence-transformers` extra (intentionally
omitted per the Dockerfile), and `test_demo_freshness` needs network. None reference the
changed code. Confirmed identical failures on `main`.

```bash
git fetch origin
git checkout claude/prod-api-key-prepopulation-itf21w
cd backend
python -m pytest tests/test_require_user_api_key.py -q     # 7 passed (no heavy deps)
python -m pytest -q                                         # full suite
```

### Sandbox gotcha (may not apply on your box)
In this cloud sandbox, `pip install -e ".[dev]"` failed because the transitive dep
`red-black-tree-mod` won't build under modern setuptools (`AttributeError: install_layout`).
Workaround that got the full suite green: a venv with `setuptools<60`:
```bash
python -m venv /tmp/byok-venv && /tmp/byok-venv/bin/pip install "setuptools<60" wheel
/tmp/byok-venv/bin/pip install -e ".[dev]"
/tmp/byok-venv/bin/python -m spacy download en_core_web_sm
/tmp/byok-venv/bin/python -m pytest -q
```
Your existing PROD/DEV venv already has these deps, so this is only relevant for a fresh env.

## Deploying to PROD (operator action — not done yet)
> Merging the code does NOT fix PROD by itself. The live key lives in the PROD environment,
> not the repo. You must also set the env var and restart.

**PROD is bare-metal with a uv-managed venv — there is NO `pip`.** (Per the prior demo-exemplars
handoff.) To update Python deps if ever needed:
`cd backend && ~/.local/bin/uv pip install --python .venv/bin/python <pkg>`. This change adds
**no new dependencies**, so no install is required — only a code pull + env var + restart.

1. Merge PR #2 into `main`.
2. On the PROD host: `git pull`.
3. Set the env var in PROD's environment / service config:
   `FOLIO_ENRICH_REQUIRE_USER_API_KEY=true`
   - You may KEEP `FOLIO_ENRICH_GOOGLE_API_KEY` (still usable for your own test-connection;
     just no longer auto-spent by the public), OR remove it for a blunter belt-and-suspenders fix.
4. Restart / redeploy the service. **(Open question: exact restart mechanism for bare-metal PROD —
   systemd unit? supervisor? — confirm how the uvicorn process is managed and restart it.)**
5. Verify:
   ```bash
   scripts/verify-byok.sh https://enrich.openlegalstandard.org
   ```
   Expect **PASS** and the LLM chip showing **"Not Configured"**. (Before the change it correctly
   reports FAIL: "server key may be spent by anonymous users.")

DEV (Railway) is identical in behavior — set the same env var there if you want DEV protected too.

## Hardening folded into PR #2 (2026-06-28, second pass)

A follow-up code review (`docs/plans/2026-06-28-001-fix-byok-harden-public-key-drain-plan.md`)
found three gaps in the first pass and they were fixed **on this same branch / PR**:

1. **Key storage is now blocked server-side in BYOK mode.** `PUT /settings` previously still
   wrote a visitor's key into the shared `settings` singleton (the frontend `PUT`s it on every
   enrich). BYOK ignored it for *serving*, but the secret still landed in shared memory.
   `update_settings` now skips all `*_api_key` writes when `require_user_api_key` is on
   (non-key fields still update). **"The server never holds a servable key" is now literally
   true.**
2. **Key persistence moved server-global → per-browser `localStorage`.** The frontend no longer
   `PUT`s the key in BYOK mode; it stores the key in the visitor's own browser
   (`folio_enrich_api_key_<provider>`) and sends it per-request only. The owner keeps
   cross-session convenience on their own machine; nothing shared is stored.
3. **`/synthetic` parity.** `SyntheticRequest` now accepts `api_key`, resolves it via the same
   choke point, and returns a clean **400** ("Add your API key...") instead of an unhandled 500
   when no key is available in BYOK mode.
4. **Explicit UX.** The setup banner now reads **"Add your API key"** (title + button + body
   explaining the key stays in the browser) when BYOK is on, instead of the generic
   "No AI provider configured".

Tests: 4 new cases in `backend/tests/test_require_user_api_key.py` (no-op key persistence in
BYOK, key persistence when off, synthetic 400, synthetic honors explicit key). Full backend
suite: **720 passed**, 38 heavy-dep tests deselected, 0 failures. No new dependencies.

**Rollout decision (resolved):** enable BYOK on **PROD and DEV**, and **keep** the Gemini env
key (used only for the owner's own server-side Test Connection; the public can't spend it, and
client-side `localStorage` now covers the owner's cross-session convenience).

## Decisions still open
- **Default posture:** kept the flag default-`false` so self-hosters aren't broken. If a future
  build wants public-safe-by-default, flip the default and let trusted instances opt out.
- **Bare-metal PROD restart mechanism** (systemd? supervisor?) — still needs confirming before
  the operator sets the env var and restarts.

## Notes / caveats
- No per-user auth exists, so BYOK mode means **nobody** (including the owner) gets the server
  key auto-applied — everyone pastes their own key per session. That's the intended trade-off
  for a public site; it cannot distinguish "owner" from "public" without real login.
- `verify-byok.sh` uses only `curl` + `python3` (no `jq`); exit 0 = enforced, 1 = not enforced
  or unreachable. Safe to run against local or PROD.
- Frontend consumes `api_key_set` from `/settings/providers` (settings modal placeholder) and
  `llm.status` from `/health/detail` (header chip) — both now reflect BYOK mode automatically.
