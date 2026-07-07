#!/usr/bin/env bash
# CH2 DATA unified board — git sync + systemd + nginx (VPS)
# Usage: /opt/ch2_Macro/deploy/scripts/redeploy-board.sh [branch]
set -euo pipefail

REPO_ROOT="/opt/ch2_Macro"
BRANCH="${1:-main}"
SERVICE_NAME="ch2-board"
BOARD_PORT="${CH2_BOARD_PORT:-5180}"

cd "$REPO_ROOT"

echo "==> redeploy board branch=$BRANCH"

git fetch origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [[ ! -f "$REPO_ROOT/deploy/board/server.mjs" ]]; then
  echo "ERROR: deploy/board/server.mjs not found" >&2
  exit 1
fi

mkdir -p "$REPO_ROOT/deploy/board/data"
chown -R ubuntu:ubuntu "$REPO_ROOT/deploy/board/data" 2>/dev/null || true

echo "==> systemd unit"
sudo cp "$REPO_ROOT/deploy/templates/ch2-board.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "==> nginx (hub site includes /board proxy)"
NGINX_SITE="/etc/nginx/sites-available/ch2data-hub"
if [[ -f "$NGINX_SITE" ]]; then
  sudo cp "$REPO_ROOT/deploy/templates/nginx-ch2data-hub.conf" "$NGINX_SITE"
  sudo nginx -t
  sudo systemctl reload nginx
else
  echo "WARN: $NGINX_SITE missing — run deploy-hub.sh first" >&2
fi

echo "==> health"
sleep 1
if curl -sf -o /dev/null "http://127.0.0.1:${BOARD_PORT}/health" \
  && curl -sf -o /dev/null "http://127.0.0.1:${BOARD_PORT}/board"; then
  echo "OK: board on port ${BOARD_PORT}"
else
  echo "ERROR: board not responding" >&2
  sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
  exit 1
fi

echo "OK: ch2 board redeploy complete"
