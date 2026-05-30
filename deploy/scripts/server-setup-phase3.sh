#!/usr/bin/env bash
# CH2 Macro dev VPS — phase 3: extract repo, restore DB, backend, frontend, nginx
set -euo pipefail

REPO=/opt/ch2_Macro
DUMP=/var/backups/ch2/land_stats_20260530.dump
DB_PW="$(cat /home/ubuntu/.ch2_db_password)"
API_TOKEN="$(openssl rand -hex 32)"
echo "$API_TOKEN" > /home/ubuntu/.ch2_api_token
chmod 600 /home/ubuntu/.ch2_api_token

echo "==> Extract repo"
cd "$REPO"
tar xzf /tmp/ch2_repo_sync.tar.gz
sed -i 's/\r$//' deploy/scripts/*.sh 2>/dev/null || true

echo "==> pg_restore"
export PGPASSWORD="$DB_PW"
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'land_stats' AND pid <> pg_backend_pid();" || true
sudo -u postgres psql <<SQL
DROP DATABASE IF EXISTS land_stats;
CREATE DATABASE land_stats OWNER ch2app;
SQL
pg_restore -h 127.0.0.1 -U ch2app -d land_stats --no-owner --no-acl --role=ch2app "$DUMP" 2>&1 | tee /var/backups/ch2/restore.log || true
# PG18 pg_dump -Fc 는 서버에 postgresql-client-18 필요:
#   sudo apt install -y postgresql-client-18
#   /usr/lib/postgresql/18/bin/pg_restore ... (위와 동일)

echo "==> DB verify"
psql "postgresql://ch2app:${DB_PW}@127.0.0.1/land_stats" -c "SELECT COUNT(*) AS land_transactions FROM land_transactions;"
psql "postgresql://ch2app:${DB_PW}@127.0.0.1/land_stats" -c "SELECT MAX(as_of_month) FROM land_basic_stats_v2;"

echo "==> Backend venv"
cd "$REPO/backend"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip -q
pip install -r requirements.txt -q

echo "==> Backend .env"
cat > "$REPO/backend/.env" <<EOF
DATABASE_URL=postgresql+psycopg2://ch2app:${DB_PW}@127.0.0.1:5432/land_stats
SECRET_KEY=$(openssl rand -hex 32)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://13.209.203.178
API_TOKEN=${API_TOKEN}
STATS_V2_DEFAULT_AS_OF_MONTH=2026-04-01
paid_analyze_work_mem_mb=192
EOF
chmod 600 "$REPO/backend/.env"

echo "==> systemd"
sudo cp "$REPO/deploy/templates/ch2-macro-backend.service" /etc/systemd/system/ch2-macro-backend.service
sudo systemctl daemon-reload
sudo systemctl enable ch2-macro-backend
sudo systemctl restart ch2-macro-backend
sleep 2
curl -sf http://127.0.0.1:8000/health

echo "==> Frontend build"
cd "$REPO/frontend"
cat > .env <<EOF
VITE_API_TOKEN=${API_TOKEN}
EOF
npm ci --silent
npm run build

echo "==> Nginx site"
sudo cp "$REPO/deploy/templates/nginx-ch2-macro.conf" /etc/nginx/sites-available/ch2-macro
sudo sed -i 's/dev-macro.YOURDOMAIN.com/13.209.203.178/g' /etc/nginx/sites-available/ch2-macro
sudo ln -sf /etc/nginx/sites-available/ch2-macro /etc/nginx/sites-enabled/ch2-macro
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "==> Smoke"
curl -sf http://127.0.0.1:8000/health
curl -sf -H "X-Api-Token: ${API_TOKEN}" "http://127.0.0.1:8000/api/free/regions?limit=2" | head -c 200
curl -sS -o /dev/null -w "nginx_root=%{http_code}\n" http://127.0.0.1/
echo "API_TOKEN saved: /home/ubuntu/.ch2_api_token"
echo "PHASE3_OK"
