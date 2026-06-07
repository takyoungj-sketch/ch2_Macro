#!/usr/bin/env bash
# VPS: scp로 코드 반영 후 scope별 frontend 빌드 + backend restart
# Usage: bash /opt/ch2_Macro/deploy/scripts/vps_apply_scope.sh [built|land|collective|all]
set -euo pipefail

REPO=/opt/ch2_Macro
SCOPE="${1:-built}"
ENV_FILE="$REPO/backend/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing $ENV_FILE" >&2
  exit 1
fi

TOKEN=$(grep '^API_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
if [[ -z "$TOKEN" ]]; then
  echo "WARN: API_TOKEN empty — frontend API calls may fail"
fi

build_app() {
  local app="$1"
  local dir="$REPO/$app"
  if [[ ! -f "$dir/package.json" ]]; then
    echo "SKIP: $app (no package.json)"
    return 0
  fi
  echo "==> build $app"
  echo "VITE_API_TOKEN=$TOKEN" > "$dir/.env"
  chmod 600 "$dir/.env"
  cd "$dir"
  npm run build
}

case "$SCOPE" in
  built)
    build_app frontend-built
    ;;
  land)
    build_app frontend
    ;;
  collective)
    build_app frontend-collective
    ;;
  all)
    build_app frontend
    build_app frontend-built
    build_app frontend-collective
    if [[ -x "$REPO/deploy/scripts/deploy-macro-gateway.sh" ]]; then
      bash "$REPO/deploy/scripts/deploy-macro-gateway.sh"
    fi
    ;;
  *)
    echo "ERROR: unknown scope '$SCOPE' (built|land|collective|all)" >&2
    exit 1
    ;;
esac

if [[ -x "$REPO/deploy/scripts/vps_sync_nginx_api_token.sh" ]]; then
  bash "$REPO/deploy/scripts/vps_sync_nginx_api_token.sh" 2>/dev/null || true
fi

echo "==> restart ch2-macro-backend"
sudo systemctl restart ch2-macro-backend
sleep 2

if systemctl is-active --quiet ch2-macro-backend; then
  echo "OK: ch2-macro-backend active"
else
  echo "ERROR: ch2-macro-backend not active" >&2
  systemctl status ch2-macro-backend --no-pager || true
  exit 1
fi

curl -sf "http://127.0.0.1:8000/health" | head -c 400 || {
  echo "WARN: /health check failed"
  exit 1
}
echo
echo "OK: vps_apply_scope.sh $SCOPE complete"
