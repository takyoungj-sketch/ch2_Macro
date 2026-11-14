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
# 재시작 직후에는 아직 응답하지 않을 수 있다 → 다시 묻되 전체를 HEALTH_WAIT(기본 60초) 안으로 묶는다.
# curl 한 번은 남은 시간과 3초 중 짧은 쪽, 쉬는 시간은 남은 시간과 2초 중 짧은 쪽 → 마감을 넘지 않는다. 끝내 실패하면 종료 코드 1.
HEALTH_URL="${CH2_HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_WAIT="${CH2_HEALTH_WAIT_SEC:-60}"
wait_health() {
  local deadline=$((SECONDS + HEALTH_WAIT)) body rem
  while :; do
    rem=$((deadline - SECONDS))
    (( rem > 0 )) || break
    if body=$(curl -sf --max-time "$(( rem < 3 ? rem : 3 ))" "$HEALTH_URL"); then
      printf '%s' "$body" | head -c 400
      echo
      return 0
    fi
    rem=$((deadline - SECONDS))
    (( rem > 0 )) || break
    sleep "$(( rem < 2 ? rem : 2 ))"
  done
  echo "ERROR: $HEALTH_URL 이 ${HEALTH_WAIT}초 안에 응답하지 않음" >&2
  return 1
}
wait_health
echo "OK: $DB promote from $INPUT"
