#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:5050}"

print_json() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    cat
  fi
}

echo "== 1) HRIS provider resolution =="
curl -sS "${BASE_URL}/api/v2/integrations/hris/status" | print_json
echo

echo "== 2) HRIS live health check =="
curl -sS "${BASE_URL}/api/v2/integrations/hris/status?check=1" | print_json
echo

echo "== 3) Employee asks for own benefits plan =="
curl -sS -X POST "${BASE_URL}/api/v2/query" \
  -H "Content-Type: application/json" \
  -H "X-User-Role: employee" \
  -d '{"query":"show my benefits plan"}' | print_json
echo

echo "== 4) Privacy policy enforcement (other employee) =="
curl -sS -X POST "${BASE_URL}/api/v2/query" \
  -H "Content-Type: application/json" \
  -H "X-User-Role: employee" \
  -d "{\"query\":\"show sarah chen's benefits plan\"}" | print_json
echo
