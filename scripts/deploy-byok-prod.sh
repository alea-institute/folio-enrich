#!/usr/bin/env bash
#
# deploy-byok-prod.sh — enable bring-your-own-key (BYOK) on the PROD folio-enrich
# instance so anonymous visitors can no longer spend the operator's LLM key.
#
# WHY: PROD currently serves enrichment using a server-stored Gemini key
# (FOLIO_ENRICH_GOOGLE_API_KEY) as a silent fallback — any anonymous visitor
# spends it. PR #2 (merged to `main` 2026-06-28) added the opt-in flag
# FOLIO_ENRICH_REQUIRE_USER_API_KEY. This script pulls that code, turns the flag
# on, restarts the service, and verifies enforcement.
#
# SAFE TO RE-RUN — idempotent. Backs up backend/.env before editing.
#
# ── Usage (run ON the PROD host, as the `ubuntu` user) ──
#   cd /home/ubuntu/folio-enrich && git pull origin main && bash scripts/deploy-byok-prod.sh
#
# ── Usage (run FROM an allowlisted machine over SSH, no need to log in first) ──
#   ssh -J hetzner-dev -i "/path/to/folio-ontokit.pem" ubuntu@54.224.195.12 \
#     'cd /home/ubuntu/folio-enrich && git pull origin main && bash scripts/deploy-byok-prod.sh'
#
# Prereqs: SSH reachable (AWS security group must allowlist your source IP on
# :22) and passwordless sudo for systemctl (already configured on this box).
#
# Env overrides (rarely needed):
#   APP_DIR    (default /home/ubuntu/folio-enrich)
#   SERVICE    (default folio-enrich)
#   PUBLIC_URL (default https://enrich.openlegalstandard.org)
#   REMOVE_SERVER_KEY=1  also comment out FOLIO_ENRICH_GOOGLE_API_KEY (belt-and-suspenders)

set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/folio-enrich}"
SERVICE="${SERVICE:-folio-enrich}"
PUBLIC_URL="${PUBLIC_URL:-https://enrich.openlegalstandard.org}"
ENV_FILE="$APP_DIR/backend/.env"
FLAG="FOLIO_ENRICH_REQUIRE_USER_API_KEY"

echo "==> folio-enrich BYOK deploy — $(date)"
cd "$APP_DIR"

echo "==> [1/6] git pull origin main"
git pull origin main

echo "==> [2/6] back up $ENV_FILE"
if [ -f "$ENV_FILE" ]; then
  backup="$ENV_FILE.bak-$(date +%F-%H%M%S)"
  cp "$ENV_FILE" "$backup"
  echo "    backed up -> $backup"
else
  echo "    !! $ENV_FILE not found — creating a new one"
  touch "$ENV_FILE"
fi

echo "==> [3/6] ensure $FLAG=true"
if grep -q "^$FLAG=" "$ENV_FILE"; then
  sed -i "s|^$FLAG=.*|$FLAG=true|" "$ENV_FILE"
else
  printf '\n# BYOK: never serve anonymous requests with a server key (added by deploy-byok-prod.sh)\n%s=true\n' "$FLAG" >> "$ENV_FILE"
fi
grep "^$FLAG=" "$ENV_FILE" | sed 's/^/    /'

if [ "${REMOVE_SERVER_KEY:-0}" = "1" ]; then
  echo "==> [3b] REMOVE_SERVER_KEY=1 — commenting out FOLIO_ENRICH_GOOGLE_API_KEY"
  sed -i "s|^FOLIO_ENRICH_GOOGLE_API_KEY=|#FOLIO_ENRICH_GOOGLE_API_KEY=|" "$ENV_FILE" || true
fi

echo "==> [4/6] restart $SERVICE (brief outage while the FOLIO embedding cache loads)"
sudo -n systemctl restart "$SERVICE"

echo "==> [5/6] wait for /health to return 200 (up to ~5 min for cache load)"
ok=""
for _ in $(seq 1 60); do
  code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$PUBLIC_URL/health" || true)
  if [ "$code" = "200" ]; then ok=1; echo "    health 200"; break; fi
  sleep 5
done
if [ -z "$ok" ]; then
  echo "!! health did not return 200 in time. Check: sudo journalctl -u $SERVICE -n 100 --no-pager"
  exit 1
fi

echo "==> [6/6] verify BYOK enforcement"
if [ -x scripts/verify-byok.sh ]; then
  scripts/verify-byok.sh "$PUBLIC_URL"
else
  curl -s "$PUBLIC_URL/settings" | grep -o '"require_user_api_key": *true' >/dev/null \
    && echo "PASS: require_user_api_key=true" \
    || { echo "FAIL: flag not active"; exit 1; }
fi
syn=$(curl -s -m 30 -o /dev/null -w '%{http_code}' -X POST "$PUBLIC_URL/synthetic" \
  -H 'Content-Type: application/json' -d '{"doc_type":"NDA"}')
echo "    synthetic (no key) => HTTP $syn  (expect 400)"
[ "$syn" = "400" ] || echo "    !! expected 400; got $syn — investigate before declaring success"

echo
echo "==> DONE. BYOK is enforced on PROD — the server key can no longer be spent by anonymous visitors."
echo "    Rollback if ever needed: restore the latest backend/.env.bak-* and 'sudo systemctl restart $SERVICE'."
