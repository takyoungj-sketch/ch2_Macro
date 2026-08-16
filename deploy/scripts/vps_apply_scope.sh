#!/usr/bin/env bash
# VPS: scp로 코드 반영 후 scope별 frontend 빌드 + backend restart
# Usage: bash /opt/ch2_Macro/deploy/scripts/vps_apply_scope.sh [built|land|collective|profile|rent|lab|all]
set -euo pipefail

REPO=/opt/ch2_Macro
SCOPE="${1:-built}"
ENV_FILE="$REPO/backend/.env"
NGINX_TEMPLATE="$REPO/deploy/templates/nginx-ch2-macro.conf"
NGINX_SITE="/etc/nginx/sites-available/ch2-macro"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing $ENV_FILE" >&2
  exit 1
fi

TOKEN=$(grep '^API_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
if [[ -z "$TOKEN" ]]; then
  echo "WARN: API_TOKEN empty — frontend API calls may fail"
fi
VWORLD_KEY=$(grep '^VWORLD_API_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r' || true)

build_app() {
  local app="$1"
  local dir="$REPO/$app"
  if [[ ! -f "$dir/package.json" ]]; then
    echo "SKIP: $app (no package.json)"
    return 0
  fi
  echo "==> build $app"
  {
    echo "VITE_API_TOKEN=$TOKEN"
    if [[ -n "${VWORLD_KEY:-}" ]]; then
      echo "VITE_VWORLD_API_KEY=$VWORLD_KEY"
    fi
  } > "$dir/.env"
  chmod 600 "$dir/.env"
  cd "$dir"
  if [[ -f package-lock.json ]]; then
    npm ci --silent
  fi
  npm run build
}

apply_nginx() {
  if [[ -f "$NGINX_TEMPLATE" ]]; then
    echo "==> nginx site from template"
    sudo cp "$NGINX_TEMPLATE" "$NGINX_SITE"
    sudo nginx -t
    sudo systemctl reload nginx
  fi
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
  profile)
    build_app frontend-profile
    apply_nginx
    ;;
  rent)
    build_app frontend-rent
    apply_nginx
    ;;
  lab)
    build_app frontend-lab
    apply_nginx
    ;;
  all)
    build_app frontend
    build_app frontend-built
    build_app frontend-collective
    build_app frontend-profile
    build_app frontend-rent
    build_app frontend-lab
    if [[ -x "$REPO/deploy/scripts/deploy-macro-gateway.sh" ]]; then
      bash "$REPO/deploy/scripts/deploy-macro-gateway.sh"
    fi
    apply_nginx
    ;;
  *)
    echo "ERROR: unknown scope '$SCOPE' (built|land|collective|profile|rent|lab|all)" >&2
    exit 1
    ;;
esac

if [[ -x "$REPO/deploy/scripts/vps_sync_nginx_api_token.sh" ]]; then
  bash "$REPO/deploy/scripts/vps_sync_nginx_api_token.sh" 2>/dev/null || true
fi

echo "==> restart ch2-macro-backend"
sudo systemctl restart ch2-macro-backend
sleep 5

if systemctl is-active --quiet ch2-macro-backend; then
  echo "OK: ch2-macro-backend active"
else
  echo "ERROR: ch2-macro-backend not active" >&2
  systemctl status ch2-macro-backend --no-pager || true
  exit 1
fi

for i in 1 2 3 4 5; do
  if curl -sf "http://127.0.0.1:8000/health" | head -c 400; then
    echo
    break
  fi
  if [[ "$i" -eq 5 ]]; then
    echo "WARN: /health check failed" >&2
    exit 1
  fi
  sleep 2
done
echo "OK: vps_apply_scope.sh $SCOPE complete"
