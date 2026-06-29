#!/usr/bin/env bash
set -euo pipefail
DUMP="${1:-/var/backups/ch2/built_stats_promote.dump}"
PG18=/usr/lib/postgresql/18/bin/pg_restore

echo "==> stop backend"
sudo systemctl stop ch2-macro-backend

echo "==> recreate built_stats"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'built_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS built_stats;
CREATE DATABASE built_stats OWNER ch2app;
SQL

echo "==> pg_restore (PG18) $DUMP"
set +e
sudo -u postgres "$PG18" -d built_stats --no-owner --no-acl "$DUMP"
RC=$?
set -e
echo "pg_restore exit=$RC"

echo "==> verify"
sudo -u postgres psql -d built_stats -t -c "SELECT asset_type, COUNT(*) FROM built_transactions GROUP BY 1 ORDER BY 1;"
sudo -u postgres psql -d built_stats -t -c "SELECT ROUND(100.0*COUNT(display_address)/NULLIF(COUNT(*),0),1) FROM built_transactions;"

sudo -u postgres psql -d built_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

echo "==> start backend"
sudo systemctl start ch2-macro-backend
sleep 3
curl -sf http://127.0.0.1:8000/health
echo
echo "OK: built_stats promote complete"
