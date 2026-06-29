#!/usr/bin/env bash
set -euo pipefail
DUMP="${1:-/var/backups/ch2/collective_stats_promote.dump}"
PG18=/usr/lib/postgresql/18/bin/pg_restore
REPO="/opt/ch2_Macro"
ENV="$REPO/backend/.env"

if [[ ! -f "$DUMP" ]]; then
  echo "ERROR: dump not found: $DUMP" >&2
  exit 1
fi

if ! grep -q '^COLLECTIVE_DATABASE_URL=' "$ENV" 2>/dev/null; then
  BUILT=$(grep '^BUILT_DATABASE_URL=' "$ENV")
  COLLECTIVE="${BUILT/BUILT_DATABASE_URL=/COLLECTIVE_DATABASE_URL=}"
  COLLECTIVE="${COLLECTIVE/built_stats/collective_stats}"
  echo "$COLLECTIVE" >> "$ENV"
fi

echo "==> stop backend"
sudo systemctl stop ch2-macro-backend

if ! sudo -u postgres psql -Atqc "SELECT 1 FROM pg_database WHERE datname='collective_stats'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE collective_stats OWNER ch2app;"
fi

echo "==> recreate collective_stats"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'collective_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS collective_stats;
CREATE DATABASE collective_stats OWNER ch2app;
SQL

echo "==> pg_restore (PG18) $DUMP"
set +e
sudo -u postgres "$PG18" -d collective_stats --no-owner --no-acl "$DUMP"
RC=$?
set -e
echo "pg_restore exit=$RC"

echo "==> verify"
sudo -u postgres psql -d collective_stats -t -c "SELECT COUNT(*) FROM collective_transactions;"
sudo -u postgres psql -d collective_stats -t -c "SELECT ROUND(100.0*COUNT(buyer_type)/NULLIF(COUNT(*),0),1) FROM collective_transactions WHERE is_valid;"

sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

echo "==> start backend"
sudo systemctl start ch2-macro-backend
sleep 3
curl -sf http://127.0.0.1:8000/health
echo
echo "OK: collective_stats promote complete"
