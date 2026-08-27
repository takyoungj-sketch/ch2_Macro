#!/usr/bin/env bash
# CH2 DATA unified board — static UI into hub + FastAPI board API
# VPS is scp-based (not a live git clone). Do not git reset.
# Usage: bash /opt/ch2_Macro/deploy/scripts/redeploy-board.sh
set -euo pipefail

REPO_ROOT="/opt/ch2_Macro"
HUB_DEST="/var/www/ch2data-hub"
BOARD_SRC="$REPO_ROOT/deploy/board/public"
NGINX_SITE="/etc/nginx/sites-available/ch2data-hub"

if [[ ! -d "$BOARD_SRC" ]]; then
  echo "ERROR: $BOARD_SRC missing" >&2
  exit 1
fi

if [[ -x "$REPO_ROOT/deploy/scripts/vps_apply_platform_db.sh" ]]; then
  echo "==> platform DB migration (if configured)"
  bash "$REPO_ROOT/deploy/scripts/vps_apply_platform_db.sh" || echo "WARN: platform DB migration skipped/failed" >&2
fi

echo "==> copy board UI to $HUB_DEST/board"
sudo mkdir -p "$HUB_DEST/board"
sudo rsync -a "$BOARD_SRC/" "$HUB_DEST/board/"
sudo chown -R www-data:www-data "$HUB_DEST/board"

echo "==> restart backend (platform routes)"
sudo systemctl restart ch2-macro-backend
sleep 2

echo "==> nginx (hub site)"
if [[ -f "$REPO_ROOT/deploy/templates/nginx-ch2data-hub.conf" && -f "$NGINX_SITE" ]]; then
  sudo cp "$REPO_ROOT/deploy/templates/nginx-ch2data-hub.conf" "$NGINX_SITE"
  sudo nginx -t
  sudo systemctl reload nginx
else
  echo "WARN: nginx hub site missing — run deploy-hub.sh first" >&2
fi

echo "==> health"
if curl -sf -o /dev/null "http://127.0.0.1:8000/api/board/meta"; then
  echo "OK: board API via FastAPI"
else
  echo "WARN: /api/board/meta not ready — set DATABASE_URL_PLATFORM in backend/.env" >&2
fi
if curl -sf -o /dev/null "https://ch2data.com/board/" || curl -sf -o /dev/null "http://127.0.0.1/board/"; then
  echo "OK: board static"
fi

echo "OK: ch2 board redeploy complete"
