#!/usr/bin/env bash
set -euo pipefail
TOKEN="$(grep '^VITE_API_TOKEN=' /opt/ch2_Macro/frontend/.env | cut -d= -f2-)"
curl -sf -H "X-Api-Token: ${TOKEN}" \
  "http://127.0.0.1:8000/api/free/regions?search=%EA%B0%80%EA%B2%BD%EB%8F%99&limit=3" | head -c 400
echo
