#!/usr/bin/env bash
set -euo pipefail

ENV=/opt/ch2_Macro/backend/.env
DB_USER=$(grep '^DATABASE_URL=' "$ENV" | sed -E 's|.*://([^:]+):.*|\1|')

echo "==> create ch2_platform (postgres superuser)"
EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='ch2_platform'" || true)
if [[ "$EXISTS" != "1" ]]; then
  sudo -u postgres psql -c "CREATE DATABASE ch2_platform OWNER ${DB_USER};"
  echo "created ch2_platform owner=${DB_USER}"
else
  echo "ch2_platform already exists"
fi

echo "==> apply migration"
bash /opt/ch2_Macro/deploy/scripts/vps_apply_platform_db.sh

echo "==> restart backend"
sudo systemctl restart ch2-macro-backend
sleep 3
systemctl is-active ch2-macro-backend

echo "==> smoke"
curl -sf http://127.0.0.1:8000/api/board/meta | head -c 300
echo

curl -sI http://127.0.0.1:8000/api/auth/google/login | tr -d '\r' | head -5

echo OK
