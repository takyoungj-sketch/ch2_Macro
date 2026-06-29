#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")
BASE=http://127.0.0.1:8000/api/collective/commercial

echo "==> addr3 설악면 count window_years=5"
curl -sf "${HDR[@]}" \
  "$BASE/regions/addr3?addr1=%EA%B2%BD%EA%B8%B0%EB%8F%84&addr2=%EA%B0%80%ED%8F%89%EA%B5%B0&asset_type=collective_shop&window_years=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([x for x in d if x.get('name')=='설악면'])"

LIST=$(curl -sf "${HDR[@]}" \
  "$BASE/clusters?addr1=%EA%B2%BD%EA%B8%B0%EB%8F%84&addr2=%EA%B0%80%ED%8F%89%EA%B5%B0&asset_type=collective_shop&window_years=5&addr3_list=%EC%84%A4%EC%95%85%EB%A9%B4&page_size=5")
echo "==> clusters:" 
echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); print([(i['display_label'],i['count']) for i in d.get('items',[])])"
KEY=$(echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('items') or [{}])[0].get('cluster_key',''))")

echo "==> transactions key=$KEY"
curl -sf "${HDR[@]}" \
  "$BASE/clusters/$KEY/transactions?addr1=%EA%B2%BD%EA%B8%B0%EB%8F%84&addr2=%EA%B0%80%ED%8F%89%EA%B5%B0&addr3_list=%EC%84%A4%EC%95%85%EB%A9%B4&window_years=5&page_size=10" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('total',d.get('total'),'items',len(d.get('items',[])),'date', (d.get('items') or [{}])[0].get('contract_date'))"
