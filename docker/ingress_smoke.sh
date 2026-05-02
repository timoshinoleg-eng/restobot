#!/usr/bin/env bash
# Ingress regression smoke for Caddy routing.
# Run on the VM where Caddy is listening on localhost:80.
set -euo pipefail

BASE_URL="${1:-http://localhost}"
FAIL=0

check() {
    local url="$1"
    local method="${2:-GET}"
    local want_status="$3"
    local want_body="${4:-}"
    local label="$5"

    local body_file
    body_file=$(mktemp)
    local status
    status=$(curl -s -o "$body_file" -w "%{http_code}" -X "$method" "$url" || true)

    if [ "$status" != "$want_status" ]; then
        echo "FAIL $label: expected HTTP $want_status, got $status"
        cat "$body_file"
        echo
        FAIL=1
    elif [ -n "$want_body" ] && ! grep -q "$want_body" "$body_file"; then
        echo "FAIL $label: status $status OK, but body missing '$want_body'"
        cat "$body_file"
        echo
        FAIL=1
    else
        echo "PASS $label: HTTP $status"
    fi
    rm -f "$body_file"
}

echo ">>> Ingress regression smoke against $BASE_URL"

check "$BASE_URL/admin/health" GET 200 "" "/admin/health -> 200"
check "$BASE_URL/widget/health" GET 200 "" "/widget/health -> 200"
check "$BASE_URL/unknown-path-xyz" GET 404 "Not Found" "unknown path -> 404 (Caddy catch-all)"
check "$BASE_URL/admin/onboarding" POST 403 "Bootstrap API is disabled" "POST /admin/onboarding -> 403 (backend, not Caddy 404)"

if [ "$FAIL" -ne 0 ]; then
    echo ">>> INGRESS SMOKE FAILED"
    exit 1
fi

echo ">>> INGRESS SMOKE PASSED"
