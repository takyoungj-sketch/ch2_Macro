#!/usr/bin/env bash
# VPS 원격: 복합 지역 선택 수정 (nginx API 토큰 주입 + 백엔드 + frontend-built 재빌드)
set -euo pipefail
REPO=/opt/ch2_Macro
sudo cp "$REPO/deploy/templates/nginx-ch2-macro.conf" /etc/nginx/sites-available/ch2-macro
bash "$REPO/deploy/scripts/vps_sync_nginx_api_token.sh"
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart ch2-macro-backend
sleep 2
echo "VITE_API_TOKEN=$(grep '^API_TOKEN=' "$REPO/backend/.env" | cut -d= -f2- | tr -d '\r')" > "$REPO/frontend-built/.env"
chmod 600 "$REPO/frontend-built/.env"
cd "$REPO/frontend-built"
npm run build
echo "OK: built regions fix deployed"
