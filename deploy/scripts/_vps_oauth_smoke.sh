#!/usr/bin/env bash
set -euo pipefail

echo "==> board meta (local)"
curl -sf http://127.0.0.1:8000/api/board/meta | python3 -m json.tool | head -20

echo "==> google login redirect (local GET)"
curl -s -D /tmp/login.hdr -o /dev/null http://127.0.0.1:8000/api/auth/google/login
grep -i '^HTTP' /tmp/login.hdr
grep -i '^location:' /tmp/login.hdr
LOC=$(grep -i '^location:' /tmp/login.hdr | cut -d' ' -f2- | tr -d '\r')
echo "$LOC" | grep -q 'accounts.google.com'
echo "$LOC" | grep -q '765026169420-mf7ba6iktjqc51e406i8s3f79t9u0oc'
echo "$LOC" | grep -q 'redirect_uri=https%3A%2F%2Fch2data.com%2Fapi%2Fauth%2Fgoogle%2Fcallback'

echo "==> invalid callback (local)"
CODE=$(curl -s -o /tmp/cb.json -w '%{http_code}' "http://127.0.0.1:8000/api/auth/google/callback?code=invalid_test_code&state=/board/")
echo "callback HTTP=$CODE body=$(cat /tmp/cb.json)"

echo "==> users count"
sudo -u postgres psql -d ch2_platform -tAc 'SELECT COUNT(*) FROM users'

echo "==> public https login redirect"
curl -s -D /tmp/plogin.hdr -o /dev/null https://ch2data.com/api/auth/google/login
grep -i '^HTTP' /tmp/plogin.hdr
grep -i '^location:' /tmp/plogin.hdr
PLOC=$(grep -i '^location:' /tmp/plogin.hdr | cut -d' ' -f2- | tr -d '\r')
echo "$PLOC" | grep -q 'accounts.google.com'

echo "==> public board meta"
curl -sf https://ch2data.com/api/board/meta | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['auth']['enabled'] is True; print('auth.enabled OK')"

echo SMOKE_OK
