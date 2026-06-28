# 🔴 PENDING PROD DEPLOY — Enable BYOK to stop public key drain (2026-06-28)

**Status: code merged, DEV done, PROD NOT done — blocked on SSH access (Mike on vacation).**
When SSH to PROD is available again, this is a **one-command** fix. Read the TL;DR, run the
command, done.

---

## TL;DR (the whole thing in one command)

Once your machine can reach PROD on port 22 (see **Prerequisite** below), run **either**:

**A) From an allowlisted machine, over SSH (no manual login needed):**
```bash
ssh -J hetzner-dev -i "/home/damienriehl/Coding Projects/folio-ontokit.pem" ubuntu@54.224.195.12 \
  'cd /home/ubuntu/folio-enrich && git pull origin main && bash scripts/deploy-byok-prod.sh'
```
(Drop `-J hetzner-dev` if your own IP is the one that's allowlisted.)

**B) Already logged into the PROD host as `ubuntu`:**
```bash
cd /home/ubuntu/folio-enrich && git pull origin main && bash scripts/deploy-byok-prod.sh
```

The script (`scripts/deploy-byok-prod.sh`, now committed to `main`) is **idempotent**: it pulls
`main`, backs up `backend/.env`, sets `FOLIO_ENRICH_REQUIRE_USER_API_KEY=true`, restarts the
service, waits for health, and verifies. Expected final output: **PASS** and
`synthetic (no key) => HTTP 400`.

---

## Why this is needed (the bug)

PROD (`https://enrich.openlegalstandard.org`) serves enrichment using a **server-stored Gemini
key** (`FOLIO_ENRICH_GOOGLE_API_KEY` in `backend/.env`) as a silent fallback for every request.
Any anonymous visitor spends the operator's key. The key string is never *exposed* (endpoints
return only a boolean), but it is *spendable* by anyone.

**Verified live on 2026-06-28** (PROD, still vulnerable as of this writing):
- `GET /settings` → `google_api_key_set: true`, and **no** `require_user_api_key` field (= old code)
- `GET /health/detail` → `llm.status: "configured"`, provider `google`, `gemini-3-flash-preview`
- `POST /synthetic` with no key → **HTTP 200** (it generates, spending the server key)

> ⚠️ This disproves an older note that claimed "PROD stores no server-side key." It does. That's
> the whole reason for this work.

## The fix (already coded + merged)

PR **#2** (merged to `main` 2026-06-28, commit `7bb1219`) adds an opt-in flag
**`FOLIO_ENRICH_REQUIRE_USER_API_KEY`** (default `false`). When `true`:
- the server key is **never** used to serve a request (no silent fallback);
- `PUT /settings` **won't even store** an API key (defense in depth);
- every visitor supplies their own key, which the **browser keeps in `localStorage`** and sends
  per-request only — the server never holds a servable key;
- `/synthetic` returns a clean **400** ("Add your API key…") instead of a 500 when no key;
- the UI shows an **"Add your API key"** banner.

Merging the code does **not** fix PROD by itself — the live key is in PROD's environment, not the
repo. You must set the flag and restart. That's what the script does.

---

## Prerequisite: SSH access (the current blocker)

As of 2026-06-28, PROD **port 22 is silently dropped** (AWS security group) from every source IP
available to us:
- home IP `97.116.181.129` — blocked (this is the exact IP a 2026-06-17 request asked Mike to
  allowlist; that request was evidently never applied)
- Hetzner static jump IP `204.168.246.227` — also blocked
- no Tailscale route to PROD

**Ask Mike (when back from vacation) to allowlist, on the AWS security group for the PROD
instance (`54.224.195.12`), inbound TCP 22 from:**
- `97.116.181.129/32` (Damien home — note: dynamic, may have rotated; re-check current IP with
  `curl -s https://api.ipify.org`)
- `204.168.246.227/32` (Hetzner `hetzner-dev`, **static** — preferred durable anchor; use the
  `-J hetzner-dev` ProxyJump form so egress is always this IP regardless of home-IP churn)

Confirm reachability before deploying:
```bash
ssh -J hetzner-dev -i "/home/damienriehl/Coding Projects/folio-ontokit.pem" \
  -o ConnectTimeout=10 ubuntu@54.224.195.12 'echo OK; hostname'
```

---

## Interim mitigation (if you want to stop the bleed BEFORE the full deploy)

Stopping the drain does not even require the new code — just remove the key and restart. Still
needs SSH, but it's the minimal change:
```bash
ssh -J hetzner-dev -i "/home/damienriehl/Coding Projects/folio-ontokit.pem" ubuntu@54.224.195.12 \
  'cd /home/ubuntu/folio-enrich && cp backend/.env backend/.env.bak-$(date +%F) \
   && sed -i "s|^FOLIO_ENRICH_GOOGLE_API_KEY=|#FOLIO_ENRICH_GOOGLE_API_KEY=|" backend/.env \
   && sudo -n systemctl restart folio-enrich'
```
The proper deploy (the script above) is better — it keeps the key usable for *your own* in-app
"Test Connection" while blocking public spend.

---

## Manual step-by-step (if you'd rather not use the script)

```bash
# 1. On the PROD host:
cd /home/ubuntu/folio-enrich
git pull origin main

# 2. Back up and edit the (git-ignored, manual) env file:
cp backend/.env backend/.env.bak-$(date +%F)
echo 'FOLIO_ENRICH_REQUIRE_USER_API_KEY=true' >> backend/.env   # (skip if the line already exists)

# 3. Restart (passwordless sudo is configured; brief outage while the embedding cache loads):
sudo -n systemctl restart folio-enrich

# 4. Verify:
scripts/verify-byok.sh https://enrich.openlegalstandard.org   # expect: PASS
curl -s https://enrich.openlegalstandard.org/settings | grep -o '"require_user_api_key": *true'
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  https://enrich.openlegalstandard.org/synthetic \
  -H 'Content-Type: application/json' -d '{"doc_type":"NDA"}'   # expect: 400
```

## What success looks like
- `verify-byok.sh` prints **PASS**
- Header LLM chip shows **"Not Configured"**; first-time visitors see the **"Add your API key"** banner
- `/synthetic` with no key → **400** (was 200)
- `/settings` → `require_user_api_key: true`, `google_api_key_set: false`
- Gemini spend from anonymous traffic **stops** (watch the provider dashboard first 24h)

## Rollback
Restore the latest backup and restart — reverts to prior shared-key behavior:
```bash
cd /home/ubuntu/folio-enrich && cp backend/.env.bak-<DATE> backend/.env && sudo -n systemctl restart folio-enrich
```

---

## DEV (Railway) — already done, low priority
- Railway `folio-enrich` tracks `main`, so it **auto-deployed the new code** on merge. Verified
  live: `/settings` has `require_user_api_key`, `/synthetic` no-key → **400**.
- DEV has **no** server key (`google_api_key_set: false`) so it was never vulnerable. Setting the
  flag there is cosmetic.
- If you do want it set: the Railway CLI here is unauthorized (`railway login` is interactive), so
  set `FOLIO_ENRICH_REQUIRE_USER_API_KEY=true` in the **Railway dashboard** → folio-enrich service
  → Variables (triggers a redeploy). Service id `96ebb3a0-532f-4be8-9d8e-2a4240c22aeb`,
  project `alea-tools`, env `production`.

---

## Server facts you'll need (from prior handoffs)
- **SSH:** `ssh -J hetzner-dev -i "/home/damienriehl/Coding Projects/folio-ontokit.pem" ubuntu@54.224.195.12`
  (host `54.224.195.12`, Ubuntu 24.04 ARM64, bare-metal + systemd, **no Docker, no pip** — uv-managed venv)
- **App dir:** `/home/ubuntu/folio-enrich` (backend at `backend/`, env at `backend/.env`, venv `backend/.venv/`)
- **Service / restart:** `folio-enrich.service` → `sudo -n systemctl restart folio-enrich` (passwordless)
- **No new deps** in this change, so **no** `uv pip install` step is required.
- **Restart cost:** startup blocks on the FOLIO embedding index; the cache at
  `~/.folio-enrich/cache/embeddings/` (OWL hash `9a9d3cb5d2823f2a` as of 2026-05-25) makes it fast.
  If the OWL changed, the first restart can take ~5 min (the script waits up to ~5 min for health).
- **Logs if anything's off:** `sudo journalctl -u folio-enrich -n 100 --no-pager`

## References
- Deploy script: `scripts/deploy-byok-prod.sh`
- BYOK verifier: `scripts/verify-byok.sh`
- Plan + code review: `docs/plans/2026-06-28-001-fix-byok-harden-public-key-drain-plan.md`
- Original BYOK handoff: `docs/HANDOFF-2026-06-28-byok-api-key.md`
- PR: https://github.com/alea-institute/folio-enrich/pull/2 (merged)
- IP allowlist background: `dev-twin/docs/HANDOFF-2026-06-17-alea-prod-ip-allowlist.md`
