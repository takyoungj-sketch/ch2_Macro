#!/usr/bin/env bash
set -euo pipefail
REPO=/opt/ch2_Macro
LOG=/tmp/lt_ingest_all.log
PY="$REPO/backend/.venv/bin/python"

echo "==> grant ch2app mart + sequences (idempotent)"
sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT SELECT, INSERT, UPDATE, DELETE ON
  collective_building_annual_stats,
  collective_building_rolling_stats,
  collective_building_stats,
  collective_commercial_cluster_annual_stats
TO ch2app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO ch2app;
SQL

echo "==> ingest long-term annual (2010-2020) — residential"
set -a
# shellcheck source=/dev/null
. "$REPO/backend/.env"
set +a
cd "$REPO/pipeline"
: > "$LOG"
nohup "$PY" ingest_collective_long_term_annual.py >> "$LOG" 2>&1 &
echo "residential pid=$!"
sleep 3
tail -5 "$LOG"

echo "==> ingest long-term annual (2010-2020) — collective commercial (shop/factory)"
COMM_LOG=/tmp/lt_ingest_commercial.log
: > "$COMM_LOG"
nohup "$PY" ingest_collective_commercial_long_term_annual.py >> "$COMM_LOG" 2>&1 &
echo "commercial pid=$!"
sleep 3
tail -5 "$COMM_LOG"
