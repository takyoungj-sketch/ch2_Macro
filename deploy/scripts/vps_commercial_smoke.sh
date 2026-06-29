#!/usr/bin/env bash
# Commercial cluster mart + rolling smoke (mirror vps_collective_smoke.sh)
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")
BASE=http://127.0.0.1:8000/api/collective/commercial

echo "==> clusters list (5y mart)"
LIST=$(curl -sf "${HDR[@]}" \
  "$BASE/clusters?addr1=%EC%84%9C%EC%9A%B8%ED%8A%B9%EB%B3%84%EC%8B%9C&addr2=%EC%A2%85%EB%A1%9C%EA%B5%AC&window_years=5&page_size=3")
echo "$LIST" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('total', d.get('total'), 'items', len(d.get('items',[])), 'source', d.get('data_source'), 'as_of', d.get('stats_as_of_label'))
items=d.get('items') or []
if not items:
    raise SystemExit('FAIL: no clusters')
print('first', items[0].get('cluster_key','')[:12], items[0].get('count'))
"
KEY=$(echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('items') or [{}])[0]['cluster_key'])")

echo "==> rolling 5y cluster=$KEY"
curl -sf "${HDR[@]}" \
  "$BASE/clusters/$KEY/stats/rolling?window_years=5" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
pts=d.get('points',[])
print('points', len(pts), 'source', d.get('data_source'))
if len(pts) < 1:
    raise SystemExit('FAIL: no rolling points')
"

echo "==> by-year"
curl -sf "${HDR[@]}" \
  "$BASE/clusters/$KEY/stats/by-year" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
pts=d.get('points',[])
print('years', len(pts), 'source', d.get('data_source'))
"

echo "==> cohort histogram (2 clusters)"
KEY2=$(echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or []; print(items[1]['cluster_key'] if len(items)>1 else items[0]['cluster_key'])")
curl -sf "${HDR[@]}" -X POST "$BASE/analysis/cohort/histogram" \
  -H 'Content-Type: application/json' \
  -d "{\"cluster_keys\":[\"$KEY\",\"$KEY2\"],\"year_from\":2021,\"year_to\":2026}" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('cohort bins', len(d.get('bins',[])), 'n', d.get('n'))
"

echo "OK: commercial smoke passed"
