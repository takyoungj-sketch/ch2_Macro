#!/usr/bin/env bash
# VPS: .env vs Settings vs OAuth redirect client_id 비교
set -euo pipefail

EXPECTED_ID="765026169420-mf7ba6iktjqc51e406i8s3f79t9u0oc.apps.googleusercontent.com"
ENV_FILE=/opt/ch2_Macro/backend/.env
VENV=/opt/ch2_Macro/backend/.venv/bin/python

cd /opt/ch2_Macro/backend

echo "==> 1) backend/.env GOOGLE_*"
grep -E '^GOOGLE_(CLIENT_ID|CLIENT_SECRET|OAUTH_REDIRECT_URI)=' "$ENV_FILE" | sed 's/GOOGLE_CLIENT_SECRET=.*/GOOGLE_CLIENT_SECRET=***/'

echo
echo "==> 2) Settings load (same process as uvicorn would read)"
$VENV <<'PY'
from app.config import settings
print("settings.google_client_id=", settings.google_client_id)
print("settings.google_oauth_redirect_uri=", settings.google_oauth_redirect_uri)
print("settings.platform_database_url set=", bool((settings.platform_database_url or "").strip()))
print("settings.google_client_secret set=", bool((settings.google_client_secret or "").strip()))
PY

echo
echo "==> 3) OAuth redirect client_id (running backend)"
LOC=$(curl -s -D - -o /dev/null http://127.0.0.1:8000/api/auth/google/login | grep -i '^location:' | cut -d' ' -f2- | tr -d '\r')
OAUTH_CID=$(python3 -c "import urllib.parse,sys; q=urllib.parse.urlparse(sys.argv[1]).query; print(dict(urllib.parse.parse_qsl(q)).get('client_id',''))" "$LOC")
echo "redirect client_id=$OAUTH_CID"

echo
echo "==> 4) Compare with Google Cloud Console expected"
echo "expected=$EXPECTED_ID"
ENV_CID=$(grep '^GOOGLE_CLIENT_ID=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
SETTINGS_CID=$($VENV -c "from app.config import settings; print(settings.google_client_id)")

MISMATCH=0
if [[ "$ENV_CID" != "$EXPECTED_ID" ]]; then echo "MISMATCH env: $ENV_CID"; MISMATCH=1; fi
if [[ "$SETTINGS_CID" != "$EXPECTED_ID" ]]; then echo "MISMATCH settings: $SETTINGS_CID"; MISMATCH=1; fi
if [[ "$OAUTH_CID" != "$EXPECTED_ID" ]]; then echo "MISMATCH oauth: $OAUTH_CID"; MISMATCH=1; fi

if [[ "$ENV_CID" != "$SETTINGS_CID" ]]; then
  echo "MISMATCH: .env != Settings (backend may need restart or wrong cwd)"
  MISMATCH=1
fi

if [[ "$SETTINGS_CID" != "$OAUTH_CID" ]]; then
  echo "MISMATCH: Settings != OAuth redirect"
  MISMATCH=1
fi

if [[ $MISMATCH -eq 0 ]]; then
  echo "ALL_MATCH OK"
else
  exit 1
fi

echo
echo "==> 5) systemd backend env (pid start time)"
PID=$(systemctl show -p MainPID --value ch2-macro-backend)
echo "MainPID=$PID"
ps -p "$PID" -o lstart= 2>/dev/null || true
