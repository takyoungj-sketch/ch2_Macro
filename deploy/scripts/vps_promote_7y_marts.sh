#!/usr/bin/env bash
# VPS: DDL 053 + (optional) danji tables restore + mart rebuild 3·5·7
# Usage:
#   bash /opt/ch2_Macro/deploy/scripts/vps_promote_7y_marts.sh
#   bash /opt/ch2_Macro/deploy/scripts/vps_promote_7y_marts.sh --danji-dump /var/backups/ch2/collective_danji_promote.sql.gz
#   bash /opt/ch2_Macro/deploy/scripts/vps_promote_7y_marts.sh --skip-land   # collective+built only
set -euo pipefail

REPO=/opt/ch2_Macro
ENV="$REPO/backend/.env"
PY="$REPO/backend/.venv/bin/python"
AS_OF="${AS_OF:-2026-07-01}"
WINDOWS="${WINDOWS:-3,5,7}"
DANJI_DUMP=""
SKIP_LAND=0
SKIP_DDL=0
SKIP_DANJI=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --danji-dump) DANJI_DUMP="${2:-}"; shift 2 ;;
    --skip-land) SKIP_LAND=1; shift ;;
    --skip-ddl) SKIP_DDL=1; shift ;;
    --skip-danji) SKIP_DANJI=1; shift ;;
    --as-of) AS_OF="${2:-}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

TS="$(date +%Y%m%d_%H%M%S)"
LOG="/var/backups/ch2/promote_7y_${TS}.log"
mkdir -p /var/backups/ch2
exec >>"$LOG" 2>&1

echo "==> promote 7y marts AS_OF=$AS_OF WINDOWS=$WINDOWS LOG=$LOG"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: missing $PY" >&2
  exit 1
fi
if [[ ! -f "$ENV" ]]; then
  echo "ERROR: missing $ENV" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source <(grep -E '^(DATABASE_URL|COLLECTIVE_DATABASE_URL|BUILT_DATABASE_URL)=' "$ENV" | tr -d '\r')
set +a

apply_ddl() {
  echo "==> DDL 053 (window_years <= 7)"
  for db in land_stats collective_stats built_stats; do
    echo "   -> $db"
    sudo -u postgres psql -d "$db" -v ON_ERROR_STOP=1 -f "$REPO/db/053_window_years_max_7.sql"
  done
  echo "==> DDL 049·052 (collective danji attributes)"
  sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 -f "$REPO/db/049_collective_building_attributes.sql"
  sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 -f "$REPO/db/052_collective_attributes_dictionary_columns.sql"
}

restore_danji() {
  if [[ -z "$DANJI_DUMP" || ! -f "$DANJI_DUMP" ]]; then
    echo "==> skip danji restore (no dump)"
    return 0
  fi
  echo "==> restore danji tables from $DANJI_DUMP"
  sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 <<'SQL'
TRUNCATE builder_master RESTART IDENTITY CASCADE;
TRUNCATE collective_building_attributes RESTART IDENTITY CASCADE;
SQL
  filter_pg18_sql() {
    sed -e '/^SET transaction_timeout/d' -e '/^\\restrict/d' -e '/^\\unrestrict/d'
  }
  gunzip -c "$DANJI_DUMP" | filter_pg18_sql | sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1
  sudo -u postgres psql -d collective_stats -Atqc "SELECT 'builder_master', count(*) FROM builder_master UNION ALL SELECT 'collective_building_attributes', count(*) FROM collective_building_attributes;"
}

fix_ownership() {
  echo "==> ensure ch2app owns public tables"
  for db in land_stats collective_stats built_stats; do
    sudo -u postgres psql -d "$db" -v ON_ERROR_STOP=1 <<'SQL'
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO ch2app', r.tablename);
  END LOOP;
END $$;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
SQL
  done
}

rebuild_built() {
  echo "==> built scope_stats"
  cd "$REPO/backend"
  export PYTHONUNBUFFERED=1
  "$PY" ../pipeline/built/build_scope_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
}

rebuild_collective() {
  echo "==> collective marts"
  cd "$REPO/backend"
  export PYTHONUNBUFFERED=1
  "$PY" ../pipeline/build_collective_building_rolling_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
  "$PY" ../pipeline/build_collective_building_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
  "$PY" ../pipeline/build_collective_market_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
  "$PY" ../pipeline/build_collective_commercial_cluster_rolling_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
  "$PY" ../pipeline/build_collective_commercial_cluster_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
  "$PY" ../pipeline/build_collective_commercial_market_stats.py --as-of "$AS_OF" --windows "$WINDOWS"
}

rebuild_land() {
  echo "==> land V2 marts (may take hours)"
  cd "$REPO/backend"
  export PYTHONUNBUFFERED=1
  "$PY" ../pipeline/build_stats_v2.py --as-of "$AS_OF" --windows "$WINDOWS"
  "$PY" ../pipeline/build_upper_stats_v2.py --as-of "$AS_OF" --windows "$WINDOWS"
}

verify_counts() {
  echo "==> verify window_years counts"
  sudo -u postgres psql -d land_stats -Atqc "SELECT 'land_v2', window_years, count(*) FROM land_basic_stats_v2 GROUP BY 2 ORDER BY 2;"
  sudo -u postgres psql -d collective_stats -Atqc "SELECT 'coll_roll', window_years, count(*) FROM collective_building_rolling_stats GROUP BY 2 ORDER BY 2;"
  sudo -u postgres psql -d built_stats -Atqc "SELECT 'built_scope', window_years, count(*) FROM built_scope_stats GROUP BY 2 ORDER BY 2;" 2>/dev/null || true
}

if [[ "$SKIP_DDL" -eq 0 ]]; then
  apply_ddl
else
  echo "==> skip DDL (already applied)"
fi
if [[ "$SKIP_DANJI" -eq 0 ]]; then
  restore_danji
else
  echo "==> skip danji restore"
fi
fix_ownership
rebuild_built
rebuild_collective
if [[ "$SKIP_LAND" -eq 0 ]]; then
  rebuild_land
else
  echo "==> skip land rebuild"
fi
verify_counts
sudo systemctl restart ch2-macro-backend
sleep 3
curl -sf http://127.0.0.1:8000/health | head -c 400
echo
echo "OK: promote 7y complete LOG=$LOG"
