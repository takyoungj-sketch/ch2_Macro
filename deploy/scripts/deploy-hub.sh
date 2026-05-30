#!/usr/bin/env bash
# CH2 DATA hub — static files to /var/www/ch2data-hub + nginx site enable
# Usage: sudo bash /opt/ch2_Macro/deploy/scripts/deploy-hub.sh
set -euo pipefail

REPO_ROOT="/opt/ch2_Macro"
HUB_SRC="$REPO_ROOT/deploy/hub"
HUB_DEST="/var/www/ch2data-hub"
NGINX_SITE="/etc/nginx/sites-available/ch2data-hub"
NGINX_ENABLED="/etc/nginx/sites-enabled/ch2data-hub"

if [[ ! -d "$HUB_SRC" ]]; then
  echo "ERROR: hub source missing: $HUB_SRC" >&2
  exit 1
fi

echo "==> sync hub static files"
sudo mkdir -p "$HUB_DEST"
sudo rsync -a --delete "$HUB_SRC/" "$HUB_DEST/"
sudo chown -R www-data:www-data "$HUB_DEST"

echo "==> nginx site ch2data-hub"
sudo cp "$REPO_ROOT/deploy/templates/nginx-ch2data-hub.conf" "$NGINX_SITE"
sudo ln -sf "$NGINX_SITE" "$NGINX_ENABLED"

echo "==> reload nginx"
sudo nginx -t
sudo systemctl reload nginx

echo "OK: hub deployed to $HUB_DEST"
