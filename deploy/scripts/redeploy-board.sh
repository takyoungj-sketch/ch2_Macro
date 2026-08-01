#!/usr/bin/env bash
# CH2 DATA unified board — static UI + FastAPI board API (Postgres ch2_platform)
# Usage: /opt/ch2_Macro/deploy/scripts/redeploy-board.sh [branch]
set -euo pipefail

REPO_ROOT="/opt/ch2_Macro"
BRANCH="${1:-main}"

cd "$REPO_ROOT"

echo "==> redeploy board branch=$BRANCH"

git fetch origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [[ ! -d "$REPO_ROOT/deploy/board/public" ]]; then
  echo "ERROR: deploy/board/public missing" >&2
  exit 1
fi

if [[ -x "$REPO_ROOT/deploy/scripts/vps_apply_platform_db.sh" ]]; then
  echo "==> platform DB migration (if configured)"
  bash "$REPO_ROOT/deploy/scripts/vps_apply_platform_db.sh" || echo "WARN: platform DB migration skipped/failed" >&2
fi

echo "==> restart backend (platform routes)"
sudo systemctl restart ch2-macro-backend
sleep 2

echo "==> nginx (hub site — static /board + FastAPI /api/board)"
NGINX_SITE="/etc/nginx/sites-available/ch2data-hub"
if [[ -f "$NGINX_SITE" ]]; then
  sudo cp "$REPO_ROOT/deploy/templates/nginx-ch2data-hub.conf" "$NGINX_SITE"
  sudo nginx -t
  sudo systemctl reload nginx
else
  echo "WARN: $NGINX_SITE missing — run deploy-hub.sh first" >&2
fi

echo "==> health"
if curl -sf -o /dev/null "http://127.0.0.1:8000/api/board/meta"; then
  echo "OK: board API via FastAPI"
else
  echo "WARN: /api/board/meta not ready — set DATABASE_URL_PLATFORM and Google OAuth in backend/.env" >&2
fi

echo "OK: ch2 board redeploy complete"
