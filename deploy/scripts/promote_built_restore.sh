#!/usr/bin/env bash
# Promote: built_stats dump → VPS restore
# Usage: promote_built_restore.sh /var/backups/ch2/built_stats_promote.dump
set -euo pipefail

INPUT="${1:?dump path required}"
TS="$(date +%Y%m%d_%H%M)"
LOG="/var/backups/ch2/built_restore_${TS}.log"
PRE="/tmp/built_stats_vps_pre_promote_${TS}.dump"

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='built_stats'" | grep -q 1; then
  echo "==> create built_stats database"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE built_stats OWNER ch2app;"
fi

echo "==> VPS pre-promote backup (built_stats)"
sudo -u postgres pg_dump -Fc --no-owner --no-acl -f "$PRE" built_stats
sudo mv "$PRE" "/var/backups/ch2/built_stats_vps_pre_promote_${TS}.dump"
ls -lh "/var/backups/ch2/built_stats_vps_pre_promote_${TS}.dump"

echo "==> stop backend"
sudo systemctl stop ch2-macro-backend

echo "==> recreate built_stats"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'built_stats' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS built_stats;
CREATE DATABASE built_stats OWNER ch2app;
SQL

echo "==> restore ($INPUT)"
set +e
if [[ "$INPUT" == *.sql.gz ]]; then
  gunzip -c "$INPUT" | sudo -u postgres psql -v ON_ERROR_STOP=1 -d built_stats 2>&1 | tee "$LOG"
  RC="${PIPESTATUS[1]}"
elif [[ "$INPUT" == *.sql ]]; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -d built_stats -f "$INPUT" 2>&1 | tee "$LOG"
  RC=$?
else
  sudo -u postgres pg_restore -d built_stats --no-owner --no-acl "$INPUT" 2>&1 | tee "$LOG"
  RC="${PIPESTATUS[0]}"
fi
set -e
echo "restore exit=$RC"

echo "==> verify counts"
sudo -u postgres psql -d built_stats -t -c "SELECT asset_type, COUNT(*) FROM built_transactions GROUP BY asset_type ORDER BY 1;"
sudo -u postgres psql -d built_stats -t -c "SELECT COUNT(*) FROM region_codes;"

echo "==> grant ch2app"
sudo -u postgres psql -d built_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

echo "==> restart backend + redeploy frontends"
if [[ -x /opt/ch2_Macro/deploy/scripts/redeploy.sh ]]; then
  bash /opt/ch2_Macro/deploy/scripts/redeploy.sh main
else
  sudo systemctl restart ch2-macro-backend
fi

echo "==> health"
curl -sf "http://127.0.0.1:8000/health"
echo
echo "OK: built_stats promote restore complete"
