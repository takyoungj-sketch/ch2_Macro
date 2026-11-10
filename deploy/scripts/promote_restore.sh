#!/usr/bin/env bash
# Promote: pg_restore (custom .dump) 또는 plain SQL (.sql / .sql.gz) → land_stats 교체
# Usage:
#   promote_restore.sh /var/backups/ch2/land_stats_promote.dump
#   promote_restore.sh /var/backups/ch2/land_stats_promote.sql.gz
set -euo pipefail

INPUT="${1:?dump path required}"
REPO_ROOT="${CH2_PROMOTE_REPO_ROOT:-/opt/ch2_Macro}"
BACKUP_DIR="${CH2_PROMOTE_BACKUP_DIR:-/var/backups/ch2}"
ENV_FILE="$REPO_ROOT/backend/.env"
BACKEND_UNIT=ch2-macro-backend.service
HEALTH_URL=http://127.0.0.1:8000/health
# Optional: explicit month after restore (default = latest completed monthly publication)
AS_OF_OVERRIDE="${2:-}"
MONTH_PATTERN='^[0-9]{4}-(0[1-9]|1[0-2])-01$'
if [[ -n "$AS_OF_OVERRIDE" && ! "$AS_OF_OVERRIDE" =~ $MONTH_PATTERN ]]; then
  echo "ERROR: expected YYYY-MM-01 for the explicit land stats month"
  exit 1
fi
TS="$(date +%Y%m%d_%H%M)"
LOG="$BACKUP_DIR/restore_${TS}.log"
PRE="${TMPDIR:-/tmp}/land_stats_vps_pre_promote_${TS}.dump"
PG18_BIN="/usr/lib/postgresql/18/bin"
if [[ -x "${PG18_BIN}/pg_dump" ]]; then
  PG_DUMP="${PG18_BIN}/pg_dump"
  PG_RESTORE="${PG18_BIN}/pg_restore"
else
  PG_DUMP="pg_dump"
  PG_RESTORE="pg_restore"
fi

fetch_health() {
  local response
  response=$(curl --silent --fail --max-time 3 --write-out '\n%{http_code}' "$1") || return 1
  [[ "${response##*$'\n'}" == 200 ]] || return 1
  printf '%s' "${response%$'\n'*}"
}

check_health_payload() {
  python3 -c '
import json
import sys

try:
    body = json.load(sys.stdin)
except (ValueError, UnicodeError):
    sys.exit("invalid /health JSON")
if not isinstance(body, dict) or body.get("status") != "ok":
    sys.exit("/health status is not ok")
if "configured_land_as_of_month" not in body:
    sys.exit("/health lacks configured_land_as_of_month")
if len(sys.argv) > 1:
    if body.get("configured_land_as_of_month") != sys.argv[1]:
        sys.exit(f"/health configured land month does not match {sys.argv[1]}")
    if body.get("latest_as_of_month") != sys.argv[2]:
        sys.exit(f"/health latest land data month does not match {sys.argv[2]}")
' "$@"
}

wait_for_backend() {
  local unit=$1 url=$2 month=$3 latest=$4 response state last_state=
  while true; do
    if ! systemctl is-active --quiet "$unit"; then
      state="systemd service is not active"
    elif ! response=$(fetch_health "$url"); then
      state="/health request failed"
    elif state=$(check_health_payload "$month" "$latest" <<<"$response" 2>&1); then
      if systemctl is-active --quiet "$unit"; then
        return 0
      fi
      state="systemd service stopped during the probe"
    fi
    if [[ "$state" != "$last_state" ]]; then
      printf 'Waiting for backend: %s\n' "$state"
      last_state=$state
    fi
    sleep 2
  done
}

# Check the artifact and configuration before stopping the service.
if [[ ! -f "$INPUT" || ! -s "$INPUT" ]]; then
  echo "ERROR: missing or empty Promote dump" >&2
  exit 1
fi
if [[ ! -d "$BACKUP_DIR" || ! -w "$BACKUP_DIR" || ! -f "$ENV_FILE" || ! -w "$ENV_FILE" ]]; then
  echo "ERROR: backup directory or backend configuration is not writable" >&2
  exit 1
fi
case "$INPUT" in
  *.sql.gz) gzip -t -- "$INPUT" ;;
  *.sql) [[ -r "$INPUT" ]] || { echo "ERROR: unreadable Promote SQL" >&2; exit 1; } ;;
  *) sudo -u postgres "$PG_RESTORE" --list "$INPUT" >/dev/null ;;
esac
if ! command -v python3 >/dev/null || ! command -v timeout >/dev/null; then
  echo "ERROR: Promote readiness requires python3 and timeout" >&2
  exit 1
fi
if ! PREFLIGHT_HEALTH=$(fetch_health "$HEALTH_URL") ||
   ! check_health_payload <<<"$PREFLIGHT_HEALTH"; then
  echo "ERROR: verify the deployed backend health contract before Promote; database unchanged" >&2
  exit 1
fi

echo "==> VPS pre-promote backup (custom format, $PG_DUMP)"
sudo -u postgres "$PG_DUMP" -Fc --no-owner --no-acl -f "$PRE" land_stats
sudo mv "$PRE" "$BACKUP_DIR/land_stats_vps_pre_promote_${TS}.dump"
ls -lh "$BACKUP_DIR/land_stats_vps_pre_promote_${TS}.dump"

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
  RC=$?
elif [[ "$INPUT" == *.sql ]]; then
  filter_pg18_sql < "$INPUT" | sudo -u postgres psql -v ON_ERROR_STOP=1 -d land_stats 2>&1 | tee "$LOG"
  RC=$?
else
  sudo -u postgres "$PG_RESTORE" -d land_stats --no-owner --no-acl "$INPUT" 2>&1 | tee "$LOG"
  RC=$?
fi
set -e
echo "restore exit=$RC"
if (( RC != 0 )); then
  exit "$RC"
fi

echo "==> verify counts"
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d land_stats -t -c "SELECT COUNT(*) FROM land_transactions;"
LATEST_DATA_MONTH="$(sudo -u postgres psql -XAt -v ON_ERROR_STOP=1 -d land_stats -c "SELECT MAX(as_of_month) FROM land_basic_stats_v2;")"
echo "latest restored land data month: $LATEST_DATA_MONTH"

echo "==> grant ch2app (plain SQL restore 후 권한)"
sudo -u postgres psql -d land_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL

if [[ -z "$AS_OF_OVERRIDE" ]]; then
  PUB_TABLE="$(sudo -u postgres psql -XAt -v ON_ERROR_STOP=1 -d land_stats -c "SELECT to_regclass('public.land_stats_v2_publications');")"
  if [[ -n "$PUB_TABLE" ]]; then
    AS_OF_OVERRIDE="$(sudo -u postgres psql -XAt -v ON_ERROR_STOP=1 -d land_stats -c "SELECT MAX(as_of_month) FROM land_stats_v2_publications;")"
  else
    echo "WARN: legacy dump without completion records; using newest restored basic stats month"
    AS_OF_OVERRIDE="$LATEST_DATA_MONTH"
  fi
fi
if [[ ! "$AS_OF_OVERRIDE" =~ $MONTH_PATTERN ]]; then
  echo "ERROR: no valid land stats publication month"
  exit 1
fi
MONTH_PRESENT="$(sudo -u postgres psql -XAt -v ON_ERROR_STOP=1 -d land_stats -c "SELECT EXISTS (SELECT 1 FROM land_basic_stats_v2 WHERE as_of_month = '$AS_OF_OVERRIDE');")"
if [[ "$MONTH_PRESENT" != t ]]; then
  echo "ERROR: requested land stats month $AS_OF_OVERRIDE is absent from the restored data" >&2
  exit 1
fi
echo "==> set STATS_V2_DEFAULT_AS_OF_MONTH=$AS_OF_OVERRIDE"
if grep -q '^STATS_V2_DEFAULT_AS_OF_MONTH=' "$ENV_FILE"; then
  sed -i "s/^STATS_V2_DEFAULT_AS_OF_MONTH=.*/STATS_V2_DEFAULT_AS_OF_MONTH=${AS_OF_OVERRIDE}/" "$ENV_FILE"
else
  echo "STATS_V2_DEFAULT_AS_OF_MONTH=${AS_OF_OVERRIDE}" >> "$ENV_FILE"
fi

report_backend_state() {
  timeout 5s systemctl show "$BACKEND_UNIT" \
    -p ActiveState -p SubState -p Result -p MainPID -p ExecMainStatus >&2 || true
  echo "Restore log: $LOG" >&2
  echo "Inspect service logs locally: sudo journalctl -u $BACKEND_UNIT -n 40 --no-pager" >&2
}

echo "==> restart backend"
if [[ -e "$REPO_ROOT/.git" && -x "$REPO_ROOT/deploy/scripts/redeploy.sh" ]]; then
  CH2_REDEPLOY_SKIP_HEALTH=1 bash "$REPO_ROOT/deploy/scripts/redeploy.sh" main || {
    echo "ERROR: backend redeploy command failed after restore" >&2
    report_backend_state
    exit 1
  }
elif ! sudo systemctl restart "$BACKEND_UNIT"; then
  echo "ERROR: systemd restart command failed after restore" >&2
  report_backend_state
  exit 1
fi

echo "==> health (up to 120s; expected land month=$AS_OF_OVERRIDE, latest data=$LATEST_DATA_MONTH)"
export -f fetch_health check_health_payload wait_for_backend
if timeout 120s bash -c 'wait_for_backend "$@"' _ "$BACKEND_UNIT" "$HEALTH_URL" "$AS_OF_OVERRIDE" "$LATEST_DATA_MONTH"; then
  echo "OK: promote restore complete"
  exit 0
else
  HEALTH_RC=$?
fi
if (( HEALTH_RC == 124 )); then
  echo "ERROR: backend readiness timed out after 120s" >&2
else
  echo "ERROR: backend readiness failed after Promote (probe exit=$HEALTH_RC)" >&2
fi
report_backend_state
exit 1
