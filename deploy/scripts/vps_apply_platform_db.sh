#!/usr/bin/env bash
# Apply ch2_platform schema (048) on VPS PostgreSQL
# Usage: bash /opt/ch2_Macro/deploy/scripts/vps_apply_platform_db.sh
set -euo pipefail

REPO_ROOT="/opt/ch2_Macro"
SQL_FILES=(
  "$REPO_ROOT/db/048_ch2_platform.sql"
  "$REPO_ROOT/db/048b_board_support.sql"
)
ENV_FILE="$REPO_ROOT/backend/.env"

for SQL_FILE in "${SQL_FILES[@]}"; do
  if [[ ! -f "$SQL_FILE" ]]; then
    echo "ERROR: missing $SQL_FILE" >&2
    exit 1
  fi
done

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PLATFORM_URL="${DATABASE_URL_PLATFORM:-}"
if [[ -z "$PLATFORM_URL" ]]; then
  echo "ERROR: DATABASE_URL_PLATFORM not set in backend/.env" >&2
  exit 1
fi

# postgresql+psycopg2://user:pass@host:5432/ch2_platform → psql URL
PSQL_URL="${PLATFORM_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"

DB_NAME="$(echo "$PSQL_URL" | sed -E 's|.*/([^/?]+).*|\1|')"
ADMIN_URL="$(echo "$PSQL_URL" | sed -E "s|/${DB_NAME}.*|/postgres|")"

echo "==> ensure database $DB_NAME"
psql "$ADMIN_URL" -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 \
  || psql "$ADMIN_URL" -c "CREATE DATABASE \"$DB_NAME\" OWNER $(echo "$PSQL_URL" | sed -E 's|postgresql://([^:]+):.*|\1|');"

for SQL_FILE in "${SQL_FILES[@]}"; do
  echo "==> apply $SQL_FILE"
  psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f "$SQL_FILE"
done

echo "OK: ch2_platform schema applied"
