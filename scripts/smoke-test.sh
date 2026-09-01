#!/usr/bin/env bash
# Post-deploy verification. Runs after a deploy and before traffic is trusted:
# if this fails, the deploy is rolled back rather than left half-live.
#
#   BASE_URL=https://staging.example.com ./scripts/smoke-test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
TIMEOUT="${TIMEOUT:-10}"
failures=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; failures=$((failures + 1)); }

check_status() {
  local name="$1" path="$2" expected="$3"
  local actual
  actual=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "${BASE_URL}${path}" || echo "000")
  if [ "$actual" = "$expected" ]; then
    pass "$name (${path} -> ${actual})"
  else
    fail "$name (${path} -> ${actual}, expected ${expected})"
  fi
}

check_body() {
  local name="$1" path="$2" needle="$3"
  local body
  body=$(curl -sS --max-time "$TIMEOUT" "${BASE_URL}${path}" || echo "")
  if printf '%s' "$body" | grep -q "$needle"; then
    pass "$name"
  else
    fail "$name (expected to find '${needle}')"
  fi
}

echo "Smoke test against ${BASE_URL}"

# 1. The process is up.
check_status "liveness" /livez 200

# 2. Its dependencies are reachable — this is what gates traffic.
check_status "readiness" /readyz 200
check_body   "readiness reports every dependency healthy" /readyz '"status":"ready"'

# 3. Routing to the API actually works (not just the health endpoints).
check_status "API is routed" /api/health 200

# 4. Auth is enforced. A 200 here would mean the auth middleware vanished.
check_status "protected endpoint rejects anonymous access" /api/notes 401

# 5. The frontend is served.
check_status "frontend" / 200

echo
if [ "$failures" -gt 0 ]; then
  echo "Smoke test FAILED: ${failures} check(s) failed."
  exit 1
fi
echo "Smoke test passed."
