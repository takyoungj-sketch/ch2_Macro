#!/usr/bin/env bash
# Promote: pg_restore (custom .dump) 또는 plain SQL (.sql / .sql.gz) → land_stats 교체
# Usage:
#   promote_restore.sh /var/backups/ch2/land_stats_promote.dump
#   promote_restore.sh /var/backups/ch2/land_stats_promote.sql.gz
set -euo pipefail

INPUT="${1:?dump path required}"
TS="$(date +%Y%m%d_%H%M)"
LOG="/var/backups/ch2/restore_${TS}.log"
PRE="/tmp/land_stats_vps_pre_promote_${TS}.dump"

echo "==> VPS pre-promote backup (custom format)"
sudo -u postgres pg_dump -Fc --no-owner --no-acl -f "$PRE" land_stats
sudo mv "$PRE" "/var/backups/ch2/land_stats_vps_pre_promote_${TS}.dump"
ls -lh "/var/backups/ch2/land_stats_vps_pre_promote_${TS}.dump"

echo "==> stop backend"
sudo systemctl stop ch2-macro-backend

echo "==> recreate DB"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'land_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS land_stats;
CREATE DATABASE land_stats OWNER ch2app;
SQL

echo "==> restore ($INPUT)"
set +e
filter_pg18_sql() {
  sed -e '/^SET transaction_timeout/d' -e '/^\\restrict/d' -e '/^\\unrestrict/d'
}

if [[ "$INPUT" == *.sql.gz ]]; then
  gunzip -c "$INPUT" | filter_pg18_sql | sudo -u postgres psql -v ON_ERROR_STOP=1 -d land_stats 2>&1 | tee "$LOG"
  RC="${PIPESTATUS[1]}"
elif [[ "$INPUT" == *.sql ]]; then
  filter_pg18_sql < "$INPUT" | sudo -u postgres psql -v ON_ERROR_STOP=1 -d land_stats 2>&1 | tee "$LOG"
  RC=$?
else
  sudo -u postgres pg_restore -d land_stats --no-owner --no-acl "$INPUT" 2>&1 | tee "$LOG"
  RC="${PIPESTATUS[0]}"
fi
set -e
echo "restore exit=$RC"

echo "==> verify counts"
sudo -u postgres psql -d land_stats -t -c "SELECT COUNT(*) FROM land_transactions;"
sudo -u postgres psql -d land_stats -t -c "SELECT MAX(as_of_month) FROM land_basic_stats_v2;"

echo "==> grant ch2app (plain SQL restore 후 권한)"
sudo -u postgres psql -d land_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

ENV_FILE="/opt/ch2_Macro/backend/.env"
if grep -q '^STATS_V2_DEFAULT_AS_OF_MONTH=' "$ENV_FILE"; then
  sed -i 's/^STATS_V2_DEFAULT_AS_OF_MONTH=.*/STATS_V2_DEFAULT_AS_OF_MONTH=2026-05-01/' "$ENV_FILE"
else
  echo 'STATS_V2_DEFAULT_AS_OF_MONTH=2026-05-01' >> "$ENV_FILE"
fi

echo "==> redeploy"
if [[ -x /opt/ch2_Macro/deploy/scripts/redeploy.sh ]]; then
  bash /opt/ch2_Macro/deploy/scripts/redeploy.sh main
else
  echo "WARN: git redeploy skipped (no .git). Restart backend only."
  sudo systemctl restart ch2-macro-backend
fi

echo "==> health"
curl -sf "http://127.0.0.1:8000/health"
echo
echo "OK: promote restore complete"
