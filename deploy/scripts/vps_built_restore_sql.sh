#!/usr/bin/env bash
# VPS: built_stats SQL restore only (PG18 dump → PG16)
set -euo pipefail
DUMP=/var/backups/ch2/built_stats_promote.sql
sudo systemctl stop ch2-macro-backend || true
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'built_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS built_stats;
CREATE DATABASE built_stats OWNER ch2app;
SQL
sed -e '/^SET transaction_timeout/d' -e '/^\\restrict/d' -e '/^\\unrestrict/d' "$DUMP" \
  | sudo -u postgres psql -v ON_ERROR_STOP=1 -d built_stats
sudo -u postgres psql -d built_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL
sudo -u postgres psql -d built_stats -t -c "SELECT asset_type, COUNT(*) FROM built_transactions GROUP BY 1 ORDER BY 1;"
