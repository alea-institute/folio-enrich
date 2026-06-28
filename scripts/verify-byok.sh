#!/usr/bin/env bash
#
# verify-byok.sh — confirm bring-your-own-key (BYOK) enforcement is active.
#
# Checks that a FOLIO Enrich instance is NOT serving requests with a
# server-stored LLM API key. Use it before/after enabling
# FOLIO_ENRICH_REQUIRE_USER_API_KEY on a public deployment.
#
# Usage:
#   scripts/verify-byok.sh [BASE_URL]
#
# Examples:
#   scripts/verify-byok.sh                                  # http://localhost:8000
#   scripts/verify-byok.sh https://enrich.openlegalstandard.org
#
# Exit code: 0 = BYOK enforced (public cannot spend the operator's key)
#            1 = NOT enforced, or the instance is unreachable
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"

echo "Checking BYOK enforcement at: $BASE_URL"
echo

health=$(curl -fsS "$BASE_URL/health/detail") || {
  echo "FAIL: could not reach $BASE_URL/health/detail" >&2
  exit 1
}
settings=$(curl -fsS "$BASE_URL/settings") || {
  echo "FAIL: could not reach $BASE_URL/settings" >&2
  exit 1
}

# Parse with python3 (no jq dependency). Prints a verdict and sets exit status.
HEALTH_JSON="$health" SETTINGS_JSON="$settings" python3 - <<'PY'
import json, os, sys

health = json.loads(os.environ["HEALTH_JSON"])
settings = json.loads(os.environ["SETTINGS_JSON"])

llm = health.get("llm", {})
llm_status = llm.get("status")
provider = llm.get("provider")
model = llm.get("model")
require = settings.get("require_user_api_key")

# Any provider key the server reports as usable for requests.
exposed = [k for k, v in settings.items() if k.endswith("_api_key_set") and v]

print(f"  provider/model         : {provider} / {model}")
print(f"  llm.status             : {llm_status}")
print(f"  require_user_api_key   : {require}")
print(f"  keys reported usable   : {exposed or 'none'}")
print()

ok = (require is True) and (llm_status == "no_api_key") and (not exposed)

if ok:
    print("PASS: BYOK enforced — no server key is used to serve requests.")
    sys.exit(0)

print("FAIL: server key may be spent by anonymous users.")
if require is None:
    print("  -> This build predates the BYOK flag; deploy the latest code first.")
elif require is not True:
    print("  -> Set FOLIO_ENRICH_REQUIRE_USER_API_KEY=true on the host and restart.")
else:
    print("  -> Flag is on but a key still reads as usable; check provider config.")
sys.exit(1)
PY
