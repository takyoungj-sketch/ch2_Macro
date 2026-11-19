#!/usr/bin/env bash
# 조회만 하는 스모크. DDL·재시작·쓰기 없음.
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")
BASE=http://127.0.0.1:8000

expect_login_gate() {
  local url="$1"
  local label="$2"
  local code
  code=$(curl -sS -o /tmp/ch2_smoke_body.json -w '%{http_code}' --max-time 30 "${HDR[@]}" "$url")
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

# addr2가 없으면 라우터가 400을 낸다. 목록은 5년 롤링 기본이라 비로그인도 열린다.
KEY=$(curl -sf "${HDR[@]}" "$BASE/api/collective/buildings?search=%EA%B4%91%EC%A7%84&addr2=%EA%B4%91%EC%A7%84%EA%B5%AC&asset_type=officetel&window_years=5&limit=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or []; print(next((x['building_key'] for x in items if '캠퍼스' in x.get('display_name','')), items[0]['building_key'] if items else ''))")
echo "building_key=$KEY"
if [[ -z "$KEY" ]]; then
  echo "FAIL: building key empty"
  exit 1
fi

echo "==> rolling"
curl -sf "${HDR[@]}" "$BASE/api/collective/buildings/${KEY}/stats/rolling?window_years=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('points',len(d.get('points',[])),'source',d.get('data_source'))"

echo "==> tx gate"
expect_login_gate "$BASE/api/collective/buildings/${KEY}/transactions?page=1&page_size=5" "transactions"

echo "==> yearly gate"
expect_login_gate "$BASE/api/collective/buildings/${KEY}/stats/by-year" "stats/by-year"

echo "OK: collective smoke passed"
