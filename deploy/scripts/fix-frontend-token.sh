#!/usr/bin/env bash
set -euo pipefail
API=$(cat /home/ubuntu/.ch2_api_token)
printf 'VITE_API_TOKEN=%s\n' "$API" > /opt/ch2_Macro/frontend/.env
cd /opt/ch2_Macro/frontend
npm run build
sudo systemctl reload nginx
curl -sS -o /dev/null -w "api_no_token=%{http_code}\n" "http://127.0.0.1/api/free/regions?limit=1"
curl -sS -H "X-Api-Token: $API" -o /dev/null -w "api_with_token=%{http_code}\n" "http://127.0.0.1/api/free/regions?limit=1"
echo "FRONTEND_TOKEN_OK"
