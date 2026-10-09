#!/usr/bin/env bash
# 토스 테스트 키·구독 API 준비 상태 확인 (시크릿 출력 없음)
set -euo pipefail

ENV_FILE="/opt/ch2_Macro/backend/.env"
API="https://ch2data.com"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[[ -f "$ENV_FILE" ]] || fail "missing $ENV_FILE"

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

ck="${TOSS_CLIENT_KEY:-}"
sk="${TOSS_SECRET_KEY:-}"

if [[ -z "$ck" || -z "$sk" ]]; then
  fail "TOSS_CLIENT_KEY 또는 TOSS_SECRET_KEY가 비어 있습니다. $ENV_FILE 에 MID ch2datoe5e 의 API 개별 연동 테스트 키를 넣으세요."
fi

case "$ck" in
  test_ck_*)
    echo "OK: client key prefix test_ck_ (API 개별 연동)"
    ;;
  test_gck_*)
    fail "client key가 test_gck_ 입니다. 결제위젯 키가 아니라 API 개별 연동 test_ck_ 키가 필요합니다."
    ;;
  *)
    echo "WARN: client key가 test_ck_ 로 시작하지 않습니다. 테스트/라이브 키 종류를 확인하세요."
    ;;
esac

echo "==> /api/billing/toss/config"
cfg=$(curl -sf "$API/api/billing/toss/config") || fail "billing config API unreachable"
echo "$cfg" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if not d.get('enabled'):
    raise SystemExit('enabled=false — 백엔드 재시작 후 다시 확인하세요.')
ck=d.get('clientKey') or ''
if not ck.startswith('test_ck_'):
    raise SystemExit('public clientKey prefix unexpected')
print('OK: enabled=true, clientKey prefix', ck[:12]+'...')
"

if [[ -z "${PLATFORM_REVIEW_EMAIL:-}" || -z "${PLATFORM_REVIEW_PASSWORD:-}" ]]; then
  echo "WARN: PLATFORM_REVIEW_EMAIL/PASSWORD 없음 — 심사용 로그인 불가"
else
  echo "==> review-login + billing/prepare (smoke)"
  jar=$(mktemp)
  login_body=$(python3 -c "import json,os; print(json.dumps({'email':os.environ['PLATFORM_REVIEW_EMAIL'],'password':os.environ['PLATFORM_REVIEW_PASSWORD']}))")
  curl -sf -c "$jar" -b "$jar" -X POST "$API/api/auth/review-login" \
    -H "Content-Type: application/json" \
    -d "$login_body" >/dev/null \
    || fail "review-login failed"

  prep=$(curl -sf -b "$jar" -X POST "$API/api/billing/toss/billing/prepare" \
    -H "Content-Type: application/json" \
    -d '{"plan_id":"macro_monthly"}') || fail "billing/prepare failed"
  echo "$prep" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for k in ('clientKey','customerKey','pendingId'):
    if not d.get(k):
        raise SystemExit(f'missing {k}')
print('OK: billing/prepare pendingId=', d['pendingId'][:24]+'...')
"
  rm -f "$jar"
fi

echo ""
echo "다음: 브라우저에서 https://ch2data.com/subscribe/ → 심사 로그인 → 「카드로 구독하기」"
echo "테스트 카드: 토스 문서의 테스트 번호 사용. 완료 후 billing-success 페이지에서 activate 호출됩니다."
