#!/usr/bin/env bash
# CH2 Macro — dev VPS smoke test
# Usage:
#   BASE=https://dev-macro.example.com TOKEN=xxx ./health-check.sh
#   ./health-check.sh   # localhost backend only
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:-}"

echo "==> health (no token)"
curl -sf "${BASE%/}/health" | tee /tmp/ch2_health.json
echo

if [[ -n "$TOKEN" ]]; then
  echo "==> regions (with token)"
  curl -sf -H "X-Api-Token: $TOKEN" "${BASE%/}/api/free/regions?limit=3" | head -c 300
  echo
else
  echo "==> skip API test (TOKEN not set)"
fi

echo "==> disk (local VPS only)"
if [[ "$BASE" == http://127.0.0.1:* ]]; then
  df -h / | tail -1
  free -h | head -2
fi

echo "OK"
