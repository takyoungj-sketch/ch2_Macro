#!/usr/bin/env bash
# 조회만 하는 스모크. 상업 클러스터 목록·5년 롤링은 무료, 연도 통계·코호트는 구독 게이트.
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

expect_login_gate() {
  local url="$1"
  local label="$2"
  shift 2
  local code
  code=$(curl -sS -o /tmp/ch2_smoke_body.json -w '%{http_code}' --max-time 30 "${HDR[@]}" "$@" "$url")
  python3 - "$label" "$code" <<'PY'
import json, sys
label, code = sys.argv[1], sys.argv[2]
raw = open("/tmp/ch2_smoke_body.json", "rb").read()
try:
    data = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    data = {}
detail = data.get("detail") if isinstance(data, dict) else None
if code == "401" and detail == "로그인이 필요합니다.":
    print(f"OK: {label} gate 401")
    raise SystemExit(0)
print(f"FAIL: {label} expected 401 로그인이 필요합니다., got {code} detail={detail!r}")
raise SystemExit(1)
PY
}

echo "==> by-year gate"
expect_login_gate "$BASE/clusters/$KEY/stats/by-year" "commercial by-year"

echo "==> cohort histogram gate"
KEY2=$(echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or []; print(items[1]['cluster_key'] if len(items)>1 else items[0]['cluster_key'])")
expect_login_gate "$BASE/analysis/cohort/histogram" "commercial cohort" \
  -X POST -H 'Content-Type: application/json' \
  -d "{\"cluster_keys\":[\"$KEY\",\"$KEY2\"],\"year_from\":2021,\"year_to\":2026}"

echo "OK: commercial smoke passed"
