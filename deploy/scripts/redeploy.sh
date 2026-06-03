#!/usr/bin/env bash
# CH2 Macro — git pull 후 backend + land/built frontend + gateway 재배포 (dev VPS)
# Usage: /opt/ch2_Macro/deploy/scripts/redeploy.sh [branch]
set -euo pipefail

REPO_ROOT="/opt/ch2_Macro"
BRANCH="${1:-main}"

echo "==> redeploy branch=$BRANCH"

cd "$REPO_ROOT"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "==> backend dependencies"
cd "$REPO_ROOT/backend"
source .venv/bin/activate
pip install -q -r requirements.txt

echo "==> frontend land build"
cd "$REPO_ROOT/frontend"
if [[ ! -f .env ]] && [[ -f "$REPO_ROOT/deploy/templates/frontend.env.production.example" ]]; then
  echo "WARN: frontend/.env missing — copy template and set VITE_API_TOKEN before build"
fi
npm ci
npm run build

echo "==> frontend built build"
cd "$REPO_ROOT/frontend-built"
if [[ ! -f .env ]] && [[ -f "$REPO_ROOT/deploy/templates/frontend-built.env.production.example" ]]; then
  echo "WARN: frontend-built/.env missing — copy template and set VITE_API_TOKEN before build"
fi
npm ci
npm run build

echo "==> macro gateway"
if [[ -x "$REPO_ROOT/deploy/scripts/deploy-macro-gateway.sh" ]]; then
  bash "$REPO_ROOT/deploy/scripts/deploy-macro-gateway.sh"
fi

echo "==> restart services"
bash "$REPO_ROOT/deploy/scripts/vps_sync_nginx_api_token.sh" 2>/dev/null || true
sudo systemctl restart ch2-macro-backend
sudo nginx -t
sudo systemctl reload nginx

echo "==> health"
sleep 2
curl -sf "http://127.0.0.1:8000/health" | head -c 800
echo
echo "OK: redeploy complete (gateway /, land /land/, built /built/)"
