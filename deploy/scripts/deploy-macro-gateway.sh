#!/usr/bin/env bash
# Macro 유형 선택 게이트웨이 — deploy/macro-gateway → nginx 가 / 에서 서빙
# Usage: sudo bash /opt/ch2_Macro/deploy/scripts/deploy-macro-gateway.sh
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/ch2_Macro}"
SRC="$REPO_ROOT/deploy/macro-gateway"

if [[ ! -f "$SRC/index.html" ]]; then
  echo "missing $SRC/index.html"
  exit 1
fi

echo "OK: macro gateway at $SRC (nginx root location = /)"
ls -la "$SRC/index.html" "$SRC/style.css"
