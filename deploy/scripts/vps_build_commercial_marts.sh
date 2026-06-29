#!/usr/bin/env bash
# VPS: DDL 032 (idempotent) + commercial cluster mart builds
set -euo pipefail

REPO=/opt/ch2_Macro
ENV="$REPO/backend/.env"
AS_OF="${1:-2026-05-01}"

DBURL=$(grep '^COLLECTIVE_DATABASE_URL=' "$ENV" | cut -d= -f2- | tr -d '\r')
if [[ -z "$DBURL" ]]; then
  BUILT=$(grep '^BUILT_DATABASE_URL=' "$ENV" | cut -d= -f2- | tr -d '\r')
  DBURL="${BUILT/built_stats/collective_stats}"
fi
export COLLECTIVE_DATABASE_URL="$DBURL"
PSQLURL="${DBURL/postgresql+psycopg2/postgresql}"

echo "==> apply DDL 032 (if needed)"
psql "$PSQLURL" -v ON_ERROR_STOP=1 -f "$REPO/db/032_collective_commercial_cluster_stats.sql"

echo "==> commercial transactions"
psql "$PSQLURL" -Atqc "SELECT COUNT(*) FROM collective_commercial_transactions"

cd "$REPO/pipeline"
PY="$REPO/backend/.venv/bin/python"
echo "==> build cluster stats as_of=$AS_OF"
"$PY" build_collective_commercial_cluster_stats.py --as-of "$AS_OF" --windows 3,5
echo "==> build rolling stats"
"$PY" build_collective_commercial_cluster_rolling_stats.py --as-of "$AS_OF" --windows 3,5

echo "==> mart counts"
psql "$PSQLURL" -Atqc "SELECT 'stats', COUNT(*) FROM collective_commercial_cluster_stats"
psql "$PSQLURL" -Atqc "SELECT 'annual', COUNT(*) FROM collective_commercial_cluster_annual_stats"
psql "$PSQLURL" -Atqc "SELECT 'rolling', COUNT(*) FROM collective_commercial_cluster_rolling_stats"
echo "OK: commercial marts built"
