#!/usr/bin/env bash
# Restore built_stats or collective_stats from filtered plain SQL .sql.gz
# Usage: vps_promote_db_sql.sh built_stats /var/backups/ch2/built_stats_promote_202608.sql.gz
set -euo pipefail
DB="${1:?database name required}"
INPUT="${2:?dump path required}"
TS="$(date +%Y%m%d_%H%M)"
PRE="/tmp/${DB}_vps_pre_promote_${TS}.dump"
PG16="/usr/lib/postgresql/16/bin/pg_dump"

echo "==> pre-promote backup $DB"
sudo -u postgres "$PG16" -Fc --no-owner --no-acl -f "$PRE" "$DB"
sudo mv "$PRE" "/var/backups/ch2/${DB}_vps_pre_promote_${TS}.dump"

echo "==> stop backend"
sudo systemctl stop ch2-macro-backend

echo "==> recreate $DB"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${DB};
CREATE DATABASE ${DB} OWNER ch2app;
SQL

filter_pg18_sql() {
  sed -e '/^SET transaction_timeout/d' -e '/^\\restrict/d' -e '/^\\unrestrict/d'
}
echo "==> restore $INPUT"
gunzip -c "$INPUT" | filter_pg18_sql | sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB"

sudo -u postgres psql -d "$DB" -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

sudo systemctl restart ch2-macro-backend
sleep 4
curl -sf http://127.0.0.1:8000/health | head -c 400
echo
echo "OK: $DB promote from $INPUT"
