#!/usr/bin/env bash
set -euo pipefail
REPO=/opt/ch2_Macro
DB_PW=$(cat /home/ubuntu/.ch2_db_password)
if [ -f /home/ubuntu/.ch2_api_token ]; then
  API_TOKEN=$(cat /home/ubuntu/.ch2_api_token)
else
  API_TOKEN=$(openssl rand -hex 32)
  echo "$API_TOKEN" > /home/ubuntu/.ch2_api_token
  chmod 600 /home/ubuntu/.ch2_api_token
fi

echo "==> Backend venv"
cd "$REPO/backend"
if [ ! -d .venv ]; then
  python3.11 -m venv .venv
fi
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
sleep 3
curl -sf http://127.0.0.1:8000/health

echo "==> Frontend build"
cd "$REPO/frontend"
printf 'VITE_API_TOKEN=%s\n' "$API_TOKEN" > .env
npm ci
npm run build

echo "==> Nginx"
sudo cp "$REPO/deploy/templates/nginx-ch2-macro.conf" /etc/nginx/sites-available/ch2-macro
sudo sed -i 's/dev-macro.YOURDOMAIN.com/13.209.203.178/g' /etc/nginx/sites-available/ch2-macro
sudo ln -sf /etc/nginx/sites-available/ch2-macro /etc/nginx/sites-enabled/ch2-macro
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "==> Smoke"
curl -sf http://127.0.0.1:8000/health
curl -sf -H "X-Api-Token: ${API_TOKEN}" "http://127.0.0.1:8000/api/free/regions?limit=1" | head -c 120
curl -sS -o /dev/null -w "nginx_root=%{http_code}\n" http://127.0.0.1/
echo "PHASE3_APP_OK"
