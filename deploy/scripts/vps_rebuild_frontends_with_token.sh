#!/usr/bin/env bash
# VPS: frontend / frontend-built .env 에 VITE_API_TOKEN 주입 후 재빌드
set -euo pipefail
REPO=/opt/ch2_Macro
ENV_FILE="$REPO/backend/.env"
TOKEN=$(grep '^API_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: API_TOKEN missing in backend/.env"
  exit 1
fi

for app in frontend frontend-built frontend-collective; do
  echo "VITE_API_TOKEN=$TOKEN" > "$REPO/$app/.env"
  chmod 600 "$REPO/$app/.env"
  echo "==> build $app"
  cd "$REPO/$app"
  npm ci --silent
  npm run build
done

echo "OK: frontends rebuilt with VITE_API_TOKEN"
bash "$REPO/deploy/scripts/vps_sync_nginx_api_token.sh" 2>/dev/null || true
