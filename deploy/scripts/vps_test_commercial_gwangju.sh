#!/usr/bin/env bash
set -euo pipefail
TOKEN=$(grep '^API_TOKEN=' /opt/ch2_Macro/backend/.env | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")
BASE="http://127.0.0.1:8000/api/collective/commercial"

echo "==> structure"
curl -sf "${HDR[@]}" "$BASE/regions/structure?addr1=광주광역시&addr2=남구&asset_type=collective_shop"

echo
echo "==> addr3"
curl -sf "${HDR[@]}" "$BASE/regions/addr3?addr1=광주광역시&addr2=남구&asset_type=collective_shop" | head -c 600

echo
echo "==> leaf"
curl -sf "${HDR[@]}" "$BASE/regions/leaf?addr1=광주광역시&addr2=남구&asset_type=collective_shop" | head -c 600

echo
echo "==> clusters"
curl -s -w "\nHTTP:%{http_code}\n" "${HDR[@]}" "$BASE/clusters?addr1=광주광역시&addr2=남구&asset_type=collective_shop&page_size=3" | tail -20

echo "==> db sample"
sudo -u postgres psql -d collective_stats -Atc "
SELECT COUNT(*), COUNT(addr3), COUNT(addr4), COUNT(cluster_id)
FROM collective_commercial_transactions
WHERE addr1='광주광역시' AND addr2='남구' AND asset_type='collective_shop' AND is_valid=true;
"
