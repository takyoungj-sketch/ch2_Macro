#!/usr/bin/env bash
set -euo pipefail
BACKUP="/var/backups/ch2/land_stats_vps_pre_promote_20260601_1557.dump"

echo "postgres: $(postgres --version)"

sudo systemctl stop ch2-macro-backend || true

sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'land_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS land_stats;
CREATE DATABASE land_stats OWNER ch2app;
SQL

echo "==> restore VPS backup"
set +e
sudo -u postgres pg_restore -d land_stats --no-owner --no-acl "$BACKUP" 2>&1 | tail -20
set -e

sudo -u postgres psql -d land_stats -t -c "SELECT COUNT(*) FROM land_transactions;"
sudo -u postgres psql -d land_stats -t -c "SELECT MAX(as_of_month) FROM land_basic_stats_v2;"

sed -i 's/^STATS_V2_DEFAULT_AS_OF_MONTH=.*/STATS_V2_DEFAULT_AS_OF_MONTH=2026-04-01/' /opt/ch2_Macro/backend/.env
sudo systemctl start ch2-macro-backend
sleep 2
curl -sf http://127.0.0.1:8000/health
echo
echo "OK: emergency rollback"
