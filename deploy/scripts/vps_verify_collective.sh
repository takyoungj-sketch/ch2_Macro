#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
CH2PASS=$(grep '^BUILT_DATABASE_URL=' "$ENV" | sed -n 's/.*:\/\/ch2app:\([^@]*\)@.*/\1/p')
export PGPASSWORD="$CH2PASS"
echo "region_codes collective: $(psql -h 127.0.0.1 -U ch2app -d collective_stats -Atqc 'SELECT COUNT(*) FROM region_codes')"
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
echo "==> /api/collective/meta/filters"
curl -sf -H "X-Api-Token: $TOKEN" http://127.0.0.1:8000/api/collective/meta/filters | head -c 250
echo
echo "==> /api/collective/commercial/meta/filters"
curl -sf -H "X-Api-Token: $TOKEN" http://127.0.0.1:8000/api/collective/commercial/meta/filters | head -c 250
echo
