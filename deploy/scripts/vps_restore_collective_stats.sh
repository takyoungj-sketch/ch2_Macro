#!/usr/bin/env bash
# Restore collective_stats from pg_dump on VPS
# Usage: bash /opt/ch2_Macro/deploy/scripts/vps_restore_collective_stats.sh [dump_path]
set -euo pipefail

REPO="/opt/ch2_Macro"
ENV="$REPO/backend/.env"
DUMP="${1:-$REPO/backups/collective_stats_promote.dump}"

if [[ ! -f "$DUMP" ]]; then
  echo "ERROR: dump not found: $DUMP" >&2
  exit 1
fi

if ! grep -q '^COLLECTIVE_DATABASE_URL=' "$ENV" 2>/dev/null; then
  BUILT=$(grep '^BUILT_DATABASE_URL=' "$ENV")
  COLLECTIVE="${BUILT/BUILT_DATABASE_URL=/COLLECTIVE_DATABASE_URL=}"
  COLLECTIVE="${COLLECTIVE/built_stats/collective_stats}"
  echo "$COLLECTIVE" >> "$ENV"
  echo "==> added COLLECTIVE_DATABASE_URL to backend/.env"
fi

CH2PASS=$(grep '^BUILT_DATABASE_URL=' "$ENV" | sed -n 's/.*:\/\/ch2app:\([^@]*\)@.*/\1/p')
export PGPASSWORD="$CH2PASS"

if ! sudo -u postgres psql -Atqc "SELECT 1 FROM pg_database WHERE datname='collective_stats'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE collective_stats OWNER ch2app;"
  echo "==> created database collective_stats"
fi

echo "==> pg_restore from $DUMP"
/usr/lib/postgresql/18/bin/pg_restore -h 127.0.0.1 -U ch2app -d collective_stats --no-owner --no-acl --clean --if-exists "$DUMP" || true

echo "==> row counts"
psql -h 127.0.0.1 -U ch2app -d collective_stats -Atqc "SELECT 'collective_transactions=' || COUNT(*) FROM collective_transactions"
psql -h 127.0.0.1 -U ch2app -d collective_stats -Atqc "SELECT 'commercial_tx=' || COUNT(*) FROM collective_commercial_transactions"

if [[ -x "$REPO/backend/.venv/bin/pip" ]]; then
  "$REPO/backend/.venv/bin/pip" install -q 'statsmodels>=0.14.0'
fi

echo "==> restart ch2-macro-backend"
sudo systemctl restart ch2-macro-backend
sleep 3

if systemctl is-active --quiet ch2-macro-backend; then
  echo "OK: ch2-macro-backend active"
else
  systemctl status ch2-macro-backend --no-pager -l || true
  exit 1
fi

curl -sf "http://127.0.0.1:8000/health" | head -c 800
echo
echo "OK: collective_stats restore complete"
