#!/usr/bin/env bash
# VPS에서 1회 실행: 코드 tar + built_stats dump 반영 (이미 /var/backups/ch2/ 에 업로드됨)
set -euo pipefail

REPO=/opt/ch2_Macro
TAR=/var/backups/ch2/ch2_built_deploy_sync.tar
DUMP=/var/backups/ch2/built_stats_promote.sql

echo "==> extract code (keep backend/.env)"
cd "$REPO"
tar -xf "$TAR" -C "$REPO"
chmod +x deploy/scripts/*.sh 2>/dev/null || true
sed -i 's/\r$//' deploy/scripts/*.sh 2>/dev/null || true

echo "==> backend .env BUILT_DATABASE_URL"
ENV_FILE="$REPO/backend/.env"
if ! grep -q '^BUILT_DATABASE_URL=' "$ENV_FILE"; then
  LAND_URL=$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)
  if echo "$LAND_URL" | grep -q land_stats; then
    BUILT_URL=$(echo "$LAND_URL" | sed 's/land_stats/built_stats/')
  else
    BUILT_URL="${LAND_URL%/*}/built_stats"
  fi
  echo "BUILT_DATABASE_URL=$BUILT_URL" >> "$ENV_FILE"
  echo "added BUILT_DATABASE_URL"
else
  echo "BUILT_DATABASE_URL already set"
fi

echo "==> built_stats DB + restore"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='built_stats'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE built_stats OWNER ch2app;"
fi

sudo systemctl stop ch2-macro-backend
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'built_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS built_stats;
CREATE DATABASE built_stats OWNER ch2app;
SQL

set +e
if [[ "$DUMP" == *.sql ]]; then
  sed -e '/^SET transaction_timeout/d' -e '/^\\restrict/d' -e '/^\\unrestrict/d' "$DUMP" \
    | sudo -u postgres psql -v ON_ERROR_STOP=1 -d built_stats 2>&1 | tail -15
else
  sudo -u postgres pg_restore -d built_stats --no-owner --no-acl "$DUMP" 2>&1 | tail -10
fi
set -e

sudo -u postgres psql -d built_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

sudo -u postgres psql -d built_stats -t -c "SELECT asset_type, COUNT(*) FROM built_transactions GROUP BY 1 ORDER BY 1;"

echo "==> backend deps"
cd "$REPO/backend"
source .venv/bin/activate
pip install -q -r requirements.txt

echo "==> frontend land build"
cd "$REPO/frontend"
npm ci --silent
npm run build

echo "==> frontend built"
cd "$REPO/frontend-built"
if [[ ! -f .env ]] && [[ -f ../frontend/.env ]]; then
  TOKEN=$(grep '^VITE_API_TOKEN=' ../frontend/.env | cut -d= -f2- || true)
  if [[ -n "${TOKEN:-}" ]]; then
    echo "VITE_API_TOKEN=$TOKEN" > .env
    chmod 600 .env
  fi
fi
npm ci --silent
npm run build

echo "==> nginx"
sudo cp "$REPO/deploy/templates/nginx-ch2-macro.conf" /etc/nginx/sites-available/ch2-macro
sudo nginx -t
sudo systemctl reload nginx

echo "==> hub"
sudo bash "$REPO/deploy/scripts/deploy-hub.sh"

echo "==> restart backend"
sudo systemctl start ch2-macro-backend
sleep 2
curl -sf http://127.0.0.1:8000/health
echo
curl -sI -H "Host: macro.ch2data.com" http://127.0.0.1/ | head -3
curl -sI -H "Host: macro.ch2data.com" http://127.0.0.1/land/ | head -3
curl -sI -H "Host: macro.ch2data.com" http://127.0.0.1/built/ | head -3
echo "OK: built deploy complete"
