#!/usr/bin/env bash
# 조회만 하는 스모크. /api/built/ 는 구독 게이트라 비로그인 401이 정상이다.
set -euo pipefail

expect_login_gate() {
  local url="$1"
  local label="$2"
  local code
  code=$(curl -sk -o /tmp/ch2_smoke_body.json -w '%{http_code}' --max-time 30 "$url")
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

echo "=== API meta/filters (nginx injects proxy token; subscription gate remains) ==="
expect_login_gate "https://macro.ch2data.com/api/built/meta/filters" "built meta/filters"

echo "=== API addr2 for Seoul ==="
expect_login_gate "https://macro.ch2data.com/api/built/regions/addr2?addr1=%EC%84%9C%EC%9A%B8%ED%8A%B9%EB%B3%84%EC%8B%9C" "built addr2"

echo "OK: built region gate smoke passed"
