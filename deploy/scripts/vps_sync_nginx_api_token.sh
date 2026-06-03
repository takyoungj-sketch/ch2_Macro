#!/usr/bin/env bash
# VPS: backend/.env API_TOKEN → nginx 프록시 헤더 스니펫 (구 JS 번들·캐시 대비)
set -euo pipefail
REPO=/opt/ch2_Macro
ENV_FILE="$REPO/backend/.env"
OUT="/etc/nginx/snippets/ch2-api-proxy-token.conf"
TOKEN=$(grep '^API_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: API_TOKEN missing in $ENV_FILE"
  exit 1
fi
# nginx 설정에 따옴표 이스케이프
SAFE=${TOKEN//\\/\\\\}
SAFE=${SAFE//\"/\\\"}
printf '%s\n' "proxy_set_header X-CH2-Proxy-Token \"$SAFE\";" | sudo tee "$OUT" >/dev/null
sudo chmod 600 "$OUT"
echo "OK: wrote $OUT"
